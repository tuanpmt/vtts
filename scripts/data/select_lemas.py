"""Pick a syllable-coverage-weighted subset of LEMAS (CC BY 4.0) for teacher pretraining.

Input is a slim TSV (key, audio, dur, mean_score, min_score, text) built from the LEMAS jsonl.
Clips are filtered by duration, alignment score and readability (no letter spelling, no digits),
then chosen in two passes: first clips that add syllables still seen fewer than --min-count times,
then a random fill up to --hours. Writes LEMAS paths + text + duration as TSV.

Usage: uv run python scripts/data/select_lemas.py --slim slim.tsv --out pick.tsv [--hours 60]
"""

import argparse
import collections
import random
import re
from pathlib import Path

from vtts.frontend.normalize import normalize, spelled_words
from vtts.frontend.phoneme_set import PUNCTUATION

DIGIT = re.compile(r"\d")


def syllables(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w not in PUNCTUATION]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slim", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=60.0)
    ap.add_argument("--min-count", type=int, default=30)
    ap.add_argument("--min-score", type=float, default=0.85)
    ap.add_argument("--per-source", type=int, default=150)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    clips = []
    for ln in a.slim.open(encoding="utf-8"):
        key, audio, dur, ms, mn, text = ln.rstrip("\n").split("\t")
        dur, ms, mn = float(dur), float(ms), float(mn)
        if not 2.0 <= dur <= 12.0 or ms < a.min_score or mn < 0.3 or DIGIT.search(text):
            continue
        if spelled_words(text):
            continue
        syl = syllables(text)
        if len(syl) < 4 or len(syl) / dur > 7.5:
            continue
        clips.append((key, audio, dur, text, syl))
    print(f"eligible {len(clips)} clips, {sum(c[2] for c in clips) / 3600:.0f} h")

    random.Random(a.seed).shuffle(clips)
    src = collections.Counter()
    seen = collections.Counter()
    picked, budget, total = [], a.hours * 3600, 0.0

    def take(c) -> None:
        nonlocal total
        picked.append(c)
        total += c[2]
        src[c[0].split("-")[0]] += 1
        seen.update(c[4])

    freq = collections.Counter(s for c in clips for s in c[4])
    rare_first = sorted(clips, key=lambda c: min(freq[s] for s in c[4]))
    used = set()
    for c in rare_first:
        if total >= budget * 0.5:
            break
        if src[c[0].split("-")[0]] >= a.per_source:
            continue
        if any(seen[s] < a.min_count for s in c[4]):
            take(c)
            used.add(c[0])
    n_cov = len(picked)
    for c in clips:
        if total >= budget:
            break
        if c[0] in used or src[c[0].split("-")[0]] >= a.per_source:
            continue
        take(c)
    print(f"picked {len(picked)} clips ({n_cov} for coverage), {total / 3600:.1f} h, "
          f"{len(seen)} distinct syllables, {len(src)} sources")
    with a.out.open("w", encoding="utf-8") as o:
        for key, audio, dur, text, _ in picked:
            o.write(f"{key}\t{audio}\t{dur}\t{text}\n")


if __name__ == "__main__":
    main()
