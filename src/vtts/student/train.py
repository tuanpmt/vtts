"""Student training: stage "front" (duration + acoustic regression), "dec" (GAN decoder on
teacher latents), "joint" (decoder fine-tuned on predicted latents). Resumable, NaN-safe,
AMP on CUDA.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from vtts.teacher.config import TeacherConfig
from vtts.teacher.model import build_discriminator
from vtts.teacher.vits.losses import discriminator_loss, feature_loss, generator_loss
from vtts.teacher.vits.mel_processing import mel_spectrogram_torch

from .config import StudentConfig
from .distill_data import DistillShards
from .model import Student

SEG_FRAMES = 32
KEEP_LAST = 3
STFT_RES = ((512, 128, 512), (1024, 256, 1024), (2048, 512, 2048))
# high-band STFT loss (hf_weight > 0): shorter windows resolve the frame-to-frame structure of
# the 5-10 kHz noise layer better than the 2048-point one
HF_STFT_RES = ((256, 64, 256), (512, 128, 512), (1024, 256, 1024))
DISCS = ("mpd", "mpd+mrd", "mpd+mrd-hf")


# ---------------- batches ----------------

def front_batch(items: list[dict], latent: int, stats: dict | None = None) -> dict:
    n = max(len(it["ids"]) for it in items)
    t = max(int(it["dur"].sum()) for it in items)
    b = len(items)
    ids = torch.zeros(b, n, dtype=torch.long)
    dur = torch.zeros(b, n, dtype=torch.long)
    tok_mask = torch.zeros(b, n)
    z = torch.zeros(b, latent, t)
    frame_mask = torch.zeros(b, t)
    for k, it in enumerate(items):
        m, tt = len(it["ids"]), int(it["dur"].sum())
        ids[k, :m] = torch.from_numpy(it["ids"].astype(np.int64))
        dur[k, :m] = torch.from_numpy(it["dur"].astype(np.int64))
        tok_mask[k, :m] = 1
        z[k, :, :tt] = torch.from_numpy(it["z"].astype(np.float32))
        frame_mask[k, :tt] = 1
    out = {"ids": ids, "dur": dur, "tok_mask": tok_mask, "z": z, "frame_mask": frame_mask}
    if stats is not None and all("lf0" in it for it in items):
        pros = torch.zeros(b, 2, t)
        for k, it in enumerate(items):
            tt = int(it["dur"].sum())
            lf0 = (np.asarray(it["lf0"], np.float32) - stats["lf0_mean"]) / stats["lf0_std"]
            en = (np.asarray(it["energy"], np.float32) - stats["energy_mean"]) / stats["energy_std"]
            pros[k, 0, :tt] = torch.from_numpy(lf0)
            pros[k, 1, :tt] = torch.from_numpy(en)
        out["prosody"] = pros
    return out


def crop(it: dict, rnd: random.Random, hop: int) -> tuple[int, np.ndarray, np.ndarray]:
    t = int(it["dur"].sum())
    start = rnd.randint(0, max(0, t - SEG_FRAMES))
    z = np.zeros((it["z"].shape[0], SEG_FRAMES), np.float32)
    a = np.zeros(SEG_FRAMES * hop, np.float32)
    zz = it["z"][:, start: start + SEG_FRAMES].astype(np.float32)
    z[:, : zz.shape[1]] = zz
    aa = it["audio"][start * hop: (start + SEG_FRAMES) * hop].astype(np.float32) / 32767.0
    a[: len(aa)] = aa
    return start, z, a


# ---------------- losses ----------------

def mr_stft_loss(y_hat: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    loss = 0.0
    for n_fft, hop, win in STFT_RES:
        w = torch.hann_window(win, device=y.device)
        s_hat = torch.stft(y_hat, n_fft, hop, win, w, return_complex=True).abs().clamp_min(1e-5)
        s = torch.stft(y, n_fft, hop, win, w, return_complex=True).abs().clamp_min(1e-5)
        sc = torch.norm(s - s_hat, p="fro") / torch.norm(s, p="fro").clamp_min(1e-5)
        loss = loss + sc + F.l1_loss(torch.log(s_hat), torch.log(s))
    return loss / len(STFT_RES)


def hf_stft_loss(y_hat: torch.Tensor, y: torch.Tensor, lo_hz: float = 4000.0,
                 sr: int = 22050, resolutions=HF_STFT_RES) -> torch.Tensor:
    """Spectral convergence + log-magnitude L1 restricted to bins at or above lo_hz.

    The full-band losses are dominated by the loud low band, so an excess noise floor at
    5-10 kHz (20-40 dB below the formants) costs almost nothing; this term weighs that band
    on its own."""
    loss = 0.0
    for n_fft, hop, win in resolutions:
        w = torch.hann_window(win, device=y.device)
        lo = round(lo_hz * n_fft / sr)
        s_hat = torch.stft(y_hat, n_fft, hop, win, w, return_complex=True).abs()[:, lo:].clamp_min(1e-5)
        s = torch.stft(y, n_fft, hop, win, w, return_complex=True).abs()[:, lo:].clamp_min(1e-5)
        sc = torch.norm(s - s_hat, p="fro") / torch.norm(s, p="fro").clamp_min(1e-5)
        loss = loss + sc + F.l1_loss(torch.log(s_hat), torch.log(s))
    return loss / len(resolutions)


def build_disc(kind: str) -> torch.nn.Module:
    """mpd (VITS multi-period + scale), mpd+mrd (+ 3 linear-magnitude spectrogram
    discriminators), mpd+mrd-hf (+ 3 more on the log magnitude above 4 kHz)."""
    from .discriminators import (
        CombinedDiscriminator,
        HighBandDiscriminator,
        MultiResolutionDiscriminator,
    )

    if kind not in DISCS:
        raise ValueError(f"unknown discriminator {kind!r}; choose from {DISCS}")
    mpd = build_discriminator(TeacherConfig())
    if kind == "mpd":
        return mpd
    parts = [mpd, MultiResolutionDiscriminator()]
    if kind == "mpd+mrd-hf":
        parts.append(HighBandDiscriminator())
    return CombinedDiscriminator(*parts)


def mel(y: torch.Tensor) -> torch.Tensor:
    return mel_spectrogram_torch(y, 1024, 80, 22050, 256, 1024, 0.0, None)


# ---------------- checkpointing ----------------

def latest(out: Path, stage: str) -> Path | None:
    c = sorted(out.glob(f"{stage}_*.pt"))
    return c[-1] if c else None


def save(out: Path, stage: str, state: dict, keep_every: int = 0) -> None:
    """Write a checkpoint and delete all but the newest KEEP_LAST, except steps that are a
    multiple of keep_every (> 0), which are kept for later evaluation."""
    p = out / f"{stage}_{state['step']:07d}.pt"
    torch.save(state, p.with_suffix(".tmp"))
    p.with_suffix(".tmp").replace(p)
    for old in sorted(out.glob(f"{stage}_*.pt"))[:-KEEP_LAST]:
        step = int(old.stem.split("_")[-1])
        if keep_every > 0 and step % keep_every == 0:
            continue
        old.unlink()


def log(out: Path, row: dict) -> None:
    with (out / "log.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


# ---------------- training ----------------

def train(cfg: StudentConfig, shards: Path, out: Path, stage: str, max_steps: int,
          batch_size: int = 16, lr: float = 2e-4, ckpt_every: int = 2000, log_every: int = 50,
          device: str = "cuda", init: Path | None = None,
          nan_steps: frozenset[int] = frozenset(), disc: str = "mpd", hf_weight: float = 0.0,
          hf_lo_hz: float = 4000.0, keep_every: int = 0) -> None:
    """stage: "front" | "dec" | "joint". `init` loads student weights from another stage.

    GAN stages: `disc` picks the discriminator set (see build_disc); `hf_weight` > 0 adds
    hf_stft_loss above `hf_lo_hz` with that weight. `keep_every` > 0 keeps every checkpoint
    whose step is a multiple of it (others: only the newest KEEP_LAST)."""
    assert stage in ("front", "dec", "joint")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dev = torch.device(device)
    use_amp = dev.type == "cuda"
    if dev.type == "cuda":
        # intermittent illegal-memory-access from cached cuFFT plans seen with two trainers
        # sharing one GPU (driver 620 / CUDA 13.2); plans are cheap to rebuild
        torch.backends.cuda.cufft_plan_cache.max_size = 0
    ds = DistillShards(shards)
    stats = None
    if cfg.prosody:
        import json

        stats = json.loads((Path(shards) / "prosody_stats.json").read_text())
    student = Student(cfg).to(dev)
    gan = stage in ("dec", "joint")
    disc_kind, disc = disc, None
    if gan:
        disc = build_disc(disc_kind).to(dev)
    params = (list(student.duration.parameters()) + list(student.acoustic.parameters())
              if stage == "front" else
              list(student.decoder.parameters()) + (list(student.acoustic.parameters()) if stage == "joint" else []))
    opt = torch.optim.AdamW(params, lr, betas=(0.8, 0.99), eps=1e-9)
    opt_d = torch.optim.AdamW(disc.parameters(), lr, betas=(0.8, 0.99), eps=1e-9) if gan else None
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    step = 0
    resume = latest(out, stage)
    if resume is not None:
        st = torch.load(resume, map_location=dev, weights_only=False)
        student.load_state_dict(st["student"])
        opt.load_state_dict(st["opt"])
        if gan:
            disc.load_state_dict(st["disc"])
            opt_d.load_state_dict(st["opt_d"])
        scaler.load_state_dict(st["scaler"])
        step = st["step"]
    elif init is not None:
        student.load_state_dict(torch.load(init, map_location=dev, weights_only=False)["student"])

    rnd = random.Random(1234 + step)
    t_last = time.time()
    student.train()
    while step < max_steps:
        step += 1
        items = [ds[rnd.randrange(len(ds))] for _ in range(batch_size)]
        row: dict = {"step": step}
        with torch.autocast(dev.type, enabled=use_amp):
            if stage == "front":
                b = {k: v.to(dev) for k, v in front_batch(items, cfg.latent, stats).items()}
                log_d = student.forward_duration(b["ids"])
                d_true = b["dur"].clamp(1, cfg.max_duration).float()
                n_tok = b["tok_mask"].sum()
                l_log = (((log_d.float() - torch.log(d_true)) ** 2) * b["tok_mask"]).sum() / n_tok
                # the log loss alone predicts the geometric mean (durations ~15% short, pauses
                # ~25% short); a linear term pulls the prediction to the arithmetic mean
                l_lin = (((torch.exp(log_d.float()) - d_true) ** 2) * b["tok_mask"]).sum() / n_tok
                l_dur = l_log + 0.05 * l_lin
                z_hat, p_hat = student.forward_latent_train(b["ids"], b["dur"], b.get("prosody"))
                z_hat = z_hat.float()
                m = b["frame_mask"][:, None]
                l_z = ((z_hat - b["z"]).abs() * m).sum() / (m.sum() * cfg.latent)
                cos = F.cosine_similarity(z_hat, b["z"], dim=1)
                l_cos = ((1 - cos) * b["frame_mask"]).sum() / b["frame_mask"].sum()
                loss = l_dur + l_z + l_cos
                if p_hat is not None and "prosody" in b:
                    mp = b["frame_mask"][:, None]
                    l_p = (((p_hat.float() - b["prosody"]) ** 2) * mp).sum() / (mp.sum() * 2)
                    loss = loss + l_p
                    row["l_prosody"] = l_p.item()
                row.update(loss=loss.item(), l_dur=l_dur.item(), l_z=l_z.item(), l_cos=l_cos.item())
            else:
                crops = [crop(it, rnd, cfg.hop) for it in items]
                y = torch.from_numpy(np.stack([c[2] for c in crops])).to(dev)[:, None]
                if stage == "dec":
                    z = torch.from_numpy(np.stack([c[1] for c in crops])).to(dev)
                else:
                    fb = {k: v.to(dev) for k, v in front_batch(items, cfg.latent, stats).items()}
                    z_full = student.forward_latent(fb["ids"], fb["dur"])
                    zs = [F.pad(z_full[k, :, c[0]: c[0] + SEG_FRAMES],
                                (0, SEG_FRAMES - z_full[k, :, c[0]: c[0] + SEG_FRAMES].shape[1]))
                          for k, c in enumerate(crops)]
                    z = torch.stack(zs)
                y_hat = student.decode(z)
        if stage == "front":
            if step in nan_steps:
                loss = loss * float("nan")
            ok = bool(torch.isfinite(loss))
            opt.zero_grad(set_to_none=True)
            if ok:
                scaler.scale(loss).backward()
                scaler.step(opt)
            scaler.update()
        else:
            y_hat = y_hat.float()
            with torch.autocast(dev.type, enabled=use_amp):
                d_r, d_g, _, _ = disc(y, y_hat.detach())
            l_d, _, _ = discriminator_loss([r.float() for r in d_r], [g.float() for g in d_g])
            ok = bool(torch.isfinite(l_d))
            opt_d.zero_grad(set_to_none=True)
            if ok:
                scaler.scale(l_d).backward()
                scaler.step(opt_d)
            with torch.autocast(dev.type, enabled=use_amp):
                _, d_g, f_r, f_g = disc(y, y_hat)
            l_adv, _ = generator_loss([g.float() for g in d_g])
            l_fm = feature_loss(f_r, f_g)
            l_mel = F.l1_loss(mel(y_hat[:, 0]), mel(y[:, 0])) * 45.0
            l_stft = mr_stft_loss(y_hat[:, 0], y[:, 0]) * 2.0
            loss = l_adv + l_fm + l_mel + l_stft
            if hf_weight > 0:
                l_hf = hf_stft_loss(y_hat[:, 0], y[:, 0], hf_lo_hz, cfg.sample_rate) * hf_weight
                loss = loss + l_hf
                row["l_hf"] = l_hf.item()
            if step in nan_steps:
                loss = loss * float("nan")
            ok = ok and bool(torch.isfinite(loss))
            opt.zero_grad(set_to_none=True)
            if ok:
                scaler.scale(loss).backward()
                scaler.step(opt)
            scaler.update()
            row.update(loss=loss.item(), l_d=l_d.item(), l_adv=l_adv.item(), l_fm=l_fm.item(),
                       l_mel=l_mel.item(), l_stft=l_stft.item())
        if not ok:
            log(out, {"step": step, "skipped_nan": True})
        elif step % log_every == 0:
            now = time.time()
            row["sec_per_step"] = (now - t_last) / log_every
            t_last = now
            log(out, row)
        if step % ckpt_every == 0 or step == max_steps:
            st = {"student": student.state_dict(), "opt": opt.state_dict(),
                  "scaler": scaler.state_dict(), "step": step, "stage": stage,
                  "config": cfg.__dict__, "disc": disc_kind,
                  "train_opts": {"hf_weight": hf_weight, "hf_lo_hz": hf_lo_hz, "lr": lr,
                                 "batch_size": batch_size}}
            if gan:
                st.update(disc=disc.state_dict(), opt_d=opt_d.state_dict())
            save(out, stage, st, keep_every)
