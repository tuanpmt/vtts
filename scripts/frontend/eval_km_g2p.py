"""Agreement of the Khmer front-end with the Google Khmer lexicon (CC BY 4.0).

Usage: uv run --extra gpu python scripts/frontend/eval_km_g2p.py [--holdout 10]
       [--sentences data/km/sentences.jsonl] [--errors 30]

1. Rules on held-out words: the lexicon words whose spelling hash is 0 mod --holdout are left out,
   the rhyme and onset tables are learned from the others (as build_km_lexicon.py does), and the
   rules (no override table) read the held-out words. Reported per word type and weighted by the
   word's count in Khmer Wikipedia: words read exactly (any lexicon reading), syllables (when the
   syllable count matches) and phoneme error rate (Levenshtein over phonemes / reference phonemes).
2. The shipped front-end (tables and overrides of src/vtts/frontend/lexicons/km) on running text:
   the --sentences rows are cut into words by the front-end's segmentation; every word found in
   the lexicon is compared with it (token-weighted). Words outside the lexicon have no reference
   and are counted separately. The override table holds the lexicon readings of frequent words,
   so this measures coverage of the shipped tables on Wikipedia text, not the rules alone.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _build():
    spec = importlib.util.spec_from_file_location("build_km_lexicon", ROOT / "scripts" / "frontend"
                                                  / "build_km_lexicon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def _fmt(p: list[list[str]]) -> str:
    return " . ".join(" ".join(x) for x in p)


def _score(pairs, counts):
    """pairs: (word, hypothesis syllables, reference readings). Type and token-weighted rates."""
    out = {}
    for name, weight in (("types", lambda w: 1), ("tokens", lambda w: counts.get(w, 0))):
        tot = exact = syl_tot = syl_ok = ph_tot = ph_err = 0
        for w, hyp, refs in pairs:
            k = weight(w)
            if not k:
                continue
            tot += k
            exact += k * (hyp in refs)
            ref = min(refs, key=lambda r: _edits([p for s in hyp for p in s], [p for s in r for p in s]))
            if len(ref) == len(hyp):
                syl_tot += k * len(ref)
                syl_ok += k * sum(a == b for a, b in zip(hyp, ref, strict=True))
            flat_ref = [p for s in ref for p in s]
            ph_tot += k * len(flat_ref)
            ph_err += k * _edits([p for s in hyp for p in s], flat_ref)
        out[name] = (100 * exact / max(tot, 1), 100 * syl_ok / max(syl_tot, 1), 100 * ph_err / max(ph_tot, 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", type=int, default=10)
    ap.add_argument("--sentences", type=Path, default=ROOT / "data" / "km" / "sentences.jsonl")
    ap.add_argument("--errors", type=int, default=30)
    a = ap.parse_args()
    b = _build()
    from vtts.frontend.km import g2p_km

    lex = b.load_lexicon(b.CACHE / "km_lexicon.tsv")
    counts = b.wiki_counts(set(lex), b.CACHE / "km_wiki_freq.tsv")
    held = {w for w in lex if zlib.crc32(w.encode()) % a.holdout == 0}
    rhymes, onsets = b.learn({w: p for w, p in lex.items() if w not in held}, counts)
    shipped = (g2p_km.rhyme_table, g2p_km.onset_table)
    g2p_km.rhyme_table, g2p_km.onset_table = (lambda: rhymes), (lambda: onsets)
    pairs = [(w, g2p_km.rule_phones(w), lex[w]) for w in sorted(held)]
    g2p_km.rhyme_table, g2p_km.onset_table = shipped
    s = _score(pairs, counts)
    print(f"1. rules on {len(held)} held-out lexicon words (tables learned without them):")
    for name, (ex, syl, per) in s.items():
        print(f"   {name:6s}: words exact {ex:.1f}%, syllables {syl:.1f}%, phoneme error rate {per:.1f}%")
    if a.errors:
        bad = sorted(((counts.get(w, 0), w, h, r) for w, h, r in pairs if h not in r), reverse=True)
        for c, w, h, r in bad[:a.errors]:
            print(f"   {c:6d} {w}  rules: {_fmt(h)}  lexicon: {_fmt(r[0])}")
    if not a.sentences.exists():
        return
    words, unknown = [], 0
    known = 0
    for line in a.sentences.read_text(encoding="utf-8").splitlines():
        text = json.loads(line)["text"]
        for run in re.findall(r"[ក-៓៝]+", g2p_km.spell(text)):
            for w in g2p_km.segment(run):
                if w in lex:
                    words.append(w)
                    known += 1
                else:
                    unknown += 1
    tok = {}
    for w in words:
        tok[w] = tok.get(w, 0) + 1
    pairs = [(w, g2p_km.word_phones(w), lex[w]) for w in tok]
    s = _score(pairs, tok)["tokens"]
    print(f"2. shipped front-end on {a.sentences.name}: {known} word tokens in the lexicon, {unknown} "
          f"pieces outside it ({100 * unknown / max(known + unknown, 1):.1f}%)")
    print(f"   tokens: words exact {s[0]:.1f}%, syllables {s[1]:.1f}%, phoneme error rate {s[2]:.1f}%")


if __name__ == "__main__":
    main()
