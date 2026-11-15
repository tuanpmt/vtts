"""Write the front-end golden fixture used to check the C port for exact parity.

Usage: uv run python scripts/frontend/export_frontend_golden.py --sentences FILE --out FILE.jsonl
"""

import argparse
import json
from pathlib import Path

from vtts.frontend.g2p import g2p
from vtts.frontend.normalize import normalize
from vtts.frontend.phoneme_set import PHONEME_SET_VERSION
from vtts.frontend.text import split_sentences, text_to_ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    lines = [ln.strip() for ln in args.sentences.read_text(encoding="utf-8").splitlines()]
    with args.out.open("w", encoding="utf-8") as f:
        for text in filter(None, lines):
            chunks = split_sentences(text)
            row = {
                "text": text,
                "normalized": [normalize(c) for c in chunks],
                "tokens": [g2p(normalize(c)) for c in chunks],
                "ids": text_to_ids(text),
                "phoneme_set_version": PHONEME_SET_VERSION,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
