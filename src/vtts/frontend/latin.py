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
LATIN_PAIRS["da"] = "æøåéÆØÅÉ"  # Danish letters (é in loanwords: idé, café)


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


# ---------------- sentence language ----------------
#
# Word by word, an English word whose spelling fits the pair language (I, a, time, minutes) is read
# in that language, which is right inside a sentence of the language and wrong in a whole English
# sentence. sentence_is_english sorts the tagged words of one sentence (numbers and symbols aside):
# - main: the language's own letters, or a word of lexicons/<code>/function.txt;
# - neither: a word of function.txt or native.txt that is also an English word (a, no, in, time);
# - strong English: a word of lexicons/latin/function_en.txt (the, you, of, is, can't ...);
# - English: a strong word, a word of lexicons/latin/common_en.txt or a word latin_word_lang tags
#   English (english.txt, CamelCase, spelling that does not fit the language);
# - other words: words that fit the language's spelling, in no list.
# Over the words other than the "neither" ones, the sentence is English when it has at least
# SENT_MIN_EN English words, one of them strong, more than SENT_EN_PER_MAIN times as many English
# words as main ones, English words for at least a quarter of its words, and either for half of
# them or in two runs or more (English words with other words between them: in an English
# sentence they are spread out, in a sentence of the language an English term is one run).
# lang.tag_words then reads all its words in English, numbers included, except those with the
# language's own letters (São, Müller). A sentence of the language with English terms keeps its
# word-by-word tags: it has function words of its own ("Abra o Netflix"), a term alone (Low Power
# Mode, Black Friday) has no strong English word, and a term with one (check in) is one run.
# The vi mode of the vi-en pair uses the same rule (word_evidence): its main words are those with
# Vietnamese letters, and an English word that is also a Vietnamese syllable (the, to, an, can) is
# tagged Vietnamese and counts for neither, so unaccented Vietnamese stays Vietnamese.

SENT_MIN_EN = 2
SENT_EN_PER_MAIN = 3


@cache
def _english_words() -> frozenset[str]:
    return load_words("latin", "function_en") | load_words("latin", "common_en") | load_words("latin", "english")


def own_letters(code: str) -> Callable[[str], bool]:
    """The rule of the main language's own letters ("vi": any non-ASCII letter after NFC)."""
    if code == "vi":
        from .lang import _has_vietnamese_letters

        return _has_vietnamese_letters
    return has_letters_of(code)


@cache
def _sentence_sets(code: str) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    """(main-language words, words of both, strong English, other English) of plain lower-case
    words (the lists above)."""
    strong = load_words("latin", "function_en")
    common = load_words("latin", "common_en")
    english = _english_words()
    main, native = load_words(code, "function"), load_words(code, "native")
    both = ((main | native) & english) | (native - main)
    return main - english, both, strong - both, common - both


EV_OTHER, EV_MAIN, EV_BOTH, EV_EN, EV_STRONG = range(5)


def word_evidence(core: str, tag: str, code: str) -> int:
    """EV_* of the core of a word that word_lang tagged tag ("en" or code) in mode code. "vi": the
    main-language words are those with Vietnamese letters, and a word tagged Vietnamese (a valid
    syllable, loanword or acronym) that is in an English list counts for neither."""
    key = core.lower().replace("’", "'")
    if code == "vi":
        if own_letters("vi")(core):
            return EV_MAIN
        strong, english = load_words("latin", "function_en"), _english_words()
        if tag == "vi":
            return EV_BOTH if key in english else EV_OTHER
        return EV_STRONG if key in strong else EV_EN
    if has_letters_of(code)(core):
        return EV_MAIN
    main, both, strong, common = _sentence_sets(code)
    if key in main:
        return EV_MAIN
    if key in both:
        return EV_BOTH
    if key in strong:
        return EV_STRONG
    return EV_EN if tag == "en" or key in common else EV_OTHER


def sentence_is_english(tags: list[tuple[str, str]], code: str, core: Callable[[str], str]) -> bool:
    """tags: (chunk, "en" | code | "neutral") of one sentence; core strips a chunk's edges."""
    n = n_en = n_strong = n_main = runs = 0
    prev = False
    for chunk, tag in tags:
        if tag == "neutral":
            continue
        e = word_evidence(core(chunk), tag, code)
        n += e != EV_BOTH
        n_en += e >= EV_EN
        n_strong += e == EV_STRONG
        n_main += e == EV_MAIN
        runs += e >= EV_EN and not prev
        prev = e >= EV_EN
    return (n_en >= SENT_MIN_EN and n_strong >= 1 and n_en > SENT_EN_PER_MAIN * n_main
            and 4 * n_en >= n and (2 * n_en >= n or runs >= 2))


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
