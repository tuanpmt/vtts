"""Generate distillation shards from a teacher checkpoint.

Usage: uv run python scripts/student/build_distill_pack.py --ckpt best.pt --sentences data/corpus/sentences.txt \
   --out data/distill/shards [--limit N] [--noise-scale 0.0] [--device cuda]
   [--batch-size 32] [--batch-tokens 4096] [--prosody-workers 8] [--amp none|fp16|bf16] [--per-item] [--verify N]
--sentences may be a .jsonl with {"text", "lang"} rows (bilingual, token set v2); see pack_inputs.
Resumable: existing shards are skipped.

Fast path (default): each 1000-item shard is rendered in length-sorted padded batches
(teacher_targets_batch: same per-item seeds and noise, masked decoder, so the items equal the
per-item path up to float summation order), and the frame prosody (lf0/vuv/energy, pyworld on
the CPU) is computed in a process pool while the GPU renders the next shard; the prosody goes
into the shard, so convert_shards.py carries it over and add_prosody.py only writes the stats.
--per-item: the original one-sentence-at-a-time path (reference). --verify N renders the first
N items both ways, prints the differences and exits (run it once on a new GPU type).
--amp fp16|bf16 runs the teacher's HiFi-GAN decoder under autocast: faster, durations and z
unchanged, audio about 60 dB (fp16) / 44 dB (bf16) SNR from the fp32 render; off by default.
TF32 is off unless --tf32: with it (the PyTorch default for cuDNN convolutions, so the
original pack builds) per-item and batched renders differ by float noise that flips a few
ceil'd durations (11-16 of 256 items by one frame on an RTX 5090); in fp32 the batched render
equals the per-item one (durations identical, z within one fp16 step, audio within 2 LSB).
"""

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch

from vtts.student.distill_data import (
    PROSODY_KEYS,
    items_prosody,
    pack_inputs,
    teacher_targets,
    teacher_targets_batch,
    write_shard,
)
from vtts.teacher.infer import Teacher

SHARD = 1000


def batches(lengths: list[int], batch_size: int, batch_tokens: int) -> list[list[int]]:
    """Indices sorted by length, cut into batches of at most batch_size items and at most
    batch_tokens padded tokens (bounds the decoder's activation memory on long sentences)."""
    out: list[list[int]] = []
    cur: list[int] = []
    for i in sorted(range(len(lengths)), key=lambda i: lengths[i]):
        if cur and (len(cur) >= batch_size or (len(cur) + 1) * lengths[i] > batch_tokens):
            out.append(cur)
            cur = []
        cur.append(i)
    return out + ([cur] if cur else [])


def render_batched(teacher: Teacher, seqs: list[list[int]], seed0: int, batch_size: int,
                   noise_scale: float, noise_w: float, amp: str, batch_tokens: int = 4096) -> list[dict]:
    """Items for seqs (seeds seed0 + i) in input order, rendered in length-sorted batches."""
    out: list[dict | None] = [None] * len(seqs)
    for idx in batches([len(s) for s in seqs], batch_size, batch_tokens):
        res = teacher_targets_batch(teacher, [seqs[i] for i in idx], [seed0 + i for i in idx],
                                    noise_scale, noise_w, amp)
        for i, r in zip(idx, res):
            out[i] = dict(r, ids=np.array(seqs[i], np.int32))
    return out  # type: ignore[return-value]


def render_per_item(teacher: Teacher, seqs: list[list[int]], seed0: int, noise_scale: float,
                    noise_w: float) -> list[dict]:
    return [dict(teacher_targets(teacher, ids, seed=seed0 + i, noise_scale=noise_scale, noise_w=noise_w),
                 ids=np.array(ids, np.int32)) for i, ids in enumerate(seqs)]


def verify(teacher: Teacher, seqs: list[list[int]], a) -> dict:
    ref = render_per_item(teacher, seqs, 0, a.noise_scale, a.noise_w)
    out = render_batched(teacher, seqs, 0, a.batch_size, a.noise_scale, a.noise_w, a.amp, a.batch_tokens)
    same = all(r[k].shape == o[k].shape and r[k].dtype == o[k].dtype for r, o in zip(ref, out) for k in r)
    rep = {"items": len(seqs), "same_shapes_dtypes": same,
           "dur_equal": sum(np.array_equal(r["dur"], o["dur"]) for r, o in zip(ref, out))}
    if same:
        zd = np.concatenate([np.abs(r["z"].astype(np.float32) - o["z"]).ravel() for r, o in zip(ref, out)])
        ad = np.concatenate([np.abs(r["audio"].astype(np.float32) - o["audio"]).ravel() / 32767
                             for r, o in zip(ref, out)])
        rep.update(z_max=float(zd.max()), z_mean=float(zd.mean()), audio_max=float(ad.max()),
                   audio_mean=float(ad.mean()))
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--noise-scale", type=float, default=0.333)
    ap.add_argument("--noise-w", type=float, default=0.8)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--batch-size", type=int, default=32, help="sentences per padded teacher pass")
    ap.add_argument("--batch-tokens", type=int, default=4096,
                    help="padded tokens per pass at most (memory bound; ~3.4 frames per token)")
    ap.add_argument("--per-item", action="store_true", help="original unbatched render (reference)")
    ap.add_argument("--amp", choices=("none", "fp16", "bf16"), default="none",
                    help="autocast for the teacher decoder only (not bit-close, see module doc)")
    ap.add_argument("--prosody-workers", type=int, default=8,
                    help="CPU processes computing frame prosody during the render (0: leave it to add_prosody.py)")
    ap.add_argument("--verify", type=int, default=0, metavar="N",
                    help="compare the batched and per-item render on the first N items, then exit")
    ap.add_argument("--tf32", action="store_true",
                    help="allow TF32 convolutions/matmuls on CUDA (off: fp32, so the batched render "
                         "matches the per-item one; TF32 flips some ceil'd durations either way)")
    a = ap.parse_args()
    torch.backends.cudnn.allow_tf32 = torch.backends.cuda.matmul.allow_tf32 = a.tf32
    # workers start before CUDA is initialised (spawn: no CUDA state is inherited)
    pool = (ProcessPoolExecutor(a.prosody_workers, mp_context=torch.multiprocessing.get_context("spawn"))
            if a.prosody_workers > 0 and not a.verify else None)
    teacher = Teacher.load(a.ckpt, a.device)
    seqs = pack_inputs(a.sentences, a.limit)
    if a.verify:
        print(json.dumps(verify(teacher, seqs[: a.verify], a)))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    pending = None  # (path, items, futures) of the shard whose prosody is still being computed

    def flush() -> None:
        path, items, futs = pending
        if futs is not None:
            pros = [p for f in futs for p in f.result()]
            for it, p in zip(items, pros):
                it.update(zip(PROSODY_KEYS, p))
        write_shard(path, items)
        print(f"{path.name}: {len(items)} items", flush=True)

    t0 = time.time()
    for s0 in range(0, len(seqs), SHARD):
        path = a.out / f"shard_{s0 // SHARD:05d}.npz"
        if path.exists():
            continue
        chunk = seqs[s0: s0 + SHARD]
        if a.per_item:
            items = render_per_item(teacher, chunk, s0, a.noise_scale, a.noise_w)
        else:
            items = render_batched(teacher, chunk, s0, a.batch_size, a.noise_scale, a.noise_w, a.amp,
                                   a.batch_tokens)
        futs = None
        if pool is not None:
            jobs = [(it["audio"], it["z"].shape[1]) for it in items]
            step = max(1, len(jobs) // (4 * a.prosody_workers))
            futs = [pool.submit(items_prosody, jobs[i: i + step]) for i in range(0, len(jobs), step)]
        if pending is not None:
            flush()
        pending = (path, items, futs)
    if pending is not None:
        flush()
    if pool is not None:
        pool.shutdown()
    print(f"pack done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
