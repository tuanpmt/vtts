"""Tagalog word -> tl-en tokens (spelling rules, glottal stops, stress).

Tagalog spelling (the Filipino alphabet) is nearly phonemic; what it leaves out is the stress and
the glottal stop. The rules:

- Letters: ng is one sound (ng), mga is read "manga" and the particle ng is read "nang"; c is s
  before e/i and k elsewhere, qu before e/i and q are k, ch and ts are ch (tsinelas), sh is sh,
  j is j (dyip is d y), ll is l y (Villa), ñ is n y (Niño), x is k s; f, v, z stay (loanwords).
  A doubled consonant letter is read once. e/i and o/u are kept as written.
- Glottal stop ?: between two vowels (tao -> ta?o, kain -> ka?in, maaari), after a hyphen or an
  apostrophe before a vowel (mag-aral, the normalizer writes mag'aral), and at the end of a word
  with a final glottal stop (bata? "child", hindi?). A word-initial glottal onset is not written.
  The contractions 't and 'y (dalawampu't, ako'y) add a consonant without a syllable.
- Stress and final glottal stop are not written in everyday text. Default: the second-to-last
  syllable (malumay), no final glottal stop. Words read otherwise are respelled in
  lexicons/tl/stress.tsv with the Filipino accent marks, which are also read when the text has
  them: an acute accent marks the stressed vowel (mabilis: akó, gandá; or any other syllable),
  a grave accent on the final vowel a final glottal stop with the default stress (malumi: batà,
  lupà), a circumflex on the final vowel a stressed final vowel with a glottal stop (maragsa:
  hindî, walâ).
- Affixed forms: a word not in the table is looked up without the linker -ng and the
  contractions 't/'y (same syllables, no final glottal stop: isá -> isáng), then without prefixes
  (mag- nag- pag- ma- na- pa- ka- ipa- maka- naka- paka- makapag- nakapag- pinaka- ...) and the
  infixes -um-/-in- (k-um-ain), keeping the root's stress counted from the end and its final
  glottal stop; with a suffix (-an -in -han -hin -nan -nin) a root with final stress keeps the
  stress on the last syllable and every other root takes the default.
- Function words (UNSTRESSED: ang, ng, sa, ay, at, mga ...) are not stressed.

valid_spelling() says whether a plain ASCII word could be Tagalog (latin.py uses it to tell
Tagalog from English words).
"""

from __future__ import annotations

import functools
import re
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

VOWELS = "aeiou"
ACUTE, GRAVE, CIRCUMFLEX = "\u0301", "\u0300", "\u0302"
UNSTRESSED = frozenset(("ang", "ng", "nang", "sa", "si", "ni", "kay", "ay", "at", "na", "mga", "ko",
                        "mo", "ka", "ba", "pa", "din", "rin", "daw", "raw", "po", "ho", "may", "o",
                        "kung", "nga", "lang", "man", "sina", "nina", "kina", "yung", "pag"))
PREFIXES = ("makapag", "nakapag", "pinaka", "magpa", "nagpa", "pagpa", "maki", "naki", "paki",
            "maka", "naka", "paka", "ipa", "mag", "nag", "pag", "ma", "na", "pa", "ka", "i")
SUFFIXES = ("han", "hin", "nan", "nin", "an", "in")
CLITICS = ("ng", "'t", "'y")


@functools.cache
def stress_table() -> dict[str, str]:
    return load_table("tl", "stress")


def fold(word: str) -> str:
    """Lower case, NFD: accents on vowels kept as combining marks (stress and glottal marks), ñ
    kept, other accents dropped; apostrophes kept."""
    out = []
    for ch in unicodedata.normalize("NFD", word.lower()):
        if "a" <= ch <= "z" or ch in "'-" or ch in (ACUTE, GRAVE, CIRCUMFLEX) and out and out[-1] in VOWELS:
            out.append(ch)
        elif ch == "\u0303" and out and out[-1] == "n":
            out[-1] = "ñ"
    return "".join(out).strip("-")


def _plain(w: str) -> str:
    return "".join(ch for ch in w if ch not in (ACUTE, GRAVE, CIRCUMFLEX))


def _pattern(spelled: str) -> tuple[int | None, bool]:
    """(stressed syllable counted from the end (1 = last) or None for the default, final glottal
    stop) of a word written with accent marks."""
    nuclei = [k for k, ch in enumerate(spelled) if ch in VOWELS]
    stress, glottal = None, False
    for n, k in enumerate(nuclei):
        mark = spelled[k + 1:k + 2]
        if mark == ACUTE:
            stress = len(nuclei) - n
        elif mark == CIRCUMFLEX:
            stress, glottal = len(nuclei) - n, True
        elif mark == GRAVE and n == len(nuclei) - 1:
            glottal = True
    return stress, glottal


def _lookup(w: str) -> tuple[int | None, bool] | None:
    """The stress pattern of a word with no accent marks from the table: the word, the word
    without a clitic, or its root without prefixes, infixes and suffixes."""
    table = stress_table()
    if w in table:
        return _pattern(fold(table[w]))
    for c in CLITICS:
        if w.endswith(c) and len(w) > len(c) + 1:
            base = w[:-len(c)]
            if c != "ng" or base[-1] in VOWELS:
                found = _lookup(base)
                return (found[0], False) if found else None
    for root, suffix in _roots(w):
        if root in table:
            stress, glottal = _pattern(fold(table[root]))
            if not suffix:
                return stress, glottal
            return (1 if stress == 1 else None), False
    return None


def _roots(w: str) -> list[tuple[str, bool]]:
    """(root, has a suffix) candidates: prefixes, the infixes -um-/-in-, suffixes."""
    out = []
    stems = [w]
    for _ in range(2):  # up to two prefixes (na-paka-ganda)
        stems += [s[len(p):] for s in stems for p in PREFIXES if s.startswith(p) and len(s) - len(p) >= 3]
    stems = list(dict.fromkeys(stems))
    for s in list(stems):
        if len(s) > 4 and s[0] not in VOWELS and s[1:3] in ("um", "in") and s[3] in VOWELS:
            stems.append(s[0] + s[3:])
        if s[:2] in ("um", "in") and len(s) > 4 and s[2] in VOWELS:
            stems.append(s[2:])
    for s in stems:
        if s != w:
            out.append((s, False))
        for suf in SUFFIXES:
            if s.endswith(suf) and len(s) - len(suf) >= 2:
                out.append((s[:-len(suf)], True))
    return out


def _segments(w: str) -> list[list[str]]:
    """["C", phoneme] or ["V", vowel, mark] per sound of a folded word (marks: "", acute ...)."""
    out: list[list[str]] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        nxt = w[i + 1:i + 2]
        if c in VOWELS:
            mark = w[i + 1] if i + 1 < n and w[i + 1] in (ACUTE, GRAVE, CIRCUMFLEX) else ""
            if out and out[-1][0] == "V":
                out.append(["C", "?"])
            out.append(["V", c, mark])
            i += 2 if mark else 1
            continue
        if c in "'-":
            if out and nxt in tuple(VOWELS):
                out.append(["C", "?"])
            i += 1
            continue
        two = w[i:i + 2]
        if two == "ng":
            out.append(["C", "ng"])
            i += 2
            continue
        if two in ("ch", "ts"):
            out.append(["C", "ch"])
            i += 2
            continue
        if two == "sh":
            out.append(["C", "sh"])
            i += 2
            continue
        if two == "ll":
            out += [["C", "l"], ["C", "y"]]
            i += 2
            continue
        if two == "qu" and w[i + 2:i + 3] in ("e", "i"):
            out.append(["C", "k"])
            i += 2
            continue
        if i and c == w[i - 1] and c != "'" and w[i - 2:i] != "ng":  # ngg = ng + g
            i += 1  # doubled consonant letter
            continue
        if c == "c":
            out.append(["C", "s" if nxt in ("e", "i") else "k"])
        elif c == "q":
            out.append(["C", "k"])
        elif c == "x":
            out += [["C", "k"], ["C", "s"]]
        elif c == "ñ":
            out += [["C", "n"], ["C", "y"]]
        else:
            out.append(["C", c])
        i += 1
    return out


SPECIAL = {"ng": ("n", "a", "ng"), "mga": ("m", "a", "ng", "a")}
# Spanish loanwords keep the Spanish final stress: -yon after two syllables (rehiyon, telebisyon;
# not nayon), -dad (siyudad),
# -al after y n t in words of three or more syllables (opisyal, nasyonal, kapital) and -ar,
# -el, -or (militar, papel, doktor; native words rarely end in r or el).
SPANISH_FINAL = re.compile(r"(?:[aeiou][^aeiou]*[aeiou][^aeiou]*(?:yon|[ynt]al)|dad|[aeiou][^aeiou]*(?:ar|el|or))$")


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('bata' -> b a1 t a; 'batà' -> b a1 t a ?), without the TL: prefix."""
    w = fold(word)
    plain = _plain(w)
    if plain in SPECIAL:
        return SPECIAL[plain]
    if not plain.strip("'-"):
        return ()
    if w == plain and plain in stress_table():  # whole-word entry: its letters and marks
        w = fold(stress_table()[plain])
    marked = w != plain
    pattern = _pattern(w) if marked else _lookup(plain)
    stress_from_end, glottal = pattern if pattern else (None, False)
    segs = _segments(w if marked else plain)
    nuclei = [k for k, s in enumerate(segs) if s[0] == "V"]
    stress = None
    if nuclei and plain not in UNSTRESSED:
        if stress_from_end:
            back = stress_from_end
        elif len(nuclei) > 1 and pattern is None and SPANISH_FINAL.search(plain):
            back = 1
        else:
            back = 2 if len(nuclei) > 1 else 1
        stress = nuclei[max(0, len(nuclei) - back)]
    out = [s[1] + ("1" if k == stress else "") for k, s in enumerate(segs)]
    if glottal and segs and segs[-1][0] == "V":
        out.append("?")
    return tuple(out)


def word_tokens_tl(word: str) -> list[str]:
    """tl-en tokens of one word; a word without a vowel (km, ng excepted) is spelled letter by
    letter."""
    w = _plain(fold(word))
    if w and w not in SPECIAL and not any(ch in VOWELS for ch in w):
        from .normalize_tl import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for t in word_tokens_tl(NAMES[ch])]
    return [f"TL:{p}" for p in phonemes(word)]


# ---------------- spelling check (Tagalog or English?) ----------------

ONSETS = frozenset(["pr", "tr", "kr", "gr", "br", "dr", "bl", "kl", "gl", "pl", "fl", "fr", "sw",
                    "kw", "gw", "tw", "dw", "bw", "pw", "ky", "gy", "ty", "dy", "sy", "ny", "py",
                    "by", "my", "ly", "ry", "hy", "vy", "ly", "ts", "sp", "st", "sk", "tsy", "Ny",
                    "Nw"])
CODAS = frozenset("bdgklmnprstwyhN")
FINALS = frozenset("bdgklmnprstwyhN") | {"ks", "ts"}
FOREIGN = ("th", "sh", "ph", "ck", "gh", "wh", "ee", "oo", "ou", "ea", "q", "x", "c", "v", "z",
           "f", "j")
DOUBLES = frozenset(("aa", "ii", "uu"))
# Native words with oo (two syllables: lo-ob, do-on); oo is otherwise an English letter group.
NATIVE_OO = ("loob", "look", "doon", "roon", "noon", "poot")


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Tagalog spelling: the letters of the Abakada and
    common loanword clusters (pr tr ky dy sy kw ts ...), no English letter groups or the letters
    c f j q v x z (Tagalog writes k s h p b), no doubled letters other than aa ii uu (maaari)
    and the oo of NATIVE_OO (loob, doon, kalooban),
    one consonant (or ng) at the end of a word (no "nd", "rt"), y only next to a vowel."""
    if w in ("t", "y"):  # the contractions 't, 'y (dalawampu't, ako'y)
        return True
    if not w or not w.isascii() or not w.replace("-", "").isalpha():
        return False
    w = w.replace("-", "")
    for native in NATIVE_OO:
        w = w.replace(native, native.replace("oo", "o"))
    if any(f in w for f in FOREIGN):
        return False
    if any(a == b and a + b not in DOUBLES for a, b in pairwise(w.replace("ngg", "ng"))):
        return False
    w = w.replace("ng", "N")
    runs = consonant_runs(w, y_vowel=False)
    return runs is not None and clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_tl(text: str) -> list[str]:
    """Letters the Tagalog front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded and are readable."""
    return [ch for ch in text if ch.isalpha() and not _plain(fold(ch)).strip("'-")]
