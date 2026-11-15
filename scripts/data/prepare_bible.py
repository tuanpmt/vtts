"""Prepare VietBibleVox (open.bible Vietnamese audio Bible, CC BY-SA 4.0) into 22.05 kHz wavs + metadata.csv.

Usage: uv run --with remotezip python scripts/data/prepare_bible.py --out data/bible/prepared [--src URL_OR_ZIP] [--workers 8]
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from vtts.data.bible import prepare_bible

URL = "https://huggingface.co/datasets/ntt123/VietBibleVox/resolve/main/data.zip"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=URL)
    ap.add_argument("--out", type=Path, default=Path("data/bible/prepared"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    rep = prepare_bible(a.src, a.out, workers=a.workers, limit=a.limit)
    (a.out / "prepare_report.json").write_text(json.dumps(asdict(rep), ensure_ascii=False, indent=1))
    print(f"{rep.n_out}/{rep.n_in} clips, {rep.hours:.2f} h, skipped {len(rep.skipped)}")


if __name__ == "__main__":
    main()
