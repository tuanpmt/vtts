"""Build the Khmer tables src/vtts/frontend/lexicons/km/{words.txt,overrides.tsv,rhymes.tsv,onsets.tsv}.

Usage: uv run --extra gpu python scripts/frontend/build_km_lexicon.py [--lexicon PATH]
       [--freq PATH] [--min-word-freq 3] [--min-override-freq 10] [--holdout 0]

Source: the Khmer pronunciation lexicon of Google's language-resources (km/data/lexicon.tsv,
https://github.com/google/language-resources, CC BY 4.0, Copyright 2018 Google Inc.), downloaded
to ~/.cache/vtts/ when --lexicon is not given. Khmer Wikipedia (wikimedia/wikipedia 20231101.km,
CC BY-SA) is only used to count how often each lexicon word occurs; no Wikipedia text is kept
(the counts are cached in --freq, default ~/.cache/vtts/km_wiki_freq.tsv).

- Spellings are folded as at run time (g2p_km.spell); lexicon entries with digits or Latin are
  skipped.
- rhymes.tsv / onsets.tsv: the rules of g2p_km cut each lexicon word into syllables; when the
  count matches the lexicon's, each syllable's rhyme key (Syllable.key) and onset letters are
  paired with the lexicon's vowel + final and onset sounds. The most frequent reading of each key
  is kept (weight 1 + sqrt(min(Wikipedia count, 1000)) per word; keys seen less than twice are
  dropped).
- overrides.tsv: words with a Wikipedia count >= --min-override-freq that the rules (with the new
  tables) read differently from every lexicon reading: the first lexicon reading.
- words.txt: the other lexicon words with a count >= --min-word-freq (word segmentation only).
- --holdout K: leave out every word whose spelling hash is 0 mod K from all four tables (for
  scripts/frontend/eval_km_g2p.py); the tables are then written to --out-dir.
"""

from __future__ import annotations

import argparse
import collections
import itertools
import re
import urllib.request
import zlib
from pathlib import Path

from vtts.frontend.km.g2p_km import VOWEL_PHONES as VOWELS

LEX_URL = ("https://raw.githubusercontent.com/google/language-resources/master/km/data/"
           "lexicon.tsv")
CACHE = Path.home() / ".cache" / "vtts"
OUT = Path(__file__).parents[2] / "src" / "vtts" / "frontend" / "lexicons" / "km"
KHMER_WORD = re.compile(r"[ក-៓៝\u200b-\u200d]+")


def load_lexicon(path: Path) -> dict[str, list[list[list[str]]]]:
    """Folded spelling -> readings (syllables of phonemes), in file order."""
    from vtts.frontend.km.g2p_km import spell

    lex: dict[str, list[list[list[str]]]] = collections.defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "\t" not in line:
            continue
        word, pron = line.split("\t")[:2]
        if not KHMER_WORD.fullmatch(word) or not pron.strip():
            continue
        p = [q for s in pron.split(" . ") for q in resplit(s.split())]
        if not p:
            continue
        w = spell(word)
        if p not in lex[w]:
            lex[w].append(p)
    return lex


def resplit(syl: list[str]) -> list[list[str]]:
    """A lexicon syllable with more than one vowel (a missing " . ") cut before each later vowel:
    one consonant between two vowels starts the second syllable, of more the first closes the
    first syllable. A syllable without a vowel is dropped."""
    vowels = [k for k, x in enumerate(syl) if x in VOWELS]
    if not vowels:
        return []
    cuts = [0]
    for a, b in itertools.pairwise(vowels):
        between = b - a - 1
        cuts.append(b if between == 0 else b - 1 if between == 1 else a + 2)
    cuts.append(len(syl))
    return [syl[i:j] for i, j in itertools.pairwise(cuts)]


def wiki_counts(words: set[str], cache: Path) -> collections.Counter:
    """Occurrences of the lexicon words in Khmer Wikipedia (segmentation over the lexicon)."""
    counts: collections.Counter = collections.Counter()
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            w, c = line.split("\t")
            counts[w] = int(c)
        return counts
    from datasets import load_dataset

    from vtts.frontend.km.g2p_km import REPEAT, segment, spell

    maxw = max(map(len, words))
    ds = load_dataset("wikimedia/wikipedia", "20231101.km", split="train")
    for art in ds:
        for m in re.finditer(r"[ក-៓ៗ៝]+", spell(art["text"])):
            for piece in m.group(0).split(REPEAT):
                for w in segment(piece, words, maxw) if piece else []:
                    if w in words:
                        counts[w] += 1
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("".join(f"{w}\t{c}\n" for w, c in counts.most_common()), encoding="utf-8")
    return counts


def split_syllable(ph: list[str]) -> tuple[list[str], list[str]]:
    k = next((i for i, x in enumerate(ph) if x in VOWELS), len(ph))
    return ph[:k], ph[k:]


def learn(lex, counts) -> tuple[dict[str, str], dict[str, str]]:
    from vtts.frontend.km.g2p_km import syllables

    rhymes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    onsets: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for w, prons in lex.items():
        syls = syllables(w)
        p = min(prons, key=lambda q: abs(len(q) - len(syls)))
        if len(p) != len(syls):
            continue
        weight = 1 + min(counts.get(w, 0), 1000) ** 0.5
        for s, ref in zip(syls, p, strict=True):
            if s.indep:
                continue
            ons, rh = split_syllable(ref)
            if rh:
                rhymes[s.key()][" ".join(rh)] += weight
            if len(s.onset) > 1:
                onsets[s.onset][" ".join(ons)] += weight

    def best(table):
        out = {}
        for k in sorted(table):
            c = table[k]
            reading, _ = max(c.items(), key=lambda kv: (kv[1], kv[0]))
            if sum(c.values()) >= 2 and reading:
                out[k] = reading
        return out

    return best(rhymes), best(onsets)


def write_table(path: Path, header: str, rows: dict[str, str]) -> None:
    path.write_text(header + "".join(f"{k}\t{v}\n" for k, v in rows.items()), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lexicon", type=Path, default=CACHE / "km_lexicon.tsv")
    ap.add_argument("--freq", type=Path, default=CACHE / "km_wiki_freq.tsv")
    ap.add_argument("--min-word-freq", type=int, default=3)
    ap.add_argument("--min-override-freq", type=int, default=10)
    ap.add_argument("--holdout", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()
    if not a.lexicon.exists():
        a.lexicon.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(LEX_URL, a.lexicon)
    lex = load_lexicon(a.lexicon)
    counts = wiki_counts(set(lex), a.freq)
    if a.holdout:
        lex = {w: p for w, p in lex.items() if zlib.crc32(w.encode()) % a.holdout}
    rhymes, onsets = learn(lex, counts)
    src = ("# Generated by scripts/frontend/build_km_lexicon.py from the Khmer lexicon of Google's\n"
           "# language-resources (CC BY 4.0, see NOTICE).\n")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    write_table(a.out_dir / "rhymes.tsv", "# Khmer rhymes: series + vowel signs (+ bantoc) | final sound"
                " | position\n# (e last syllable, c open with an onset cluster, m other) -> vowel"
                " and final.\n" + src, rhymes)
    write_table(a.out_dir / "onsets.tsv", "# Khmer onset clusters (letters) -> sounds.\n" + src, onsets)
    from vtts.frontend.km import g2p_km

    g2p_km.rhyme_table.cache_clear()
    g2p_km.onset_table.cache_clear()
    if a.out_dir != OUT:  # read the new tables
        g2p_km.rhyme_table = lambda: _read(a.out_dir / "rhymes.tsv")  # type: ignore[assignment]
        g2p_km.onset_table = lambda: _read(a.out_dir / "onsets.tsv")  # type: ignore[assignment]
    overrides = {}
    for w, prons in sorted(lex.items()):
        if counts.get(w, 0) >= a.min_override_freq and g2p_km.rule_phones(w) not in prons:
            overrides[w] = " . ".join(" ".join(s) for s in prons[0])
    write_table(a.out_dir / "overrides.tsv", "# Khmer words the rules read differently from the lexicon"
                f" (count >= {a.min_override_freq} in Khmer\n# Wikipedia): word<TAB>phonemes, syllables"
                " separated by \" . \".\n" + src, overrides)
    words = sorted(w for w in lex if counts.get(w, 0) >= a.min_word_freq and w not in overrides)
    (a.out_dir / "words.txt").write_text(
        "# Khmer words for word segmentation (km/g2p_km.segment), one per line.\n" + src
        + "".join(w + "\n" for w in words), encoding="utf-8")
    print(f"lexicon {len(lex)} words; rhymes {len(rhymes)}, onsets {len(onsets)}, "
          f"overrides {len(overrides)}, words {len(words)}")


def _read(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            k, v = line.split("\t")
            out[k] = v
    return out


if __name__ == "__main__":
    main()
