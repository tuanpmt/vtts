"""Parse one written Vietnamese syllable into onset / glide / nucleus / coda / tone.

Written from the standard description of Vietnamese orthography (onset, optional
labial on-glide, nucleus, optional coda or off-glide, tone carried by one
diacritic). Pure spelling variants are merged (c/k/q, g/gh, ng/ngh, iê/yê/ia/ya,
uô/ua, ươ/ưa); spellings that some dialects pronounce differently are kept apart
(tr/ch, s/x, r/d/gi, final n/ng, t/c).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Combining tone marks after NFD -> tone number (1 = ngang, unmarked).
_TONE_MARKS = {
    "̀": 2,  # huyền
    "́": 3,  # sắc
    "̉": 4,  # hỏi
    "̃": 5,  # ngã
    "̣": 6,  # nặng
}

_ALPHABET = frozenset("abcdđeghiklmnopqrstuvxyăâêôơưfjwz")
_VOWELS = frozenset("aăâeêioôơuưy")

# Written onset -> onset name. Longest match wins.
_ONSETS = {
    "ngh": "ng", "ng": "ng", "gh": "g", "gi": "gi", "ch": "ch", "tr": "tr", "th": "th",
    "ph": "ph", "kh": "kh", "nh": "nh",
    "b": "b", "c": "k", "k": "k", "d": "d", "đ": "đ", "g": "g", "h": "h", "l": "l",
    "m": "m", "n": "n", "p": "p", "r": "r", "s": "s", "t": "t", "v": "v", "x": "x",
    # letters outside the native alphabet, approximated by spelling
    "f": "ph", "w": "v", "z": "d", "j": "gi",
}
_MAX_ONSET = 3

_CODAS = ("ng", "nh", "ch", "c", "m", "n", "p", "t")

# Vowel cluster -> (nucleus, off-glide coda or None, needs_no_consonant_coda)
_VOWEL_CLUSTERS: dict[str, tuple[str, str | None, bool]] = {
    "a": ("a", None, False), "ă": ("ă", None, False), "â": ("â", None, False),
    "e": ("e", None, False), "ê": ("ê", None, False), "i": ("i", None, False),
    "y": ("i", None, False), "o": ("o", None, False), "ô": ("ô", None, False),
    "ơ": ("ơ", None, False), "u": ("u", None, False), "ư": ("ư", None, False),
    "oo": ("oo", None, False), "ôô": ("ô", None, False),
    "iê": ("iê", None, False), "yê": ("iê", None, False),
    "ia": ("iê", None, True), "ya": ("iê", None, True),
    "uô": ("uô", None, False), "ua": ("uô", None, True),
    "ươ": ("ươ", None, False), "ưa": ("ươ", None, True),
    # off-glides
    "ai": ("a", "j", True), "ay": ("ă", "j", True), "ây": ("â", "j", True),
    "ao": ("a", "w", True), "au": ("ă", "w", True), "âu": ("â", "w", True),
    "eo": ("e", "w", True), "êu": ("ê", "w", True), "iu": ("i", "w", True),
    "yu": ("i", "w", True),
    "oi": ("o", "j", True), "ôi": ("ô", "j", True), "ơi": ("ơ", "j", True),
    "ui": ("u", "j", True), "ưi": ("ư", "j", True), "ưu": ("ư", "w", True),
    "iêu": ("iê", "w", True), "yêu": ("iê", "w", True),
    "ươi": ("ươ", "j", True), "ươu": ("ươ", "w", True), "uôi": ("uô", "j", True),
}


@dataclass(frozen=True)
class Syllable:
    onset: str | None
    glide: bool
    nucleus: str
    coda: str | None
    tone: int


def _split_tone(word: str) -> tuple[str, int] | None:
    decomposed = unicodedata.normalize("NFD", word.lower())
    tone = 1
    kept = []
    for ch in decomposed:
        if ch in _TONE_MARKS:
            if tone != 1:
                return None  # two tone marks
            tone = _TONE_MARKS[ch]
        else:
            kept.append(ch)
    return unicodedata.normalize("NFC", "".join(kept)), tone


def _split_onset(base: str) -> tuple[str | None, bool, str]:
    """Return (onset, glide_from_qu, rest)."""
    if base.startswith("qu") and len(base) > 2:
        return "k", True, base[2:]
    for size in range(_MAX_ONSET, 0, -1):
        head = base[:size]
        if head in _ONSETS and (len(base) > size or (head == "gi" and base == "gi")):
            rest = base[size:]
            if head == "gi":
                # gì, gìn: the i is the nucleus; giếng: the i opens iê.
                if not any(c in _VOWELS for c in rest) or rest.startswith("ê"):
                    rest = "i" + rest
            if any(c in _VOWELS for c in rest[:1]):
                return _ONSETS[head], False, rest
    return None, False, base


def _split_glide(rest: str) -> tuple[bool, str]:
    if len(rest) >= 2:
        if rest[0] == "o" and rest[1] in "aăe":
            return True, rest[1:]
        if rest[0] == "u" and rest[1] in "êyâơ":
            return True, rest[1:]
    return False, rest


def parse_syllable(word: str) -> Syllable | None:
    if not word:
        return None
    split = _split_tone(word)
    if split is None:
        return None
    base, tone = split
    if not base or any(c not in _ALPHABET for c in base):
        return None

    onset, glide, rest = _split_onset(base)
    if not glide:
        glide, rest = _split_glide(rest)

    coda = None
    for cand in _CODAS:
        if rest.endswith(cand) and len(rest) > len(cand):
            coda = cand
            rest = rest[: -len(cand)]
            break

    cluster = _VOWEL_CLUSTERS.get(rest)
    if cluster is None:
        return None
    nucleus, offglide, open_only = cluster
    if offglide is not None or open_only:
        if coda is not None:
            return None
        if offglide is not None:
            coda = offglide
    return Syllable(onset, glide, nucleus, coda, tone)


_QUALITY = frozenset("ăâêôơư")
_TONE_BY_NUMBER = {v: k for k, v in _TONE_MARKS.items()}


def canonical_spelling(word: str) -> str:
    """Lowercase NFC spelling with the tone mark on the modern-style position.

    "hòa"/"hoà" -> "hoà", "thủy"/"thuỷ" -> "thuỷ". Only meaningful for words that
    parse as a syllable; other input is returned lowercased and NFC.
    """
    split = _split_tone(word)
    if split is None:
        return unicodedata.normalize("NFC", word.lower())
    base, tone = split
    if tone == 1:
        return base
    p = 0
    while p < len(base) and base[p] not in _VOWELS:
        p += 1
    if p < len(base) and p > 0:
        if base[p - 1] == "q" and base[p] == "u" or base[p - 1] == "g" and base[p] == "i" and p + 1 < len(base) and base[p + 1] in _VOWELS:
            p += 1
    e = p
    while e < len(base) and base[e] in _VOWELS:
        e += 1
    run = list(range(p, e))
    if not run:
        return unicodedata.normalize("NFC", word.lower())
    quality = [i for i in run if base[i] in _QUALITY]
    if quality:
        target = quality[-1]
    elif e < len(base) or len(run) == 1:
        target = run[-1]
    elif len(run) == 3 or base[p:e] in ("oa", "oe", "uy"):
        target = run[1]
    else:
        target = run[0]
    marked = base[: target + 1] + _TONE_BY_NUMBER[tone] + base[target + 1:]
    return unicodedata.normalize("NFC", marked)
