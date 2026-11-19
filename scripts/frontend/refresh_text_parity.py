"""Recompute the expected ids of existing C front-end parity fixtures (mode<TAB>text<TAB>ids lines)
after a front-end change, keeping their texts, and optionally append sentences.

Usage: uv run python scripts/frontend/refresh_text_parity.py runtime/test/text_parity_pt.tsv ...
       uv run python scripts/frontend/refresh_text_parity.py --add eval/sets/ood_en.jsonl \
           runtime/test/text_parity_pt.tsv
--add appends each sentence of the JSONL files (field "text") that the fixture does not have yet,
in the fixture's mode (the mode of its first line; in the vi and auto modes only the texts the
device's Vietnamese normalizer supports, export_text_parity.supported). The texts of the export scripts
(export_text_parity*.py) need corpora that are not in the repository; this keeps their lines.
"""

import argparse
import json
import sys
from pathlib import Path

from vtts.frontend.text import text_to_ids

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_text_parity import supported


def ids_field(text: str, mode: str) -> str:
    return ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("fixtures", nargs="+", type=Path)
    ap.add_argument("--add", nargs="*", type=Path, default=[])
    a = ap.parse_args()
    extra = [json.loads(line)["text"] for p in a.add for line in p.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    for path in a.fixtures:
        # fgets splits at \n only: keep every other character of a text as it is
        lines = [ln for ln in path.read_bytes().decode("utf-8").split("\n") if ln]
        out, seen, changed = [], set(), 0
        for ln in lines:
            mode, text, old = ln.split("\t", 2)
            new = ids_field(text, mode)
            changed += new != old
            seen.add(text)
            out.append(f"{mode}\t{text}\t{new}")
        mode = lines[0].split("\t", 1)[0]
        added = 0
        for text in extra:
            text = " ".join(text.split())
            if text and text not in seen and (mode not in ("vi", "auto") or supported(text)):
                seen.add(text)
                out.append(f"{mode}\t{text}\t{ids_field(text, mode)}")
                added += 1
        path.write_bytes(("\n".join(out) + "\n").encode("utf-8"))
        print(f"{path}: {len(lines)} lines, {changed} changed, {added} added")


if __name__ == "__main__":
    main()
