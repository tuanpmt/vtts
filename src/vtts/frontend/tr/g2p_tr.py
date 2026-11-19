"""Turkish word -> tr-en tokens (letters, ğ and long vowels, stress).

Turkish spelling is close to phonemic (vowel harmony is already written), so a word is read
letter by letter after Turkish lower-casing (I -> ı, İ -> i, see tr_lower):

- c -> c (dʒ), ç -> ch, ş -> sh, j -> zh, y -> y; ö ü ı -> oe ue I; q x w (loanwords) -> k, k s, v.
- â î û: a long vowel (hâlâ, millî); after k g, â and û also make the consonant palatal
  (kâr -> ky a long, rüzgâr -> gy a long). A doubled letter is two phonemes (anne, dikkat).
- ğ after a vowel: before a consonant or at the end it lengthens the vowel (dağ, yağmur); between
  two front vowels it is y (değil, eğer); between other vowels it lengthens the first one, and two
  equal vowels merge into one long vowel (ağaç, soğuk).
- Stress: the last syllable (Turkish default), except:
  - lexicons/tr/overrides.tsv respells words with a stress mark ˈ before the stressed vowel (place
    names Ankara, İstanbul, loanwords masa, lokanta, adverbs şimdi, sonra, evet); an entry also
    applies to the word with case, plural and possessive suffixes (masada, Ankara'dan);
  - a suffix after an apostrophe (İstanbul'da, Ahmet'in) is not stressed: the name keeps its own
    stress;
  - before -yor the stress is on the vowel before it (geliyor), before the negative -m(a/e/ı/i...)
    + yor / + dı on the syllable before the negative (gelmiyor, gelmedi), before a final copula
    -dır/-tir and a final -yla/-yle on the syllable before it (şehirdir, olmuştur, amacıyla);
  - clitics and particles (mi mı mu mü and their forms, de da, ki, ile, ve) have no stress.

valid_spelling() says whether a plain ASCII word could be Turkish (latin.py uses it to tell
Turkish from English words).
"""

from __future__ import annotations

import functools
import re
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

VOWELS = "aeıioöuü"
LONG_VOWELS = {"â": "a", "î": "i", "û": "u"}
FRONT = "eiöü"
LETTERS = frozenset("abcçdefgğhıijklmnoöprsştuüvyzqwxâîû")
FOLD = {"ä": "e", "ß": "s", "ł": "l", "æ": "e", "ø": "ö", "œ": "ö", "ñ": "n"}
PHONEME = {"a": "a", "e": "e", "ı": "I", "i": "i", "o": "o", "ö": "oe", "u": "u", "ü": "ue",
           "c": "c", "ç": "ch", "ş": "sh", "j": "zh", "q": "k", "w": "v"}
STRESS_MARK = "ˈ"
SUFFIX_MARK = "\u02bc"  # ʼ: normalize_tr writes the apostrophe before a lone suffix ('da) as this mark

UNSTRESSED = frozenset((
    "de", "da", "ki", "ile", "ve", "ya", "veya", "ise", "bile",
))
# Question particle mi with its person and tense endings (mi, mısın, miyiz, muydu ...).
QUESTION = re.compile(r"^m[ıiuü](y[ıiuü]m|s[ıiuü]n|y[ıiuü]z|s[ıiuü]n[ıiuü]z|l[ae]r|yd[ıiuü]"
                      r"(m|n|k|n[ıiuü]z|l[ae]r)?|ym[ıiuü]ş|ys[ae])?$")
# Suffixes an override entry may take (masa-da, Ankara-dan, Türkiye-nin, Avrupa-lı-lar).
SUFFIX = re.compile(r"^(l[ıiuü])?(l[ae]r)?(y?[ıiuü]m?|n?[ıiuü]n|s[ıiuü]n?|y?[ae]|n?[dt][ae]n?|"
                    r"n?[dt][ae]ki|y?l[ae]|[ıiuü]m[ıiuü]z|[ıiuü]n[ıiuü]z|n[ıiuü]n|y?d[ıiuü]r)?$")
YOR = re.compile(r"[ıiuü]yor")
NEG_YOR = re.compile(r"(?<=[^aeıioöuü])m[ıiuü]yor")
NEG_PAST = re.compile(r"(?<=[bcçdfgğhjklmnprsştvyz])m[ae]d[ıi]")
# the copula: -tır after a voiceless consonant, -dır after a vowel or a voiced one (vardır,
# olmuştur, biridir; not kültür)
COPULA = re.compile(r"((?<=[çfhkpsşt])t|(?<=[aeıioöuüâîûbcdgğjlmnrvyz])d)[ıiuü]r$")
WITH = re.compile(r"(?<=[aeıioöuü])yl[ae]$")  # amacıyla, yoluyla (ile as a suffix)


def tr_lower(text: str) -> str:
    """Turkish lower case: I -> ı, İ -> i (no combining dot), then the usual lower case."""
    return text.replace("I", "ı").replace("İ", "i").lower().replace("i̇", "i")


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("tr", "overrides")


def fold(word: str) -> str:
    """Turkish lower case, Turkish letters (and the stress mark) kept, other accented letters
    reduced to their base letter (é -> e, ä -> e)."""
    out = []
    for ch in tr_lower(word):
        if ch in LETTERS or ch == STRESS_MARK:
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _segments(w: str) -> tuple[list[list], int | None]:
    """(["V", vowel, long] or ["C", phoneme] per sound, index of a marked stressed vowel)."""
    out: list[list] = []
    marked = None
    n = len(w)
    i = 0
    while i < n:
        c = w[i]
        nxt = w[i + 1] if i + 1 < n else ""
        if c == STRESS_MARK:
            marked = len(out)
        elif c in VOWELS:
            out.append(["V", PHONEME[c], False])
        elif c in LONG_VOWELS:
            v = LONG_VOWELS[c]
            if out and out[-1] == ["C", "k"] and c in "âû":
                out[-1] = ["C", "ky"]
            elif out and out[-1] == ["C", "g"] and c in "âû":
                out[-1] = ["C", "gy"]
            out.append(["V", v, True])
        elif c == "ğ":
            prev = out[-1] if out and out[-1][0] == "V" else None
            if prev is not None:
                if nxt and nxt in VOWELS:
                    if w[i - 1] in FRONT and nxt in FRONT:
                        out.append(["C", "y"])
                    else:
                        prev[2] = True
                        if PHONEME[nxt] == prev[1]:
                            i += 1  # ağaç: two equal vowels are one long vowel
                else:
                    prev[2] = True
        elif c == "x":
            out += [["C", "k"], ["C", "s"]]
        else:
            out.append(["C", PHONEME.get(c, c)])
        i += 1
    if marked is not None:  # the mark stands before the vowel (or its onset consonant)
        while marked < len(out) and out[marked][0] != "V":
            marked += 1
        marked = marked if marked < len(out) else None
    return out, marked


def _stress(w: str, segs: list[list], marked: int | None) -> int | None:
    nuclei = [k for k, s in enumerate(segs) if s[0] == "V"]
    if not nuclei or w in UNSTRESSED or QUESTION.match(w):
        return None
    if marked is not None:
        return marked
    if len(nuclei) == 1:
        return nuclei[0]
    # pre-stressing suffixes: the vowel before the negative -m(a/e/ı/i...) + yor / + dı (gelmiyor,
    # gelmedi), the vowel of -(ı/i/u/ü)yor (geliyor), the vowel before the copula -dır/-tir
    # (şehirdir, olmuştur) and before -(y)la/-(y)le (amacıyla)
    for pattern, offset in ((NEG_YOR, -1), (NEG_PAST, -1), (YOR, 0), (COPULA, -1), (WITH, -1)):
        m = pattern.search(w)
        if m:
            k = sum(ch in VOWELS or ch in LONG_VOWELS for ch in w[:m.start()]) + offset
            if 0 <= k < len(nuclei):
                return nuclei[k]
    return nuclei[-1]


def _read(w: str, stressed: bool = True) -> list[str]:
    segs, marked = _segments(w)
    stress = _stress(w.replace(STRESS_MARK, ""), segs, marked) if stressed else None
    out = []
    for k, s in enumerate(segs):
        if s[0] == "C":
            out.append(s[1])
            continue
        out.append(s[1] + ("1" if k == stress else ""))
        if s[2]:
            out.append("long")
    return out


def _with_override(w: str) -> str:
    """The respelling of w, or of a stem in the table plus a suffix (masada -> ˈmasada)."""
    table = override_table()
    if w in table:
        return table[w]
    for k in range(len(w) - 1, 2, -1):
        stem, rest = w[:k], w[k:]
        if stem in table and SUFFIX.match(rest):
            return table[stem] + rest
    return w


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('İstanbul'da' -> i s t a1 n b u l d a), without the TR: prefix."""
    head, _, suffix = word.replace("’", "'").partition("'")
    head, suffix = fold(head), fold(suffix)
    if not head:
        return tuple(_read(suffix, stressed=False)) if suffix else ()
    out = _read(_with_override(head))
    if suffix:  # İstanbul'da, Ahmet'in: the name keeps its stress, the suffix has none
        if head == "dört" and suffix[0] in VOWELS:
            out[-1] = "d"
        out += _read(suffix, stressed=False)
    return tuple(out)


def word_tokens_tr(word: str) -> list[str]:
    """tr-en tokens of one word; a word without a vowel (km, ptt) is spelled letter by letter."""
    if word.startswith(SUFFIX_MARK):  # a suffix after an English word (iPhone'da): no stress
        return [f"TR:{p}" for p in _read(fold(word), stressed=False)]
    w = fold(word.replace("'", "").replace("’", ""))
    if w and not any(ch in VOWELS or ch in LONG_VOWELS for ch in w):
        from .normalize_tr import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_tr(n)]
    return [f"TR:{p}" for p in phonemes(word)]


# ---------------- spelling check (Turkish or English?) ----------------

ONSETS = frozenset(["tr", "pr", "pl", "kr", "kl", "gr", "gl", "br", "bl", "fl", "fr", "dr", "sp", "st",
                    "sk", "sf"])
FINALS = frozenset("bcdfghjklmnprstvyz") | {"rk", "rt", "rs", "rp", "rm", "rn", "rf", "rz", "lk", "lt",
                                            "lp", "lm", "ls", "lf", "nt", "nk", "ns", "nz", "ft", "st",
                                            "sk", "ks", "kt", "ps", "pt", "zm", "sm", "rh", "lh", "yt",
                                            "yk", "yn", "yl", "yr", "ym", "ys", "mt", "ht"}
CODAS = FINALS  # inside a word a syllable may end like a word (ders-le-ri, film-de, aks-iyon)
FOREIGN = ("th", "sh", "ch", "ph", "ck", "gh", "wh", "w", "q", "x", "oo", "ee", "ea", "ou", "oa", "ie",
           "ue", "ui", "tch")


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Turkish spelling: no q w x or English letter groups
    (th sh ch ck ng nd, oo ee ea ou ie), no doubled vowels other than aa ii (saat, şiir), onsets of
    one consonant or a common loan cluster (tr pr kr gr st sp ...), codas of one consonant inside a
    word, and a vowel, one consonant or a Turkish final cluster (rk nt st ...) at the end."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(f in w for f in FOREIGN):
        return False
    if any(a == b and a in "eouy" for a, b in pairwise(w)):
        return False
    runs = consonant_runs(w, vowels="aeiou", y_vowel=False)
    return runs is not None and clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_tr(text: str) -> list[str]:
    """Letters the Turkish front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
