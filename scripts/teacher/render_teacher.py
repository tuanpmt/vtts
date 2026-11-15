"""Render a sentence set with a teacher checkpoint.

Usage: uv run python scripts/teacher/render_teacher.py --ckpt CKPT --set eval/sets/ood.jsonl --out DIR
"""

import argparse
import json
from pathlib import Path

import soundfile as sf
import torch

from vtts.teacher.infer import Teacher


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    teacher = Teacher.load(args.ckpt, args.device)
    args.out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in args.set.read_text(encoding="utf-8").splitlines() if x]
    for r in rows:
        sf.write(args.out / f"{r['id']}.wav", teacher.synthesize(r["text"]), teacher.cfg.sample_rate)
    print(f"rendered {len(rows)} clips to {args.out}")


if __name__ == "__main__":
    main()
