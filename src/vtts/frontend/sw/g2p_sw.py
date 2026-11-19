"""Swahili word -> sw-en tokens (spelling rules, syllabic nasals, penultimate stress).

Swahili spelling is phonemic. The rules:

- Letters: ch, sh, ny, th, dh, gh, kh are one sound each; ng' is the velar nasal ng (ng'ombe);
  the prenasalized stops mb, nd, nj and ng (= ng + g: ngoma) are one token each; nz is n + z.
  A doubled consonant letter other than nn, mm is read once (Allah); c (outside ch) and q are k,
  x is k s.
- Every vowel is a syllable nucleus (kiatu = ki-a-tu, kaa = ka-a). A word-initial m before a
  consonant other than b, w, y and a word-initial n before a consonant other than d, j, g, y, z, '
  are syllabic (m-tu, m-to-to, m-zee, n-chi, n-ne): they count as a syllable but have no vowel
  token. Inside a word a nasal before a consonant closes the syllable before it (kaunti, jinsi).
- Stress: the second-to-last syllable (ki-TA-bu, m-TO-to); when that is a syllabic nasal (m-tu,
  n-chi) no vowel is marked. lexicons/sw/stress.tsv lists the few words stressed elsewhere
  (respelled with an acute accent on the stressed vowel). Function words (UNSTRESSED: na, ya,
  wa, kwa, ni ...) are not stressed.

valid_spelling() says whether a plain ASCII word could be Swahili (latin.py uses it to tell
Swahili from English words).
"""

from __future__ import annotations

import functools
import re
import unicodedata

from ..lexicons import load_table

VOWELS = "aeiou"
ACUTE = "\u0301"
UNSTRESSED = frozenset(("na", "ya", "wa", "kwa", "ni", "la", "za", "cha", "vya", "si", "pa", "mwa",
                        "ku", "li", "ma"))
DIGRAPHS = ("ng'", "ch", "sh", "ny", "th", "dh", "gh", "kh", "mb", "nd", "nj", "ng")
SOUND = {"ng'": "ng", "ng": "ngg"}


@functools.cache
def stress_table() -> dict[str, str]:
    return load_table("sw", "stress")


def fold(word: str) -> str:
    """Lower case; ’ to '; an acute accent on a vowel kept (stress mark), other accents dropped."""
    out = []
    for ch in unicodedata.normalize("NFD", word.lower().replace("’", "'")):
        if "a" <= ch <= "z" or ch == "'" or ch == ACUTE and out and out[-1] in VOWELS:
            out.append(ch)
    return "".join(out)


def _segments(w: str) -> list[list[str]]:
    """["C", phoneme], ["V", vowel, stressed] or ["N", nasal] (syllabic) per sound."""
    out: list[list[str]] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        if c in VOWELS:
            marked = w[i + 1:i + 2] == ACUTE
            out.append(["V", c, "1" if marked else ""])
            i += 2 if marked else 1
            continue
        if c in "'" or c == ACUTE:
            i += 1
            continue
        if c in "mn" and i == 0 and n > 1 and w[1] not in VOWELS and w[1] != "'":
            nxt = w[i + 1]
            if (c == "m" and nxt not in "bwy") or (c == "n" and nxt not in "djgyz"):
                out.append(["N", c])
                i += 1
                continue
        d = next((d for d in DIGRAPHS if w.startswith(d, i)), None)
        if d:
            out.append(["C", SOUND.get(d, d)])
            i += len(d)
            continue
        if i and c == w[i - 1] and c not in "mn" and out and out[-1][0] == "C":
            i += 1  # doubled consonant letter; nn, mm are both read (nne, wanne, mmea)
            continue
        if c == "x":
            out += [["C", "k"], ["C", "s"]]
        else:
            out.append(["C", {"c": "k", "q": "k"}.get(c, c)])
        i += 1
    return out


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('kitabu' -> k i t a1 b u), without the SW: prefix."""
    w = fold(word)
    plain = w.replace(ACUTE, "")
    if plain in stress_table():
        w = fold(stress_table()[plain])
    segs = _segments(w)
    nuclei = [k for k, s in enumerate(segs) if s[0] in "VN"]
    stress = next((k for k, s in enumerate(segs) if s[0] == "V" and s[2]), None)
    if stress is None and nuclei and plain not in UNSTRESSED:
        k = nuclei[-2] if len(nuclei) > 1 else nuclei[-1]
        stress = k if segs[k][0] == "V" else None
    return tuple(s[1] + ("1" if k == stress else "") for k, s in enumerate(segs))


def word_tokens_sw(word: str) -> list[str]:
    """sw-en tokens of one word; a word without a vowel (km, kg) is spelled letter by letter."""
    w = fold(word).replace(ACUTE, "")
    if w and not any(ch in VOWELS for ch in w):
        from .normalize_sw import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for t in word_tokens_sw(NAMES[ch])]
    return [f"SW:{p}" for p in phonemes(word)]


# ---------------- spelling check (Swahili or English?) ----------------

CODES = (("ng'", "N"), ("ch", "C"), ("sh", "S"), ("ny", "J"), ("th", "T"), ("dh", "D"),
         ("gh", "G"), ("kh", "K"))
ENGLISH_LE = re.compile(r"[^aeiou']le$")  # single, table, simple


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Swahili spelling: it ends in a vowel (not in a
    consonant + le: single, table), has no c (outside ch), q or x, and every consonant run (digraphs
    ch sh ny th dh gh kh ng' counted as one) has at most three consonants, no h after another
    consonant (ph, wh) and no doubled consonant other than a syllabic mm, nn at its start (mmoja,
    nne). Native words and the many loanwords with clusters fit (mtoto, nchi, kabla, rasmi,
    klabu, takriban, binafsi)."""
    if not w or not w.isascii() or w[-1] not in VOWELS or not w.replace("'", "").isalpha():
        return False
    if ENGLISH_LE.search(w):
        return False
    for d, r in CODES:
        w = w.replace(d, r)
    if "'" in w or any(ch in w for ch in "cqx"):
        return False
    for run in re.findall(rf"[^{VOWELS}]+", w):
        if len(run) > 3 or "h" in run[1:]:
            return False
        if re.search(r"(.)\1", run[1:] if run[:2] in ("mm", "nn") else run):
            return False
    return True


def unreadable_sw(text: str) -> list[str]:
    """Letters the Swahili front-end cannot read (other scripts), to filter training sentences."""
    return [ch for ch in text if ch.isalpha() and not fold(ch).replace(ACUTE, "")]
