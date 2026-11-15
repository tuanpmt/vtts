"""Build a sentence corpus for distillation from Vietnamese Wikipedia (CC-BY-SA).

Keeps sentences of 6-40 syllables in which every word is a readable syllable,
number or known loanword (no letter spelling), plus the InfoRe1 train transcripts.

Usage: uv run python scripts/build_text_corpus.py --out data/corpus/sentences.txt --target 60000
"""

import argparse
import random
import re
from pathlib import Path

from vtts.frontend.normalize import normalize, spelled_words
from vtts.frontend.phoneme_set import PUNCTUATION

SPLIT = re.compile(r"(?<=[.!?])\s+")


def good(sentence: str) -> bool:
    if not 20 <= len(sentence) <= 220 or "(" in sentence or "=" in sentence:
        return False
    if spelled_words(sentence):
        return False
    n = sum(1 for w in normalize(sentence).split() if w not in PUNCTUATION)
    return 6 <= n <= 40


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target", type=int, default=60000)
    ap.add_argument("--infore", type=Path, default=Path("data/infore1/final/train.csv"))
    args = ap.parse_args()
    from datasets import load_dataset

    out: list[str] = []
    seen = set()
    ds = load_dataset("wikimedia/wikipedia", "20231101.vi", split="train", streaming=True)
    for art in ds:
        for para in art["text"].split("\n"):
            for s in SPLIT.split(para.strip()):
                s = s.strip()
                if s and s not in seen and good(s):
                    seen.add(s)
                    out.append(s)
        if len(out) >= args.target:
            break
    if args.infore.exists():
        out += [ln.split("|")[1] for ln in args.infore.read_text(encoding="utf-8").splitlines() if ln]
    random.Random(1234).shuffle(out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} sentences to {args.out}")


if __name__ == "__main__":
    main()
