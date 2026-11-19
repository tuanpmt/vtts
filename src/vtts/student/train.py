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
from vtts.teacher.vits.losses import feature_loss, generator_loss
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

# ---------------- training ----------------

AMP_MODES = ("auto", "off", "fp16", "bf16")


def amp_dtype(amp: str, dev: torch.device) -> torch.dtype | None:
    """auto: fp16 (with a GradScaler) on CUDA, fp32 elsewhere: the recipe the released
    students were trained with."""
    if amp not in AMP_MODES:
        raise ValueError(f"unknown amp mode {amp!r}; choose from {AMP_MODES}")
    if amp == "auto":
        return torch.float16 if dev.type == "cuda" else None
    return {"off": None, "fp16": torch.float16, "bf16": torch.bfloat16}[amp]


def disc_loss(d_r: list[torch.Tensor], d_g: list[torch.Tensor]) -> torch.Tensor:
    """LSGAN discriminator loss (vits.losses.discriminator_loss without its per-term .item()
    host syncs)."""
    loss = 0.0
    for r, g in zip(d_r, d_g):
        loss = loss + torch.mean((1 - r.float()) ** 2) + torch.mean(g.float() ** 2)
    return loss


def make_batch(ds: DistillShards, rnd: random.Random, stage: str, cfg: StudentConfig,
               batch_size: int, stats: dict | None) -> dict:
    """CPU tensors for one step; draws from rnd exactly as the training loop always has
    (item choice, then the crop starts of the GAN stages)."""
    items = [ds[rnd.randrange(len(ds))] for _ in range(batch_size)]
    if stage == "front":
        return front_batch(items, cfg.latent, stats)
    crops = [crop(it, rnd, cfg.hop) for it in items]
    b = {"y": torch.from_numpy(np.stack([c[2] for c in crops]))[:, None]}
    if stage == "dec":
        b["z"] = torch.from_numpy(np.stack([c[1] for c in crops]))
    else:  # joint: the latent comes from the acoustic model on the whole sentence
        n = max(len(it["ids"]) for it in items)
        b["ids"] = torch.zeros(len(items), n, dtype=torch.long)
        b["dur"] = torch.zeros(len(items), n, dtype=torch.long)
        for k, it in enumerate(items):
            b["ids"][k, : len(it["ids"])] = torch.from_numpy(it["ids"].astype(np.int64))
            b["dur"][k, : len(it["dur"])] = torch.from_numpy(it["dur"].astype(np.int64))
        b["start"] = torch.tensor([c[0] for c in crops], dtype=torch.long)
    return b


def batch_stream(make, n: int, prefetch: int, pin: bool):
    """Yield n batches from make(); with prefetch > 0 a background thread builds (and pins)
    them ahead of the GPU, in the same order."""
    import queue
    import threading

    def ready(b: dict) -> dict:
        return {k: v.pin_memory() for k, v in b.items()} if pin else b

    if prefetch <= 0:
        for _ in range(n):
            yield ready(make())
        return
    q: queue.Queue = queue.Queue(prefetch)
    stop = threading.Event()

    def work() -> None:
        try:
            for _ in range(n):
                if stop.is_set():
                    return
                q.put(ready(make()))
        except Exception as e:  # noqa: BLE001 - re-raised in the training thread
            q.put(e)

    th = threading.Thread(target=work, daemon=True)
    th.start()
    try:
        for _ in range(n):
            b = q.get()
            if isinstance(b, Exception):
                raise b
            yield b
    finally:
        stop.set()
        while th.is_alive():
            try:
                q.get_nowait()
            except queue.Empty:
                th.join(0.05)


def _fuse_optimizer_state(opt: torch.optim.Optimizer, dev: torch.device) -> None:
    """A checkpoint written by a non-fused AdamW restores fused=False and CPU step counters:
    switch the groups back to the fused kernel and move the counters to the device."""
    for g in opt.param_groups:
        g["fused"], g["foreach"] = True, None
        for p in g["params"]:
            s = opt.state.get(p)
            if s and torch.is_tensor(s.get("step")):
                s["step"] = s["step"].to(dev, torch.float32)


def train(cfg: StudentConfig, shards: Path, out: Path, stage: str, max_steps: int,
          batch_size: int = 16, lr: float = 2e-4, ckpt_every: int = 2000, log_every: int = 50,
          device: str = "cuda", init: Path | None = None,
          nan_steps: frozenset[int] = frozenset(), disc: str = "mpd", hf_weight: float = 0.0,
          hf_lo_hz: float = 4000.0, keep_every: int = 0, amp: str = "auto", fast: bool = False,
          compile: bool = False, prefetch: int = 0, init_decoder: Path | None = None) -> None:
    """stage: "front" | "dec" | "joint". `init` loads student weights from another stage;
    `init_decoder` then replaces the decoder weights with those of another student
    checkpoint (warm decoder, experiment E6). Both only apply to a fresh run (no checkpoint
    of this stage in `out` yet).

    GAN stages: `disc` picks the discriminator set (see build_disc); `hf_weight` > 0 adds
    hf_stft_loss above `hf_lo_hz` with that weight. `keep_every` > 0 keeps every checkpoint
    whose step is a multiple of it (others: only the newest KEEP_LAST).

    Speed: `amp` (see amp_dtype; "auto" keeps the original fp16-on-CUDA recipe). `fast` uses
    a fused AdamW and skips non-finite steps without a host sync (the skip flag goes into the
    fused optimizer step / the GradScaler), so the CPU runs ahead of the GPU, and turns on
    cuDNN autotuning for the GAN stages; `prefetch` > 0 builds that many batches ahead in a
    background thread (same random stream). The updates equal the plain step up to float
    summation order. `compile` wraps the decoder and the discriminators in torch.compile."""
    assert stage in ("front", "dec", "joint")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dev = torch.device(device)
    dtype = amp_dtype(amp, dev)
    use_amp = dtype is not None
    if dev.type == "cuda":
        # intermittent illegal-memory-access from cached cuFFT plans seen with two trainers
        # sharing one GPU (driver 620 / CUDA 13.2); plans are cheap to rebuild
        torch.backends.cuda.cufft_plan_cache.max_size = 0
        if fast and stage != "front":
            torch.backends.cudnn.benchmark = True  # fixed crop shapes in the GAN stages
    ds = DistillShards(shards)
    stats = None
    if cfg.prosody:
        stats = json.loads((Path(shards) / "prosody_stats.json").read_text())
    student = Student(cfg).to(dev)
    gan = stage in ("dec", "joint")
    disc_kind, disc = disc, None
    if gan:
        disc = build_disc(disc_kind).to(dev)
    params = (list(student.duration.parameters()) + list(student.acoustic.parameters())
              if stage == "front" else
              list(student.decoder.parameters()) + (list(student.acoustic.parameters()) if stage == "joint" else []))
    fused = True if fast else None
    opt = torch.optim.AdamW(params, lr, betas=(0.8, 0.99), eps=1e-9, fused=fused)
    opt_d = torch.optim.AdamW(disc.parameters(), lr, betas=(0.8, 0.99), eps=1e-9, fused=fused) if gan else None
    scaler = torch.amp.GradScaler(dev.type, enabled=dtype == torch.float16)
    step = 0
    resume = latest(out, stage)
    if resume is not None:
        st = torch.load(resume, map_location=dev, weights_only=False)
        student.load_state_dict(st["student"])
        opt.load_state_dict(st["opt"])
        if gan:
            disc.load_state_dict(st["disc"])
            opt_d.load_state_dict(st["opt_d"])
        if st.get("scaler"):
            scaler.load_state_dict(st["scaler"])
        step = st["step"]
        if fast:
            for o in (opt, opt_d) if gan else (opt,):
                _fuse_optimizer_state(o, dev)
    else:
        if init is not None:
            student.load_state_dict(torch.load(init, map_location=dev, weights_only=False)["student"])
        if init_decoder is not None:
            src = torch.load(init_decoder, map_location=dev, weights_only=False)["student"]
            student.decoder.load_state_dict({k[len("decoder."):]: v for k, v in src.items()
                                             if k.startswith("decoder.")})
    if compile:
        student.decoder.compile()
        if gan:
            disc.compile()

    rnd = random.Random(1234 + step)
    stream = batch_stream(lambda: make_batch(ds, rnd, stage, cfg, batch_size, stats),
                          max(max_steps - step, 0), prefetch, pin=dev.type == "cuda")
    nan = torch.tensor(float("nan"), device=dev)
    one = torch.tensor(1.0, device=dev)
    skipped = torch.zeros((), dtype=torch.long, device=dev)  # fast: non-finite steps since the last row

    def update(o: torch.optim.Optimizer, loss: torch.Tensor, bad: torch.Tensor) -> None:
        """fast path: backward + step that leaves the parameters and the optimizer state
        untouched when `bad` (a device bool) is set, without reading it on the host."""
        o.zero_grad(set_to_none=True)
        # a skipped step still runs backward; NaN gradients make the GradScaler skip too
        scaler.scale(loss * torch.where(bad, nan, one)).backward()
        if scaler.is_enabled():
            scaler.step(o)
        else:
            o.found_inf = bad.float()  # read by the fused AdamW kernel (as with a GradScaler)
            o.step()
            del o.found_inf

    def plain_update(o: torch.optim.Optimizer, loss: torch.Tensor, ok: bool) -> None:
        o.zero_grad(set_to_none=True)
        if ok:
            scaler.scale(loss).backward()
            scaler.step(o)

    t_last = time.time()
    student.train()
    for cpu_b in stream:
        step += 1
        b = {k: v.to(dev, non_blocking=True) for k, v in cpu_b.items()}
        terms: dict[str, torch.Tensor] = {}
        ok = True
        with torch.autocast(dev.type, dtype=dtype or torch.float32, enabled=use_amp):
            if stage == "front":
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
                    terms["l_prosody"] = l_p
                terms.update(loss=loss, l_dur=l_dur, l_z=l_z, l_cos=l_cos)
            else:
                y = b["y"]
                if stage == "dec":
                    z = b["z"]
                else:
                    z_full = student.forward_latent(b["ids"], b["dur"])
                    # SEG_FRAMES-frame windows at the crop starts, zero past the end
                    zp = F.pad(z_full, (0, SEG_FRAMES))
                    idx = b["start"][:, None] + torch.arange(SEG_FRAMES, device=dev)
                    z = torch.gather(zp, 2, idx[:, None].expand(-1, zp.shape[1], -1))
                y_hat = student.decode(z)
        if stage == "front":
            if fast:
                bad = ~torch.isfinite(loss) | (step in nan_steps)
                update(opt, loss, bad)
                skipped += bad
            else:
                if step in nan_steps:
                    loss = loss * float("nan")
                ok = bool(torch.isfinite(loss))
                plain_update(opt, loss, ok)
            scaler.update()
        else:
            y_hat = y_hat.float()
            with torch.autocast(dev.type, dtype=dtype or torch.float32, enabled=use_amp):
                d_r, d_g, _, _ = disc(y, y_hat.detach())
            l_d = disc_loss(d_r, d_g)
            if fast:
                bad_d = ~torch.isfinite(l_d)
                update(opt_d, l_d, bad_d)
            else:
                ok = bool(torch.isfinite(l_d))
                plain_update(opt_d, l_d, ok)
            # generator pass: the discriminator's weight gradients were never used
            disc.requires_grad_(False)
            with torch.autocast(dev.type, dtype=dtype or torch.float32, enabled=use_amp):
                _, d_g, f_r, f_g = disc(y, y_hat)
            l_adv, _ = generator_loss([g.float() for g in d_g])
            l_fm = feature_loss(f_r, f_g)
            l_mel = F.l1_loss(mel(y_hat[:, 0]), mel(y[:, 0])) * 45.0
            l_stft = mr_stft_loss(y_hat[:, 0], y[:, 0]) * 2.0
            loss = l_adv + l_fm + l_mel + l_stft
            if hf_weight > 0:
                l_hf = hf_stft_loss(y_hat[:, 0], y[:, 0], hf_lo_hz, cfg.sample_rate) * hf_weight
                loss = loss + l_hf
                terms["l_hf"] = l_hf
            if fast:
                bad = bad_d | ~torch.isfinite(loss) | (step in nan_steps)
                update(opt, loss, bad)
                skipped += bad
            else:
                if step in nan_steps:
                    loss = loss * float("nan")
                ok = ok and bool(torch.isfinite(loss))
                plain_update(opt, loss, ok)
            disc.requires_grad_(True)
            scaler.update()
            terms.update(loss=loss, l_d=l_d, l_adv=l_adv, l_fm=l_fm, l_mel=l_mel, l_stft=l_stft)
        if not ok:
            log(out, {"step": step, "skipped_nan": True})
        elif step % log_every == 0:
            # the only host reads of the step, every log_every steps
            if fast and int(skipped):
                log(out, {"step": step, "skipped_nan": int(skipped)})
                skipped.zero_()
            row = {"step": step, **{k: float(v.detach()) for k, v in terms.items()}}
            now = time.time()
            row["sec_per_step"] = (now - t_last) / log_every
            t_last = now
            log(out, row)
        if step % ckpt_every == 0 or step == max_steps:
            st = {"student": student.state_dict(), "opt": opt.state_dict(),
                  "scaler": scaler.state_dict(), "step": step, "stage": stage,
                  "config": cfg.__dict__, "disc": disc_kind,
                  "train_opts": {"hf_weight": hf_weight, "hf_lo_hz": hf_lo_hz, "lr": lr,
                                 "batch_size": batch_size, "amp": amp}}
            if gan:
                st.update(disc=disc.state_dict(), opt_d=opt_d.state_dict())
            save(out, stage, st, keep_every)
