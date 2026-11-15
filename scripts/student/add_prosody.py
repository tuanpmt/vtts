"""Add frame prosody targets (log-F0, voicing, energy) to an mmap distillation pack.

Usage: uv run python scripts/student/add_prosody.py --root data/distill95/mm --workers 8
"""

import argparse
import json
from pathlib import Path

from vtts.student.distill_data import add_prosody


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    print(json.dumps(add_prosody(a.root, a.workers)))


if __name__ == "__main__":
    main()
