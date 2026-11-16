"""Synthesize a sentence list with the VoxCPM2 voice service (resumable).

Usage: uv run python scripts/data/synth_voxcpm.py --sentences data/bilingual/sentences.jsonl \
       --out data/bilingual/synth --voice nam-1 [--workers 4 --per-minute 110]
Writes OUT/audio/<id>.flac (native 24 kHz) and appends one line per attempt batch to
OUT/manifest.jsonl. Re-running skips ids already marked ok.
"""

import argparse
import json
from pathlib import Path

from vtts.data.voxcpm_client import DEFAULT_ENV, run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voice", default="nam-1")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--per-minute", type=int, default=110)
    ap.add_argument("--env", type=Path, default=DEFAULT_ENV)
    a = ap.parse_args()
    items = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines() if x.strip()]
    print(run(items, a.out, a.voice, a.workers, a.per_minute, a.env), flush=True)


if __name__ == "__main__":
    main()
