"""Train a student stage.

Usage: uv run python scripts/student/train_student.py --preset S-vocos --shards data/distill/shards \
   --out artifacts/student/S-vocos --stage front --max-steps 30000 [--init FILE]
"""

import argparse
from pathlib import Path

from vtts.student.config import PRESETS
from vtts.student.train import train


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=sorted(PRESETS), required=True)
    ap.add_argument("--shards", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stage", choices=["front", "dec", "joint"], required=True)
    ap.add_argument("--max-steps", type=int, required=True)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--init", type=Path, default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--disc", choices=["mpd", "mpd+mrd"], default="mpd")
    a = ap.parse_args()
    train(PRESETS[a.preset], a.shards, a.out, a.stage, a.max_steps, a.batch_size, a.lr,
          device=a.device, init=a.init, disc=a.disc)


if __name__ == "__main__":
    main()
