"""Distillation targets from the teacher: durations, latent z, audio; stored in npz shards."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from vtts.teacher.infer import Teacher


def pack_inputs(path: Path, limit: int | None, seed: int = 0) -> list[list[int]]:
    """Id sequences to distill, one per chunk.

    A .jsonl file has one {"text", "lang"} object per line (bilingual corpus): token set v2,
    with "mixed" read in "vi" mode as in teacher training, and lang zh / ko / ja in their pair
    token set (zh-en, ko-en, ja-en; English rows use the shared ids); with a limit, a seeded random sample
    of whole sentences keeps the language mix. Any other file is plain text, one sentence per
    line, encoded with token set v1 (the first `limit` lines).
    """
    path = Path(path)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if path.suffix != ".jsonl":
        from vtts.frontend.g2p import encode, g2p
        from vtts.frontend.text import split_sentences

        return [encode(g2p(c)) for text in lines[:limit] for c in split_sentences(text)]
    import json
    import random

    from vtts.frontend.text import text_to_ids

    rows = [json.loads(ln) for ln in lines]
    if limit is not None and limit < len(rows):
        rows = random.Random(seed).sample(rows, limit)
    # pair languages (PAIR_MODES: zh, ko, ja ...) use their pair token set; "mixed" (vi-en) is read in "vi" mode
    return [ids for r in rows for ids in text_to_ids(r["text"], _mode(r.get("lang")))]


def _mode(lang: str | None) -> str:
    from vtts.frontend.phoneme_set import PAIR_MODES

    return lang if lang == "en" or lang in PAIR_MODES else "vi"


@torch.inference_mode()
def teacher_targets(teacher: Teacher, ids: list[int], seed: int, noise_scale: float,
                    noise_w: float) -> dict:
    torch.manual_seed(seed)
    g, dev = teacher.g, teacher.device
    x = torch.tensor([ids], dtype=torch.long, device=dev)
    o, attn, _y_mask, (z, _z_p, _m_p, _logs_p) = g.infer(
        x, torch.tensor([len(ids)], device=dev), noise_scale=noise_scale,
        length_scale=teacher.cfg.length_scale, noise_scale_w=noise_w)
    dur = attn[0, 0].sum(0).round().long().cpu().numpy().astype(np.int32)
    audio = o[0, 0].float().cpu().numpy()
    return {"dur": dur, "z": z[0].float().cpu().numpy().astype(np.float16),
            "audio": (np.clip(audio, -1, 1) * 32767).astype(np.int16)}


def _sdp_reverse(dp, x: torch.Tensor, x_mask: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
    """StochasticDurationPredictor.forward(reverse=True) with the noise given (already scaled)
    instead of drawn from the global generator."""
    h = dp.proj(dp.convs(dp.pre(torch.detach(x)), x_mask)) * x_mask
    flows = list(reversed(dp.flows))
    flows = flows[:-2] + [flows[-1]]  # as in VITS: drop the unused vflow
    z = noise
    for flow in flows:
        z = flow(z, x_mask, g=h, reverse=True)
    return z[:, :1]


def _masked_decode(dec, z: torch.Tensor, y_mask: torch.Tensor) -> torch.Tensor:
    """HiFi-GAN Generator.forward on a padded batch with every conv input masked: each item's
    valid samples equal an unbatched decode (where convolutions see zero padding past the end),
    instead of picking up conv biases from the padded tail."""
    x = dec.conv_pre(z * y_mask) * y_mask
    mask = y_mask
    for i, up in enumerate(dec.ups):
        x = up(F.leaky_relu(x, dec.LRELU_SLOPE))
        mask = mask.repeat_interleave(up.stride[0], dim=-1)
        assert x.shape[-1] == mask.shape[-1], (x.shape, mask.shape)
        x = x * mask
        xs = None
        for j in range(dec.num_kernels):
            r = dec.resblocks[i * dec.num_kernels + j](x, mask)
            xs = r if xs is None else xs + r
        x = xs / dec.num_kernels
    x = dec.conv_post(F.leaky_relu(x) * mask)
    return torch.tanh(x)


@torch.inference_mode()
def teacher_targets_batch(teacher: Teacher, batch: list[list[int]], seeds: list[int],
                          noise_scale: float, noise_w: float, amp: str = "none") -> list[dict]:
    """teacher_targets for several sequences in one padded forward pass.

    Each item gets the noise teacher_targets(seed=seeds[k]) would draw (same generators, same
    draw order), all masks are honoured (also inside the decoder, see _masked_decode), so the
    results equal the per-item path up to float summation order. amp "bf16" | "fp16" runs the
    HiFi-GAN decoder under autocast (durations and z stay fp32; audio not bit-close, see
    build_distill_pack.py --amp)."""
    from vtts.teacher.vits import commons

    g, dev = teacher.g, torch.device(teacher.device)
    b = len(batch)
    n = max(len(ids) for ids in batch)
    x = torch.zeros(b, n, dtype=torch.long)
    for k, ids in enumerate(batch):
        x[k, : len(ids)] = torch.tensor(ids)
    x_len = torch.tensor([len(ids) for ids in batch])
    x, x_len = x.to(dev), x_len.to(dev)
    # per-item generators: the SDP noise is drawn on the CPU (torch.randn(...).type_as(x)), the
    # prior noise on the model device; on a CPU model both come from the one CPU generator
    cpu_gens = [torch.Generator().manual_seed(s) for s in seeds]
    dev_gens = cpu_gens if dev.type == "cpu" else [torch.Generator(dev).manual_seed(s) for s in seeds]
    h, m_p, logs_p, x_mask = g.enc_p(x, x_len)
    if g.use_sdp:
        e = torch.zeros(b, 2, n)
        for k, ids in enumerate(batch):
            e[k, :, : len(ids)] = torch.randn(1, 2, len(ids), generator=cpu_gens[k])[0]
        logw = _sdp_reverse(g.dp, h, x_mask, e.to(dev, h.dtype) * noise_w)
    else:
        logw = g.dp(h, x_mask)
    w = torch.exp(logw) * x_mask * teacher.cfg.length_scale
    w_ceil = torch.ceil(w)
    y_len = torch.clamp_min(torch.sum(w_ceil, [1, 2]), 1).long()
    y_mask = torch.unsqueeze(commons.sequence_mask(y_len, y_len.max()), 1).type_as(x_mask)
    attn = commons.generate_path(w_ceil, torch.unsqueeze(x_mask, 2) * torch.unsqueeze(y_mask, -1))
    m_p = torch.matmul(attn.squeeze(1), m_p.transpose(1, 2)).transpose(1, 2)
    logs_p = torch.matmul(attn.squeeze(1), logs_p.transpose(1, 2)).transpose(1, 2)
    y_len_cpu = y_len.cpu().tolist()
    # randn_like(m_p) in VITS fills a tensor with m_p's transposed [b, t, d] layout (the CPU
    # sampler's order depends on it): draw each item into the same layout
    eps = torch.zeros_like(m_p)
    for k, t in enumerate(y_len_cpu):
        e_k = torch.empty(1, t, m_p.shape[1], device=dev, dtype=m_p.dtype).transpose(1, 2)
        eps[k, :, :t] = e_k.normal_(generator=dev_gens[k])[0]
    z_p = m_p + eps * torch.exp(logs_p) * noise_scale
    z = g.flow(z_p, y_mask, reverse=True)
    # durations and latents stay fp32; amp (opt-in) only covers the HiFi-GAN decoder
    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}.get(amp)
    with torch.autocast(dev.type, dtype=dtype or torch.float32, enabled=dtype is not None):
        o = _masked_decode(g.dec, z, y_mask)
    hop = o.shape[-1] // z.shape[-1]
    dur = attn[:, 0].sum(1).round().long().cpu().numpy().astype(np.int32)
    z16 = z.float().cpu().numpy().astype(np.float16)
    audio = (np.clip(o[:, 0].float().cpu().numpy(), -1, 1) * 32767).astype(np.int16)
    return [{"dur": dur[k, : len(ids)], "z": z16[k, :, : y_len_cpu[k]],
             "audio": audio[k, : y_len_cpu[k] * hop]} for k, ids in enumerate(batch)]


def write_shard(path: Path, items: list[dict]) -> None:
    """Concatenate variable-length items with offset tables (one npz per shard). Items may carry
    frame prosody (lf0, vuv, energy: one value per z frame), stored on the z offsets."""
    arrays = {}
    for key in ("ids", "dur", "audio"):
        arrays[key] = np.concatenate([it[key] for it in items])
        arrays[key + "_off"] = np.cumsum([0] + [len(it[key]) for it in items]).astype(np.int64)
    arrays["z"] = np.concatenate([it["z"] for it in items], axis=1)
    arrays["z_off"] = np.cumsum([0] + [it["z"].shape[1] for it in items]).astype(np.int64)
    if all(k in it for it in items for k in PROSODY_KEYS):
        for k in PROSODY_KEYS:
            arrays[k] = np.concatenate([it[k] for it in items])
    tmp = Path(path).with_suffix(".tmp")
    with open(tmp, "wb") as f:  # a killed writer leaves no half shard that a resume would skip
        np.savez(f, **arrays)
    tmp.replace(path)


KEYS = ("ids", "ids_off", "dur", "dur_off", "audio", "audio_off", "z", "z_off")


def convert_to_mmap(src: Path, dst: Path) -> None:
    """npz shards -> one directory of .npy files per shard, readable with mmap (random access
    without loading whole shards)."""
    for p in sorted(Path(src).glob("shard_*.npz")):
        out = Path(dst) / p.stem
        if (out / "z_off.npy").exists():
            continue
        out.mkdir(parents=True, exist_ok=True)
        d = np.load(p)
        # prosody computed while rendering (build_distill_pack.py) travels with the shard
        for key in KEYS + tuple(k for k in PROSODY_KEYS if k in d.files):
            np.save(out / f"{key}.npy", d[key])


class DistillShards:
    """Random access over all shards in a directory: mmap'd .npy shard directories when
    present (fast), else npz files loaded lazily and cached per shard."""

    def __init__(self, root: Path):
        self.dirs = sorted(d for d in Path(root).glob("shard_*") if d.is_dir())
        self.paths = [] if self.dirs else sorted(Path(root).glob("shard_*.npz"))
        self._mm = [{k: np.load(d / f"{k}.npy", mmap_mode="r")
                     for k in KEYS + tuple(p for p in ("lf0", "vuv", "energy") if (d / f"{p}.npy").exists())}
                    for d in self.dirs]
        self.index: list[tuple[int, int]] = []
        if self.dirs:
            for s, m in enumerate(self._mm):
                self.index += [(s, i) for i in range(len(m["ids_off"]) - 1)]
        for s, p in enumerate(self.paths):
            n = len(np.load(p)["ids_off"]) - 1
            self.index += [(s, i) for i in range(n)]
        self._cache: dict[int, dict] = {}

    def __len__(self) -> int:
        return len(self.index)

    def _shard(self, s: int) -> dict:
        if self.dirs:
            return self._mm[s]
        if s not in self._cache:
            if len(self._cache) > 8:
                self._cache.pop(next(iter(self._cache)))
            self._cache[s] = dict(np.load(self.paths[s]))
        return self._cache[s]

    def __getitem__(self, k: int) -> dict:
        s, i = self.index[k]
        d = self._shard(s)
        out = {}
        for key in ("ids", "dur", "audio"):
            a, b = d[key + "_off"][i], d[key + "_off"][i + 1]
            out[key] = d[key][a:b]
        a, b = d["z_off"][i], d["z_off"][i + 1]
        out["z"] = d["z"][:, a:b]
        for key in ("lf0", "vuv", "energy"):
            if key in d:
                out[key] = d[key][a:b]
        return out


PROSODY_KEYS = ("lf0", "vuv", "energy")


def item_prosody(audio: np.ndarray, n_frames: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Frame prosody of one item in its stored dtypes: lf0 float32, vuv uint8, energy float32."""
    from .prosody import frame_prosody

    f, v, e = frame_prosody(np.asarray(audio), n_frames)
    return f.astype(np.float32), v.astype(np.uint8), e.astype(np.float32)


def items_prosody(jobs: list[tuple[np.ndarray, int]]) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """item_prosody over (audio, n_frames) pairs; one process-pool task."""
    return [item_prosody(a, n) for a, n in jobs]


def _prosody_shard(shard_dir: Path) -> tuple[float, float, float, float, int, int]:
    """Write lf0/vuv/energy .npy for one mmap shard (kept when the pack builder already wrote
    them); return sums for the global stats."""
    d = {k: np.load(shard_dir / f"{k}.npy", mmap_mode="r") for k in KEYS}
    total = int(d["z_off"][-1])
    if all((shard_dir / f"{k}.npy").exists() for k in PROSODY_KEYS):
        lf0, vuv, energy = (np.load(shard_dir / f"{k}.npy") for k in PROSODY_KEYS)
        assert len(lf0) == len(vuv) == len(energy) == total, shard_dir
    else:
        n_items = len(d["ids_off"]) - 1
        lf0 = np.zeros(total, np.float32)
        vuv = np.zeros(total, np.uint8)
        energy = np.zeros(total, np.float32)
        for i in range(n_items):
            a, b = int(d["z_off"][i]), int(d["z_off"][i + 1])
            audio = d["audio"][d["audio_off"][i]: d["audio_off"][i + 1]]
            lf0[a:b], vuv[a:b], energy[a:b] = item_prosody(audio, b - a)
        np.save(shard_dir / "lf0.npy", lf0)
        np.save(shard_dir / "vuv.npy", vuv)
        np.save(shard_dir / "energy.npy", energy)
    sel = vuv > 0
    return (float(lf0[sel].sum()), float((lf0[sel] ** 2).sum()), float(energy.sum()),
            float((energy ** 2).sum()), int(sel.sum()), total)


def add_prosody(root: Path, workers: int = 8) -> dict:
    """Add frame prosody targets to every mmap shard under root and write prosody_stats.json."""
    import json
    from concurrent.futures import ProcessPoolExecutor

    dirs = sorted(d for d in Path(root).glob("shard_*") if d.is_dir())
    if workers > 1:
        with ProcessPoolExecutor(workers) as pool:
            parts = list(pool.map(_prosody_shard, dirs))
    else:
        parts = [_prosody_shard(d) for d in dirs]
    s1, s2, e1, e2, nv, nt = (sum(p[k] for p in parts) for k in range(6))
    lf0_mean = s1 / max(nv, 1)
    stats = {"lf0_mean": lf0_mean, "lf0_std": max((s2 / max(nv, 1) - lf0_mean ** 2) ** 0.5, 1e-3),
             "energy_mean": e1 / max(nt, 1),
             "energy_std": max((e2 / max(nt, 1) - (e1 / max(nt, 1)) ** 2) ** 0.5, 1e-3)}
    (Path(root) / "prosody_stats.json").write_text(json.dumps(stats))
    return stats
