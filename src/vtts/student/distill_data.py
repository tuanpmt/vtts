"""Distillation targets from the teacher: durations, latent z, audio; stored in npz shards."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

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


def write_shard(path: Path, items: list[dict]) -> None:
    """Concatenate variable-length items with offset tables (one npz per shard)."""
    arrays = {}
    for key in ("ids", "dur", "audio"):
        arrays[key] = np.concatenate([it[key] for it in items])
        arrays[key + "_off"] = np.cumsum([0] + [len(it[key]) for it in items]).astype(np.int64)
    arrays["z"] = np.concatenate([it["z"] for it in items], axis=1)
    arrays["z_off"] = np.cumsum([0] + [it["z"].shape[1] for it in items]).astype(np.int64)
    np.savez(path, **arrays)


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
        for key in KEYS:
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


def _prosody_shard(shard_dir: Path) -> tuple[float, float, float, float, int, int]:
    """Write lf0/vuv/energy .npy for one mmap shard; return sums for the global stats."""
    from .prosody import frame_prosody

    d = {k: np.load(shard_dir / f"{k}.npy", mmap_mode="r") for k in KEYS}
    n_items = len(d["ids_off"]) - 1
    total = int(d["z_off"][-1])
    lf0 = np.zeros(total, np.float32)
    vuv = np.zeros(total, np.uint8)
    energy = np.zeros(total, np.float32)
    for i in range(n_items):
        a, b = int(d["z_off"][i]), int(d["z_off"][i + 1])
        audio = np.asarray(d["audio"][d["audio_off"][i]: d["audio_off"][i + 1]])
        f, v, e = frame_prosody(audio, b - a)
        lf0[a:b], vuv[a:b], energy[a:b] = f, v.astype(np.uint8), e
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
