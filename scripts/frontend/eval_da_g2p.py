"""Measure the Danish G2P against two references (measuring sticks only; nothing is shipped).

Usage: uv run python scripts/frontend/eval_da_g2p.py --sentences data/da/sentences.jsonl \
       [--nst PATH/dan030224NST.pron] [--freq PATH/da_freq.json] [--n 2000]

1. eSpeak NG (`espeak-ng -v da --ipa`), on the words of the odd rows of the first --n sentences:
   both readings are mapped to coarse IPA (no stress, stød or length; the r-schwa and the open o
   of "op" are one class, as eSpeak writes both ʌ; stops p/b t/d k/g and ɔ/ɒ merged), then whole-word agreement and the phoneme error
   rate (PER) over all word tokens. eSpeak is a rule system with its own errors.
2. NST (the lexicon source, CC0), on words NOT in lexicons/da (ranks after the table's words in
   --freq that NST transcribes): how well compounds + rules read unseen words, exact token
   sequence, without stress/stød, and PER.
3. Coverage of the running text: share of word tokens read from the lexicon, as known words,
   as compounds and by the rules alone.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from vtts.frontend.da.g2p_da import (
    fold,
    known_words,
    lexicon,
    split_compound,
    word_tokens_names,
)

OURS = {"i": "i", "e": "e", "E": "ɛ", "a": "a", "A": "ɑ", "y": "y", "2": "ø", "9": "œ", "u": "u",
        "o": "o", "O": "ɔ", "Q": "ɒ", "@": "ə", "V": "ʌ", "6": "ʌ", "6~": "ʌ", "j~": "j", "w": "w",
        "p": "p", "t": "t", "k": "k", "b": "b", "d": "d", "g": "g", "f": "f", "v": "v", "s": "s",
        "s'": "ʃ", "h": "h", "m": "m", "n": "n", "N": "ŋ", "l": "l", "R": "ʁ", "j": "j", "D": "ð"}
ESPEAK = {"ʋ": "v", "ɡ": "g", "ɐ": "ʌ", "r": "ʁ", "ɕ": "ʃ", "æ": "ɛ", "ɪ": "i", "ʊ": "u", "ɜ": "ə",
          "ɤ": "ʌ", "ʏ": "y", "ɘ": "ə", "ε": "ɛ"}
# Merged in both readings: the Danish stop pairs (b d g are unaspirated p t k; NST writes sp st sk
# and a stop after a vowel as b d g, eSpeak as p t k) and ɔ/ɒ (the notations place å differently).
MERGE = {"p": "b", "t": "d", "k": "g", "ɒ": "ɔ"}
DROP = set("ˈˌʔ‍ː̯ ̩-.")
WORD = re.compile(r"[a-zæøåé]+")


def ours_coarse(word: str) -> list[str]:
    out = []
    for t in word_tokens_names(word):
        t = t.removesuffix(":")
        if t in OURS:
            out.append(MERGE.get(OURS[t], OURS[t]))
    return out


def espeak_coarse(words: list[str]) -> list[list[str]]:
    p = subprocess.run(["espeak-ng", "-v", "da", "-q", "--ipa=3", "--sep=_"], input="\n".join(words),
                       capture_output=True, text=True, check=True)
    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    out = []
    for ln in lines:
        seq = []
        for ch in re.sub(r"\([a-z]+\)", "", ln).replace("_", ""):
            if ch in DROP or ch == "?":
                continue
            ch = ESPEAK.get(ch, ch)
            seq.append(MERGE.get(ch, ch))
        out.append(seq)
    return out


def edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--nst", type=Path)
    ap.add_argument("--freq", type=Path)
    ap.add_argument("--n", type=int, default=2000)
    a = ap.parse_args()
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines()[:a.n]][1::2]
    tokens = [w for r in rows for w in WORD.findall(r["text"].lower())]
    types = sorted(set(tokens))
    print(f"{len(rows)} sentences, {len(tokens)} word tokens, {len(types)} types")

    src = Counter()
    for w in tokens:
        f = fold(w)
        src["lexicon" if f in lexicon() else "known" if f in known_words()
            else "compound" if split_compound(f) else "rules"] += 1
    print("coverage:", ", ".join(f"{k} {100 * v / len(tokens):.1f}%" for k, v in src.most_common()))

    es = dict(zip(types, espeak_coarse(types), strict=True))
    same = err = ref_len = 0
    for w in tokens:
        h, r = ours_coarse(w), es[w]
        same += h == r
        err += edits(r, h)
        ref_len += len(r)
    print(f"eSpeak NG: {100 * same / len(tokens):.1f}% of word tokens read the same (coarse), "
          f"PER {100 * err / max(ref_len, 1):.1f}%")

    if a.nst and a.freq:
        sys.path.insert(0, str(Path(__file__).parent))
        from build_da_lexicon import best_reading, load_nst, nst_to_tokens

        nst = load_nst(a.nst)
        freq = json.loads(a.freq.read_text(encoding="utf-8"))
        n = exact = seg = err = ref_len = 0
        for w, _ in freq:
            if w in known_words() or w not in nst or not WORD.fullmatch(w):
                continue
            ref = nst_to_tokens(best_reading(nst[w]))
            if ref is None:
                continue
            hyp = word_tokens_names(w)
            n += 1
            exact += hyp == ref
            strip = [t for t in hyp if t not in '"%?'], [t for t in ref if t not in '"%?']
            seg += strip[0] == strip[1]
            err += edits(strip[1], strip[0])
            ref_len += len(strip[1])
            if n >= 20000:
                break
        print(f"NST, {n} unseen words: exact {100 * exact / n:.1f}%, without stress and stød "
              f"{100 * seg / n:.1f}%, PER {100 * err / ref_len:.1f}%")


if __name__ == "__main__":
    main()
