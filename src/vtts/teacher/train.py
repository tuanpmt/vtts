"""Plain-PyTorch VITS training loop: AMP on CUDA, resumable, NaN-safe.

Options for fast GPUs: bf16 autocast, a learning-rate override for large batches, TF32, pinned
memory. With AMP, steps with non-finite gradients are skipped by the GradScaler (logged `scale` drops).

Loss recipe and optimizer follow Piper/VITS: discriminator step first, then the
generator step with adversarial + feature-matching + mel (x c_mel) + duration + KL
(x c_kl); AdamW(lr 2e-4, betas 0.8/0.99, eps 1e-9) with exponential decay per epoch.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

import torch
import torch.distributed as dist
from torch.nn import functional as F
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader

from .config import TeacherConfig
from .data import BucketSampler, TeacherDataset, collate
from .model import build_discriminator, build_generator, load_warmstart
from .vits.commons import slice_segments
from .vits.losses import discriminator_loss, feature_loss, generator_loss, kl_loss
from .vits.mel_processing import mel_spectrogram_torch, spec_to_mel_torch

KEEP_LAST = 3


def latest_checkpoint(out_dir: Path) -> Path | None:
    ckpts = sorted(Path(out_dir).glob("ckpt_*.pt"))
    return ckpts[-1] if ckpts else None


def _save(out_dir: Path, state: dict) -> None:
    path = out_dir / f"ckpt_{state['step']:07d}.pt"
    tmp = path.with_suffix(".tmp")
    torch.save(state, tmp)
    tmp.replace(path)
    for old in sorted(out_dir.glob("ckpt_*.pt"))[:-KEEP_LAST]:
        if (out_dir / "best.pt").exists() and (out_dir / "best.pt").resolve() == old.resolve():
            continue
        old.unlink()


def _log(out_dir: Path, row: dict) -> None:
    with (out_dir / "log.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


def _one_thread(_: int) -> None:
    """Data workers each use one intra-op thread; otherwise every worker spawns one thread per
    core and they starve each other (and the training process)."""
    torch.set_num_threads(1)


def train(cfg: TeacherConfig, train_csv: Path, wav_dir: Path, cache_dir: Path | None, out_dir: Path,
          warmstart: Path | None, max_steps: int, ckpt_every: int, device: str = "cuda",
          log_every: int = 50, num_workers: int = 0,
          nan_steps: frozenset[int] = frozenset(), max_batch_frames: int | None = None,
          amp_dtype: str = "fp16", learning_rate: float | None = None) -> None:
    """Train until `max_steps`; resumes from the newest checkpoint in out_dir if any.

    `nan_steps` is a testing aid: the generator loss is replaced by NaN at those steps.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dev = torch.device(device)
    use_amp = dev.type == "cuda"
    # multi-GPU: started with torchrun (scripts/teacher/train_teacher.py initializes the process
    # group); each rank trains on its share of the batches and rank 0 alone logs and saves
    ddp = dist.is_available() and dist.is_initialized()
    rank, world = (dist.get_rank(), dist.get_world_size()) if ddp else (0, 1)
    main = rank == 0
    # bf16 (Ampere and newer) needs no loss scaling to stay finite; the GradScaler is kept in both
    # modes because it also skips optimizer steps whose gradients are not finite, without a host sync
    autocast_dtype = torch.bfloat16 if amp_dtype == "bf16" else torch.float16
    if dev.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    lr = learning_rate if learning_rate is not None else cfg.learning_rate

    g, d = build_generator(cfg).to(dev), build_discriminator(cfg).to(dev)
    # fused AdamW: one kernel per step instead of several per tensor, and no host sync for the
    # GradScaler's inf check; the CPU-side launch overhead is what limits a slow host CPU
    fused = dev.type == "cuda"
    opt_g = torch.optim.AdamW(g.parameters(), lr, betas=cfg.betas, eps=cfg.eps, fused=fused)
    opt_d = torch.optim.AdamW(d.parameters(), lr, betas=cfg.betas, eps=cfg.eps, fused=fused)
    sched_g = torch.optim.lr_scheduler.ExponentialLR(opt_g, gamma=cfg.lr_decay)
    sched_d = torch.optim.lr_scheduler.ExponentialLR(opt_d, gamma=cfg.lr_decay)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    step, epoch = 0, 0

    resume = latest_checkpoint(out_dir)
    if resume is not None:
        st = torch.load(resume, map_location=dev, weights_only=False)
        g.load_state_dict(st["g"])
        d.load_state_dict(st["d"])
        opt_g.load_state_dict(st["opt_g"])
        opt_d.load_state_dict(st["opt_d"])
        for opt in (opt_g, opt_d):  # a checkpoint saved without fused AdamW must not switch it off
            for group in opt.param_groups:
                group["fused"], group["foreach"] = fused or None, None if fused else group.get("foreach")
        sched_g.load_state_dict(st["sched_g"])
        sched_d.load_state_dict(st["sched_d"])
        scaler.load_state_dict(st["scaler"])
        step, epoch = st["step"], st["epoch"]
    elif warmstart is not None:
        load_warmstart(g, d, warmstart)
    g_mod, d_mod = g, d  # unwrapped modules: checkpoints never carry the "module." prefix
    if ddp:
        ids = [dev.index] if dev.type == "cuda" else None
        g, d = DDP(g, device_ids=ids), DDP(d, device_ids=ids)

    ds = TeacherDataset(train_csv, wav_dir, cache_dir, cfg)
    sampler = BucketSampler(ds.frame_lengths(), cfg.batch_size, max_frames=max_batch_frames,
                            rank=rank, world_size=world)
    seg_frames = cfg.segment_size // cfg.hop_length
    loader = DataLoader(ds, batch_sampler=sampler, num_workers=num_workers,
                        collate_fn=lambda b: collate(b, seg_frames, cfg.hop_length),
                        persistent_workers=num_workers > 0, worker_init_fn=_one_thread,
                        pin_memory=dev.type == "cuda",
                        prefetch_factor=4 if num_workers > 0 else None)

    def state() -> dict:
        return {"g": g_mod.state_dict(), "d": d_mod.state_dict(), "opt_g": opt_g.state_dict(),
                "opt_d": opt_d.state_dict(), "sched_g": sched_g.state_dict(),
                "sched_d": sched_d.state_dict(), "scaler": scaler.state_dict(),
                "step": step, "epoch": epoch, "config": cfg.__dict__}

    g.train()
    d.train()
    t_last = time.time()
    while step < max_steps:
        sampler.set_epoch(epoch)
        for batch in loader:
            if step >= max_steps:
                break
            step += 1
            x, x_len = batch["ids"].to(dev, non_blocking=True), batch["ids_lengths"].to(dev, non_blocking=True)
            spec = batch["spec"].to(dev, non_blocking=True)
            spec_len = batch["spec_lengths"].to(dev, non_blocking=True)
            wav = batch["wav"].to(dev, non_blocking=True)

            with torch.autocast(dev.type, dtype=autocast_dtype, enabled=use_amp):
                y_hat, l_length, _attn, ids_slice, _x_mask, z_mask, (_z, z_p, m_p, logs_p, _m_q,
                                                                     logs_q) = g(x, x_len, spec, spec_len)
            y = slice_segments(wav, ids_slice * cfg.hop_length, cfg.segment_size)
            mel = spec_to_mel_torch(spec, cfg.filter_length, cfg.mel_channels, cfg.sample_rate,
                                    cfg.mel_fmin, cfg.mel_fmax)
            y_mel = slice_segments(mel, ids_slice, seg_frames)
            y_hat_mel = mel_spectrogram_torch(y_hat.squeeze(1).float(), cfg.filter_length,
                                              cfg.mel_channels, cfg.sample_rate, cfg.hop_length,
                                              cfg.win_length, cfg.mel_fmin, cfg.mel_fmax)

            # discriminator step (must finish before the generator re-runs D)
            with torch.autocast(dev.type, dtype=autocast_dtype, enabled=use_amp):
                d_real, d_fake, _, _ = d(y, y_hat.detach())
            loss_d, _, _ = discriminator_loss([r.float() for r in d_real], [f.float() for f in d_fake])
            # without AMP (CPU) a host check skips the step; with AMP the GradScaler skips steps with
            # non-finite gradients on the GPU, so the loop never waits for the device here
            skipped = False if use_amp else not torch.isfinite(loss_d)
            opt_d.zero_grad(set_to_none=True)
            if not skipped:
                scaler.scale(loss_d).backward()
                scaler.step(opt_d)

            # generator step; D's gradients from this loss are thrown away, so D skips the all-reduce
            no_sync = d.no_sync() if ddp else contextlib.nullcontext()
            no_sync.__enter__()
            with torch.autocast(dev.type, dtype=autocast_dtype, enabled=use_amp):
                _, d_fake_g, fmap_r, fmap_g = d(y, y_hat)
            loss_dur = torch.sum(l_length.float())
            loss_mel = F.l1_loss(y_mel, y_hat_mel) * cfg.c_mel
            loss_kl = kl_loss(z_p.float(), logs_q.float(), m_p.float(), logs_p.float(), z_mask) * cfg.c_kl
            loss_fm = feature_loss(fmap_r, fmap_g)
            loss_adv, _ = generator_loss([f.float() for f in d_fake_g])
            loss_g = loss_adv + loss_fm + loss_mel + loss_dur + loss_kl
            if step in nan_steps:
                loss_g = loss_g * float("nan")
            skipped = skipped or (not use_amp and not torch.isfinite(loss_g))
            opt_g.zero_grad(set_to_none=True)
            if skipped:
                no_sync.__exit__(None, None, None)
                if main:
                    _log(out_dir, {"step": step, "skipped_nan": True})
            else:
                scaler.scale(loss_g).backward()
                no_sync.__exit__(None, None, None)
                scaler.step(opt_g)
            scaler.update()
            if main and not skipped and step % log_every == 0:
                now = time.time()
                _log(out_dir, {"step": step, "epoch": epoch, "loss_g": loss_g.item(),
                               "loss_d": loss_d.item(), "loss_mel": loss_mel.item(),
                               "loss_kl": loss_kl.item(), "loss_dur": loss_dur.item(),
                               "loss_fm": loss_fm.item(), "loss_adv": loss_adv.item(),
                               "lr": opt_g.param_groups[0]["lr"], "scale": scaler.get_scale(),
                               "sec_per_step": (now - t_last) / log_every})
                t_last = now
            if main and (step % ckpt_every == 0 or step == max_steps):
                _save(out_dir, state())
        else:
            epoch += 1
            sched_g.step()
            sched_d.step()
    if main:
        _save(out_dir, state())
