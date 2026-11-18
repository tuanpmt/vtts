"""Language of a plain Latin word in a Latin-script pair (es-en, id-en, pt-en).

Spanish, Indonesian and Portuguese are written in the same letters as English, so a word without
the language's own letters (á, ñ, ç, ã ...) needs a rule, like Vietnamese in the vi-en pair
(lang.py). In order, for a pair language L:

1. a word in lexicons/L/native.txt is L (function words and native words that look English);
2. a word in lexicons/latin/english.txt is English (common English words and tech terms whose
   spelling would also fit L: update, online, game, smart ...);
3. a word with a capital letter after a lower-case one is English (iPhone, GitHub, macOS);
4. a short all-caps word (2-5 letters) is L: an acronym, spelled with L's letter names;
5. a word whose spelling fits L (vtts.frontend.L.g2p_L.valid_spelling: letters, onset and coda
   clusters of L) is L; any other word is English (Facebook, Bluetooth, weekend).

Hyphenated words are decided on their parts (Wi-Fi: "wi" does not fit Spanish, so English).
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from functools import cache
from itertools import pairwise

from .lexicons import load_words

# Pair language -> its letters outside ASCII (a word with one of them is that language).
LATIN_PAIRS: dict[str, str] = {
    "es": "áéíóúüñÁÉÍÓÚÜÑ",
    "id": "",  # Indonesian has no letters of its own
}


@cache
def _valid(code: str) -> Callable[[str], bool]:
    return importlib.import_module(f"vtts.frontend.{code}.g2p_{code}").valid_spelling


@cache
def has_letters_of(code: str) -> Callable[[str], bool]:
    letters = frozenset(LATIN_PAIRS[code])
    return lambda word: any(ch in letters for ch in word)


def _camel(part: str) -> bool:
    return any(a.islower() and b.isupper() for a, b in pairwise(part))


def latin_word_lang(core: str, code: str) -> str:
    """code or "en" for a Latin word (letters, - and ') in the pair of code."""
    low = core.lower()
    if has_letters_of(code)(core) or low in load_words(code, "native"):
        return code
    if low in load_words("latin", "english"):
        return "en"
    parts = [p for p in re.split(r"[-']", core) if p]
    if any(_camel(p) for p in parts):
        return "en"
    if all(p.isupper() and 2 <= len(p) <= 5 for p in parts):
        return code
    if all(_valid(code)(p.lower()) for p in parts):
        return code
    return "en"


# ---------------- spelling checks shared by the languages' valid_spelling ----------------

def consonant_runs(w: str, vowels: str = "aeiou",
                   y_vowel: bool = True) -> list[tuple[str, bool, bool]] | None:
    """(consonant run, at the start, at the end) of a word whose digraphs were replaced by one
    upper-case letter; with y_vowel, y is a vowel unless a vowel follows. None when the word has
    no vowel."""
    is_v = [ch in vowels or (y_vowel and ch == "y" and not (k + 1 < len(w) and w[k + 1] in vowels))
            for k, ch in enumerate(w)]
    if not any(is_v):
        return None
    runs, k = [], 0
    while k < len(w):
        if is_v[k]:
            k += 1
            continue
        j = k
        while j < len(w) and not is_v[j]:
            j += 1
        runs.append((w[k:j], k == 0, j == len(w)))
        k = j
    return runs


def clusters_fit(runs, onsets, codas, finals) -> bool:
    """Every run is a valid onset (start), final coda (end) or coda + onset (inside)."""
    def onset(r: str) -> bool:
        return len(r) == 1 or r in onsets

    for run, start, end in runs:
        if start and not onset(run):
            return False
        if end and run not in finals:
            return False
        if not start and not end and not any((s == 0 or run[:s] in codas) and onset(run[s:])
                                             for s in range(len(run))):
            return False
    return True
