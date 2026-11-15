"""Generate distillation shards from a teacher checkpoint.

Usage: uv run python scripts/student/build_distill_pack.py --ckpt best.pt --sentences data/corpus/sentences.txt \
   --out data/distill/shards [--limit N] [--noise-scale 0.0] [--device cuda]
Resumable: existing shards are skipped.
"""

import argparse
from pathlib import Path

import numpy as np
import torch

from vtts.frontend.g2p import encode, g2p
from vtts.frontend.text import split_sentences
from vtts.student.distill_data import teacher_targets, write_shard
from vtts.teacher.infer import Teacher

SHARD = 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--noise-scale", type=float, default=0.333)
    ap.add_argument("--noise-w", type=float, default=0.8)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    teacher = Teacher.load(a.ckpt, a.device)
    texts = [t for t in a.sentences.read_text(encoding="utf-8").splitlines() if t.strip()]
    if a.limit:
        texts = texts[: a.limit]
    a.out.mkdir(parents=True, exist_ok=True)
    for s0 in range(0, len(texts), SHARD):
        path = a.out / f"shard_{s0 // SHARD:05d}.npz"
        if path.exists():
            continue
        items = []
        for i, text in enumerate(texts[s0: s0 + SHARD]):
            for chunk in split_sentences(text):
                ids = encode(g2p(chunk))
                t = teacher_targets(teacher, ids, seed=s0 + i, noise_scale=a.noise_scale, noise_w=a.noise_w)
                items.append(dict(t, ids=np.array(ids, np.int32)))
        write_shard(path, items)
        print(f"{path.name}: {len(items)} items", flush=True)


if __name__ == "__main__":
    main()
