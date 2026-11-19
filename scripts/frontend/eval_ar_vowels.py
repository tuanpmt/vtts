"""Word-level vowel accuracy of the Arabic front-end against a fully vowelled reference.

Reference: the QCRI WikiNews test set (WikiNewsTruth.txt from github.com/kdarwish/Farasa,
"feel free to copy and distribute"; 70 Modern Standard Arabic news articles, about 17,000 words,
fully vowelled). It is used here only for measurement; nothing from it is in the repository.

  curl -LO https://raw.githubusercontent.com/kdarwish/Farasa/master/WikiNewsTruth.txt
  uv run python scripts/frontend/eval_ar_vowels.py WikiNewsTruth.txt [--half test] [--errors 40]

Each Arabic word of the reference is stripped of its marks and read by the front-end
(g2p_ar.vocalize + read_vocalized, pausal form); the reference word is read by the same
read_vocalized from its own marks (words of lexicons/ar/spelling.tsv, whose usual spelling hides
a long vowel, e.g. هذا = haadhaa, are read from that table on both sides). A word is right when
the two phoneme sequences are equal (stress is ignored; both are pausal, so case endings do not
count). Lines are split by parity:
"dev" (even lines) was used to look at errors while writing rules and lexicon entries, "test"
(odd lines) was not. Also reported: phoneme error rate (Levenshtein over phonemes / reference
phonemes), and accuracy split by source (lexicon, patterns, default reading).
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


def _edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def words_of(path: Path, half: str) -> list[str]:
    from vtts.frontend.ar.g2p_ar import is_arabic_word

    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    out: list[str] = []
    for k, line in enumerate(lines):
        if half != "all" and (k % 2 == 0) != (half == "dev"):
            continue
        for w in re.findall(r"[ء-ْٰٱ]+", line):
            if is_arabic_word(w):
                out.append(w)
    return out


def main() -> None:
    from vtts.frontend.ar import g2p_ar as g

    ap = argparse.ArgumentParser()
    ap.add_argument("ref", type=Path)
    ap.add_argument("--half", choices=("dev", "test", "all"), default="test")
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--no-lexicon", action="store_true")
    a = ap.parse_args()
    if a.no_lexicon:
        g.lexicon.cache_clear()
        g.lexicon = dict  # type: ignore[assignment]
    words = words_of(a.ref, a.half)
    right = edits = total = 0
    by_src: Counter = Counter()
    ok_src: Counter = Counter()
    errors: Counter = Counter()
    for w in words:
        ref = g.read_vocalized(g.vocalize(w))  # the reference's own marks (spelling table first)
        bare = g.strip_marks(w)
        src = "lexicon" if g.lexicon_vocalize(bare) else (
            "pattern" if g.pattern_vocalize(bare) != g.default_vocalize(bare) else "default")
        hyp = g.read_vocalized(g.vocalize(bare))
        by_src[src] += 1
        e = _edits(ref, hyp)
        edits += e
        total += len(ref)
        if e == 0:
            right += 1
            ok_src[src] += 1
        else:
            errors[(bare, " ".join(ref), " ".join(hyp))] += 1
    n = len(words)
    print(f"{a.half}: {n} words, word accuracy {100 * right / n:.1f}%, "
          f"phoneme error rate {100 * edits / max(total, 1):.1f}%")
    for src in ("lexicon", "pattern", "default"):
        if by_src[src]:
            print(f"  {src}: {by_src[src]} words ({100 * by_src[src] / n:.1f}%), "
                  f"accuracy {100 * ok_src[src] / by_src[src]:.1f}%")
    for (bare, ref, hyp), c in errors.most_common(a.errors):
        print(f"{c}\t{bare}\tref {ref}\thyp {hyp}")


if __name__ == "__main__":
    main()
