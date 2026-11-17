"""Build the VLEX blob (English lexicon + letter-to-sound) for the device front-end.

Usage: uv run python scripts/frontend/build_lexicon.py --out lex_en.bin [--max-words N]
       [--expect runtime/test/lex_expect.tsv --n-words 5000 --n-lts 1000]
--expect writes a fixture for runtime/test/lex_test.c: lines "L<TAB>word<TAB>ids" for lexicon
lookups (ids empty when absent) and "P<TAB>word<TAB>ids" for letter-to-sound predictions.
"""

import argparse
import random
import string
from pathlib import Path

from vtts.frontend.en.cmudict import load_cmudict
from vtts.frontend.en.vlex import build_vlex, read_vlex


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-words", type=int, default=None)
    ap.add_argument("--expect", type=Path, default=None)
    ap.add_argument("--n-words", type=int, default=5000)
    ap.add_argument("--n-lts", type=int, default=1000)
    a = ap.parse_args()
    blob = build_vlex(a.max_words)
    a.out.write_bytes(blob)
    print(f"wrote {a.out} ({len(blob)} bytes)")
    if a.expect:
        v, rnd = read_vlex(blob), random.Random(0)
        lex = sorted(load_cmudict())
        lines = []
        for w in rnd.sample(lex, min(a.n_words, len(lex))):
            lines.append(f"L\t{w}\t{' '.join(map(str, v.lookup(w)))}")
        absent = ["".join(rnd.choice(string.ascii_lowercase) for _ in range(rnd.randint(3, 9))) for _ in range(200)]
        for w in absent:
            ids = v.lookup(w)
            lines.append(f"L\t{w}\t{' '.join(map(str, ids or []))}")
        for _ in range(a.n_lts):
            w = "".join(rnd.choice(string.ascii_lowercase) for _ in range(rnd.randint(1, 14)))
            lines.append(f"P\t{w}\t{' '.join(map(str, v.predict(w)))}")
        a.expect.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {a.expect} ({len(lines)} cases)")


if __name__ == "__main__":
    main()
