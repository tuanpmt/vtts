"""Language of a plain Latin word in a Latin-script pair (es-en, id-en, pt-en, de-en, it-en,
tr-en, pl-en, fi-en).

Spanish, Indonesian and Portuguese are written in the same letters as English, so a word without
the language's own letters (á, ñ, ç, ã ...) needs a rule, like Vietnamese in the vi-en pair
(lang.py). In order, for a pair language L:

1. a word with L's own letters, in lexicons/L/native.txt (native words that look English) or a
   unit or abbreviation of L's normalizer (km, kWh, etc) is L;
2. a word in lexicons/latin/english.txt is English (common English words and tech terms whose
   spelling would also fit L: update, online, game, smart ...);
3. a word with a capital letter after a lower-case one is English (iPhone, GitHub, macOS);
4. a single letter (a unit after a number, an initial) or a short all-caps word (2-5 letters) is
   L: an acronym, spelled with L's letter names;
5. a word whose spelling fits L (vtts.frontend.L.g2p_L.valid_spelling: letters, onset and coda
   clusters of L) is L; any other word is English (Facebook, Bluetooth, weekend).

Hyphenated words are decided on their parts (Wi-Fi: "wi" does not fit Spanish, so English).

Italian and Turkish write apostrophes inside words (APOSTROPHE_MODES): an Italian elided word
(l', dell', sull': g2p_it.ELIDED) is Italian and l'acqua is decided on "acqua"; a Turkish word is
decided on its part before the apostrophe (Cumhuriyeti'nde); a part of a hyphenated word may be a
native word (sud-ovest). split_elision makes two chunks of an elided Italian word before an English
word (sull'iPhone) and of an English word before a Turkish suffix (iPhone'da).
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
    "pt": "áâãàçéêíóôõúüÁÂÃÀÇÉÊÍÓÔÕÚÜ",
    "de": "äöüßÄÖÜẞ",
    "it": "àèéìíòóùÀÈÉÌÍÒÓÙ",
    "tr": "çğıöşüâîûÇĞİÖŞÜÂÎÛ",
    "pl": "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
}
LATIN_PAIRS["nl"] = "éëïöüèáóúíàêçÉËÏÖÜÈÁÓÚÍ"
LATIN_PAIRS["sv"] = "åäöÅÄÖ"
LATIN_PAIRS["no"] = "æøåÆØÅ"
LATIN_PAIRS["fr"] = "àâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ"
LATIN_PAIRS["fi"] = "äöåšžÄÖÅŠŽ"
LATIN_PAIRS["ms"] = ""  # Malay has no letters of its own
LATIN_PAIRS["tl"] = "ñÑáàâéèêíìîóòôúùûÁÀÂÉÈÊÍÌÎÓÒÔÚÙÛ"  # ñ and the stress/glottal accent marks
# Pairs where a hyphenated word with a part in the English list is English (Tagalog affixes on
# English verbs: i-share, nag-email, na-update).
HYPHEN_ENGLISH = frozenset(("tl",))
LATIN_PAIRS["sw"] = ""  # Swahili has no letters of its own (ng' uses the apostrophe)
# Pairs where an apostrophe is part of a letter (Swahili ng'ombe): words are not split there.
APOSTROPHE_LETTER = frozenset(("sw",))


@cache
def _valid(code: str) -> Callable[[str], bool]:
    return importlib.import_module(f"vtts.frontend.{code}.g2p_{code}").valid_spelling


@cache
def _elided(code: str) -> frozenset[str]:
    """Elided words of the language written before an apostrophe (Italian l', dell', un'):
    g2p_<code>.ELIDED, empty when the module has none."""
    return getattr(importlib.import_module(f"vtts.frontend.{code}.g2p_{code}"), "ELIDED", frozenset())


@cache
def _table_keys(code: str) -> frozenset[str]:
    """Lower-case units and abbreviations (without the final '.') of the language's normalizer:
    km, kWh, GHz, etc, vc ... are read by it, so they belong to the language."""
    norm = importlib.import_module(f"vtts.frontend.{code}.normalize_{code}")
    keys = list(norm.UNITS) + list(norm.ABBREVIATIONS)
    return frozenset(k.lower().rstrip(".") for k in keys)


@cache
def has_letters_of(code: str) -> Callable[[str], bool]:
    letters = frozenset(LATIN_PAIRS[code])
    return lambda word: any(ch in letters for ch in word)


# Pair languages that write an apostrophe inside words (Italian elision l'acqua, Turkish suffixes
# after a name İstanbul'da); the typographic apostrophe ’ is read as '.
APOSTROPHE_MODES = ("it", "tr")


EDGE = ".,;:!?\"'()[]{}…“”‘’«»–—"  # lang.EDGE
SUFFIX_APOSTROPHE = ("tr",)  # a suffix after a name: Google'da, İstanbul'dan
SUFFIX_LETTERS = frozenset("abcçdefgğhıijklmnoöprsştuüvyzâîû")  # letters of a Turkish suffix


def split_elision(chunk: str, code: str) -> list[str]:
    """An elided word of the language before an English word is its own chunk (it: sull'iPhone ->
    sull' / iPhone), and so is a suffix after an English word (tr: iPhone'u -> iPhone / 'u), so
    each part is read in its language; other chunks are kept whole."""
    head, apostrophe, rest = chunk.partition("'")
    core, rest_core = head.lstrip(EDGE), rest.strip(EDGE)
    if not (apostrophe and rest_core and core):
        return [chunk]
    if core.lower() in _elided(code) and _is_plain(rest_core) and latin_word_lang(rest_core, code) == "en":
        return [head + "'", rest]
    if (code in SUFFIX_APOSTROPHE and all(ch in SUFFIX_LETTERS for ch in rest_core) and _is_plain(core)
            and latin_word_lang(core, code) == "en"):
        return [head, "'" + rest]
    return [chunk]


def _is_plain(word: str) -> bool:
    return all(ch.isascii() and (ch.isalpha() or ch in "-'") for ch in word) and any(
        ch.isalpha() for ch in word)


def _camel(part: str) -> bool:
    return any(a.islower() and b.isupper() for a, b in pairwise(part))


def latin_word_lang(core: str, code: str) -> str:
    """code or "en" for a Latin word (letters, - and ') in the pair of code."""
    low = core.lower()
    if (has_letters_of(code)(core) or low in load_words(code, "native") or low in _table_keys(code)
            or low in _elided(code)):
        return code
    if low in load_words("latin", "english"):
        return "en"
    head, apostrophe, rest = core.partition("'")
    if apostrophe and rest and head.lower() in _elided(code):  # l'acqua: decided on "acqua"
        return latin_word_lang(rest, code)
    # tr: the suffix after an apostrophe (Cumhuriyeti'nde) is not a word of its own
    stem = core.split("'")[0] if code in SUFFIX_APOSTROPHE else core
    # sw: the apostrophe of ng' is a letter, the word is split at hyphens only
    parts = [p for p in re.split(r"-" if code in APOSTROPHE_LETTER else r"[-']", stem) if p]
    if code in HYPHEN_ENGLISH and "-" in core and any(
            p.lower() in load_words("latin", "english") for p in parts):
        return "en"
    if any(_camel(p) for p in parts):
        return "en"
    if len(core) == 1 or all(p.isupper() and 2 <= len(p) <= 5 for p in parts):
        return code
    # it, tr: a part may also be a native word (sud-ovest)
    native = load_words(code, "native") if code in APOSTROPHE_MODES else frozenset()
    if all(_valid(code)(p.lower()) or p.lower() in native for p in parts):
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
