"""Write the C front-end parity fixture: sentences the device front-end supports + expected ids.

Usage: uv run python scripts/frontend/export_text_parity.py --sentences FILE... --out runtime/test/text_parity.tsv
"""

import argparse
import re
from pathlib import Path

from vtts.frontend.text import text_to_ids

# not implemented on the device front-end (documented in runtime/README.md)
UNSUPPORTED = re.compile(
    r"@|https?://|www\.|\$|\d{4}-\d{2}-\d{2}|(?<!\d)0\d{2,3}[. ]?\d{3}[. ]?\d{3,4}"
    r"|\d\s?(?:đ|đồng|vnđ|vnd|usd|km|kg|cm|mm|ml|m|g|l|°)(?![^\W\d_])", re.IGNORECASE)


def supported(text: str) -> bool:
    return not UNSUPPORTED.search(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    lines = []
    for f in a.sentences:
        for t in f.read_text(encoding="utf-8").splitlines():
            t = t.strip().replace("\t", " ")
            if t and supported(t):
                chunks = text_to_ids(t)
                lines.append(t + "\t" + ";".join(" ".join(map(str, c)) for c in chunks))
    if a.limit:
        lines = lines[: a.limit]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} cases to {a.out}")


if __name__ == "__main__":
    main()
