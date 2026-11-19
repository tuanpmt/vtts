"""Sanity checks of the Lao G2P (there is no Lao voice in eSpeak NG and no open Lao lexicon with
phonemic transcriptions; these are measuring sticks only, nothing is shipped).

Usage: uv run python scripts/frontend/eval_lo_g2p.py --sentences data/lo/sentences.jsonl \
       [--dict lao-eng-dictionary.csv] [--n 2000] [--sample 40]

1. Syllable structure on the odd rows of the first --n corpus rows: share of Lao letters read
   inside a syllable (not skipped), share of syllables with a written vowel (unwritten o/a are rare
   in modern spelling), share of characters covered by the word list.
2. The romanization column of the E-Government Center's Lao-English dictionary (MIT): for entries
   of Lao letters whose romanization is one piece per syllable, whether the syllable count agrees,
   and for those, the initial consonant and the final consonant class (romanizations are
   inconsistent: x = s, v = w, nh/gn = ny ...; the vowels and tones are not compared).
3. --sample random corpus words with their readings, printed for hand checking.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

from vtts.frontend.lo.g2p_lo import (
    DEPENDENT,
    TONE_MARKS,
    parse_word,
    prepare,
    run_syllables,
    segment,
    word_set,
)

LAO_RUN = re.compile(r"[ກ-ໍໜ-ໟ]+")
# romanization onset -> our initial (longest first)
ONSETS = (("ng", "ng"), ("ny", "ny"), ("nh", "ny"), ("gn", "ny"), ("kh", "kh"), ("th", "th"),
          ("ph", "ph"), ("ch", "c"), ("x", "s"), ("s", "s"), ("k", "k"), ("g", "k"), ("c", "c"),
          ("j", "c"), ("d", "d"), ("t", "t"), ("n", "n"), ("b", "b"), ("p", "p"), ("f", "f"),
          ("m", "m"), ("y", "j"), ("r", "r"), ("l", "l"), ("v", "w"), ("w", "w"), ("h", "h"))
FINALS = (("ng", "ng"), ("k", "k"), ("g", "k"), ("c", "k"), ("t", "t"), ("d", "t"), ("n", "n"),
          ("p", "p"), ("b", "p"), ("m", "m"))
VOWEL_START = re.compile(r"^[aeiouāăáàēéèěīíìǒōóòūúùŭ]")


def onset_of(piece: str) -> str:
    if VOWEL_START.match(piece):
        return "?"
    for r, o in ONSETS:
        if piece.startswith(r):
            return o
    return ""


def final_of(piece: str) -> str:
    for r, f in FINALS:
        if piece.endswith(r) and not piece.endswith(("nh", "ny")):
            return f
    return ""


def structure(rows: list[dict]) -> None:
    letters = read = syl = written = covered = 0
    words = word_set()
    for r in rows:
        for run in LAO_RUN.findall(r["text"]):
            w = prepare(run)
            for piece in w.split("ໆ"):
                for word in segment(piece):
                    covered += len(word) if word in words else 0
                    letters += len(word)
                    syls = parse_word(word)
                    syl += len(syls)
                    written += sum(s.kind == "x" for s in syls)
                    # letters read: everything but skipped dependent signs at a word start
                    read += len(word) - (1 if word[0] in DEPENDENT and word[0] not in TONE_MARKS else 0)
    print(f"structure: {syl} syllables; {100 * written / syl:.2f}% with a written vowel, "
          f"{100 * read / letters:.2f}% of letters read, {100 * covered / letters:.1f}% of letters in "
          f"listed words")


def dictionary_scores(path: Path) -> tuple[int, int, int, int, int]:
    n = same = syls_total = onset_ok = final_ok = 0
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w, rom = row["LaoWord"].strip(), row["Pronunciation"].strip().lower()
            if not w or not LAO_RUN.fullmatch(w) or not rom or "ຽ" in w or "ຣ" in w:
                continue
            pieces = re.split(r"[\s\-]+", re.sub(r"[^a-zāăáàēéèěīíìǒōóòūúùŭ:\s\-]", "", rom))
            pieces = [p.replace(":", "") for p in pieces if p]
            syls = run_syllables(w)
            n += 1
            if len(pieces) != len(syls):
                continue
            same += 1
            for p, s in zip(pieces, syls, strict=True):
                syls_total += 1
                onset_ok += onset_of(p) == s.initials[0]
                fin = s.final if s.final in ("k", "t", "p", "m", "n", "ng") else ""
                final_ok += final_of(p) == fin
    return n, same, syls_total, onset_ok, final_ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--dict", type=Path)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--sample", type=int, default=40)
    a = ap.parse_args()
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines()[:a.n]][1::2]
    print(f"{len(rows)} utterances")
    structure(rows)
    if a.dict:
        n, same, total, onset_ok, final_ok = dictionary_scores(a.dict)
        print(f"dictionary romanization: {n} entries, syllable count agrees for {100 * same / n:.1f}%; "
              f"on those {total} syllables: initial {100 * onset_ok / total:.1f}%, "
              f"final consonant {100 * final_ok / total:.1f}%")
    words = sorted({w for r in rows for run in LAO_RUN.findall(r["text"])
                    for w in segment(prepare(run).replace("ໆ", ""))})
    for w in random.Random(0).sample(words, min(a.sample, len(words))):
        print(w, " | ".join(" ".join(s.tokens()).replace("LO:", "") for s in run_syllables(w)))


if __name__ == "__main__":
    main()
