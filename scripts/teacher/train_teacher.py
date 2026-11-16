"""Train the VITS teacher.

Usage (GPU box):
  uv run python scripts/teacher/train_teacher.py --data data/infore1/final --wavs data/infore1/prepared/wavs \
     --out artifacts/teacher/run1 --warmstart artifacts/warmstart/epoch=4769-step=919580.ckpt \
     --max-steps 100000 --ckpt-every 5000
"""

import argparse
from pathlib import Path

from vtts.teacher.config import TeacherConfig
from vtts.teacher.train import train


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="dir with train.csv")
    ap.add_argument("--wavs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--no-cache", action="store_true", help="compute spectrograms on the fly")
    ap.add_argument("--warmstart", type=Path, default=None)
    ap.add_argument("--max-steps", type=int, default=100_000)
    ap.add_argument("--ckpt-every", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    cfg = TeacherConfig(batch_size=args.batch_size)
    train(cfg, args.data / "train.csv", args.wavs, None if args.no_cache else (args.cache or args.data / "spec_cache"), args.out,
          args.warmstart, args.max_steps, args.ckpt_every, device=args.device,
          num_workers=args.num_workers)


if __name__ == "__main__":
    main()
