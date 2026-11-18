"""Brazilian Portuguese word -> pt-en tokens (spelling rules, nasal vowels, stress).

A word (lower case, after normalize_pt) is first replaced by its entry in lexicons/pt/overrides.tsv
(respellings with accents: é/ó mark an open stressed vowel, ê/ô a closed one, ü a pronounced u
after q/g, ks/ss for x), then read letter by letter:

- c before e/i and ç -> s, ch -> sh, c -> k; g before e/i and j -> zh, g -> g; gu/qu before e/i ->
  g/k (u silent), before a/o -> g w / k w; h is silent; lh -> lh, nh -> nh;
  r at the start of a word, after n, l, s, before a consonant or at the end, and rr -> rr
  (the strong r), else r (the tap); s between vowels -> z, ss, sc/sç before e/i -> s;
  x at the start -> sh, ex + vowel at the start -> z (exemplo), before a consonant -> s, at the
  end -> k s, else sh (caixa, lixo); z at the end -> s.
- Nasal vowels: ã, õ, and a vowel before m/n that close the syllable (campo, ponte); -am at the end
  of a word -> an w (falam), -em/-ens -> en j (tem, homem); ão -> an w, ãe -> an j, õe -> on j.
- Glides: an unaccented i/u after a vowel (pai, mau, muito, partiu) is j/w, except before a nasal
  coda, nh, or a final r l z (ainda, rainha, cair, Raul, juiz).
- Stress: the vowel with an acute or circumflex accent, else ã/õ, else the second-to-last vowel
  when the word ends in a, e, o (plus s), am, em, ens, else the last one; function words
  (UNSTRESSED) are not stressed. A stressed e/o is closed (e1 o1) unless written é/ó, followed by
  a final l (papel, sol), or in -ela(s) / -osa(s) / -osos (janela, famosa): then E1 / O1.
- An unstressed e/o at the end of a word (with an optional s) is read i/u (leite, carro, de, o).

valid_spelling() says whether a plain ASCII word could be Portuguese (latin.py uses it to tell
Portuguese from English words).
"""

from __future__ import annotations

import functools
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzáéíóúâêôãõàçü")
FOLD = {"ø": "o", "æ": "e", "œ": "e", "ß": "s", "ł": "l", "ñ": "n"}
BASE = {"á": ("a", "acute"), "é": ("e", "acute"), "í": ("i", "acute"), "ó": ("o", "acute"),
        "ú": ("u", "acute"), "â": ("a", "circ"), "ê": ("e", "circ"), "ô": ("o", "circ"),
        "ã": ("a", "tilde"), "õ": ("o", "tilde"), "à": ("a", None), "ü": ("u", None)}
VOWEL_LETTERS = "aeiou" + "".join(BASE)
FRONT = "eiéíê"
UNSTRESSED = frozenset((
    "o", "a", "os", "as", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "num",
    "numa", "por", "pelo", "pela", "pelos", "pelas", "para", "pra", "com", "sem", "que", "se",
    "me", "te", "lhe", "lhes", "vos", "e", "ou", "mas", "nem", "ao", "aos", "à", "às", "como",
    "quando", "onde",
))


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("pt", "overrides")


def fold(word: str) -> str:
    """Lower case, Portuguese letters kept, other accented letters reduced to their base letter."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _vowel(ch: str) -> list:
    base, accent = BASE.get(ch, (ch, None))
    return ["V", base, accent, ch == "ü"]  # kind, vowel, accent, written with diaeresis


def _segments(w: str) -> list[list]:
    """["V", vowel, accent, diaeresis] or ["C", phoneme] per letter group."""
    out: list[list] = []
    n = len(w)
    i = 0

    def at(k: int) -> str:
        return w[k] if 0 <= k < n else ""

    while i < n:
        c, nxt, nxt2 = w[i], at(i + 1), at(i + 2)
        step = 1
        if c in VOWEL_LETTERS or c == "y":
            out.append(_vowel("i" if c == "y" else c))
        elif c == "c":
            if nxt == "h":
                out.append(["C", "sh"])
                step = 2
            else:
                out.append(["C", "s" if nxt in FRONT else "k"])
        elif c == "ç":
            out.append(["C", "s"])
        elif c in "gq":
            if c == "g" and nxt in FRONT:
                out.append(["C", "zh"])
            else:
                out.append(["C", "g" if c == "g" else "k"])
                if nxt == "u" and nxt2 in FRONT:
                    step = 2  # u silent
                elif nxt == "ü" or (nxt == "u" and nxt2 and nxt2 in VOWEL_LETTERS):
                    out.append(["G", "w"])
                    step = 2
        elif c == "h":
            pass
        elif c == "j":
            out.append(["C", "zh"])
        elif c == "l" and nxt == "h":
            out.append(["C", "lh"])
            step = 2
        elif c == "n" and nxt == "h":
            out.append(["C", "nh"])
            step = 2
        elif c == "r":
            if nxt == "r":
                out.append(["C", "rr"])
                step = 2
            else:
                strong = i == 0 or at(i - 1) in "nls" or not (nxt and nxt in VOWEL_LETTERS)
                out.append(["C", "rr" if strong else "r"])
        elif c == "s":
            if nxt == "s" or (nxt == "c" and nxt2 in FRONT) or nxt == "ç":
                out.append(["C", "s"])
                step = 2
            elif at(i - 1) in VOWEL_LETTERS and at(i - 1) and nxt and nxt in VOWEL_LETTERS:
                out.append(["C", "z"])
            else:
                out.append(["C", "s"])
        elif c == "x":
            if i == 0:
                out.append(["C", "sh"])
            elif nxt == "c" and nxt2 in FRONT:  # exceção, excelente
                out.append(["C", "s"])
                step = 2
            elif i == 1 and at(0) in "eéê":
                out.append(["C", "z" if nxt and nxt in VOWEL_LETTERS else "s"])
            elif not nxt:
                out += [["C", "k"], ["C", "s"]]
            elif nxt not in VOWEL_LETTERS:
                out.append(["C", "s"])
            else:
                out.append(["C", "sh"])
        elif c == "z":
            out.append(["C", "s" if not nxt or nxt not in VOWEL_LETTERS else "z"])
        elif c == "w":
            out.append(["G", "w"])
        else:
            out.append(["C", c])
        i += step
    return out


def _nasalize(segs: list[list]) -> list[list]:
    """Vowel + m/n closing the syllable -> nasal vowel (final -am -> an w, -em/-ens -> en j);
    ã õ are nasal; the o of ão and the e of ãe/õe are glides."""
    out: list[list] = []
    k = 0
    while k < len(segs):
        s = segs[k]
        if s[0] == "V" and s[2] == "tilde":
            s = ["V", s[1], s[2], False, True]
            out.append(s)
            nxt = segs[k + 1] if k + 1 < len(segs) else None
            if nxt is not None and nxt[0] == "V" and nxt[2] is None and nxt[1] in "oe":
                out.append(["G", "w" if nxt[1] == "o" else "j"])
                k += 1
            k += 1
            continue
        if s[0] == "V":
            s = s + [False]
            nxt = segs[k + 1] if k + 1 < len(segs) else None
            after = segs[k + 2] if k + 2 < len(segs) else None
            if nxt is not None and nxt[0] == "C" and nxt[1] in ("m", "n") and (
                    after is None or after[0] == "C"):
                s[4] = True
                out.append(s)
                rest = segs[k + 2:]
                if (not rest or rest == [["C", "s"]]) and s[1] in "ae" and s[2] != "tilde" and (
                        s[1] == "e" or nxt[1] == "m"):
                    out.append(["G", "w" if s[1] == "a" else "j"])
                k += 2
                continue
            out.append(s)
            k += 1
            continue
        out.append(s)
        k += 1
    return out


def _glides(segs: list[list]) -> None:
    for k in range(1, len(segs)):
        s, prev = segs[k], segs[k - 1]
        if not (s[0] == "V" and s[1] in "iu" and s[2] is None and not s[3] and not s[4]
                and prev[0] == "V"):
            continue
        nxt = segs[k + 1] if k + 1 < len(segs) else None
        nxt2 = segs[k + 2] if k + 2 < len(segs) else None
        if nxt is not None and nxt[0] == "C" and (
                nxt[1] == "nh" or (nxt[1] in ("rr", "r", "l") and (nxt2 is None or nxt2[0] == "C"))):
            continue
        segs[k] = ["G", "j" if s[1] == "i" else "w"]


def _stress(w: str, segs: list[list], nuclei: list[int]) -> int | None:
    if not nuclei or w in UNSTRESSED:
        return None
    marked = [k for k in nuclei if segs[k][2] in ("acute", "circ")]
    if marked:
        return marked[-1]
    tilde = [k for k in nuclei if segs[k][2] == "tilde"]
    if tilde:
        return tilde[-1]
    if len(nuclei) == 1:
        return nuclei[0]
    penult = w.endswith(("a", "e", "o", "as", "es", "os", "am", "em", "ens"))
    return nuclei[-2] if penult else nuclei[-1]


def _quality(w: str, s: list) -> str:
    """Stressed e/o: E/O (open) or e/o (closed)."""
    if s[2] == "acute":
        return s[1].upper() if s[1] in "eo" else s[1]
    if s[2] == "circ" or s[1] not in "eo":
        return s[1]
    if s[1] == "e" and (w.endswith(("el", "els", "ela", "elas"))):
        return "E"
    if s[1] == "o" and (w.endswith(("ol", "ols", "osa", "osas", "osos"))):
        return "O"
    return s[1]


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('canção' -> k a n s an1 w), without the PT: prefix."""
    w = fold(word)
    w = fold(override_table().get(w, w))
    if not w:
        return ()
    segs = _nasalize(_segments(w))
    _glides(segs)
    nuclei = [k for k, s in enumerate(segs) if s[0] == "V"]
    stress = _stress(w, segs, nuclei)
    out = []
    for k, s in enumerate(segs):
        if s[0] != "V":
            out.append(s[1])
            continue
        if k == stress:
            v = s[1] if s[4] else _quality(w, s)
            out.append(v + ("n" if s[4] else "") + "1")
            continue
        v = s[1]
        if (not s[4] and v in "eo" and nuclei and k == nuclei[-1]
                and all(t[0] == "C" and t[1] == "s" for t in segs[k + 1:])):
            v = "i" if v == "e" else "u"
        out.append(v + ("n" if s[4] else ""))
    return tuple(out)


def word_tokens_pt(word: str) -> list[str]:
    """pt-en tokens of one word; a word without a vowel (km, pq) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in VOWEL_LETTERS or ch == "y" for ch in w):
        from .normalize_pt import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_pt(n)]
    return [f"PT:{p}" for p in phonemes(word)]


# ---------------- spelling check (Portuguese or English?) ----------------

ONSETS = frozenset(["pr", "br", "tr", "dr", "cr", "gr", "fr", "vr", "pl", "bl", "cl", "gl", "fl",
                    "tl", "ps", "pn", "gn", "mn"])
CODAS = frozenset("lrsmnxcpbdgtf") | {"ns", "rs", "bs"}
FINALS = frozenset("srlzmxn") | {"ns"}
DOUBLES = frozenset(["rr", "ss", "ee", "oo", "aa"])
FOREIGN = ("sh", "th", "ph", "ck", "gh", "wh", "w", "k", "y")
DIGRAPHS = (("ch", "C"), ("lh", "L"), ("nh", "N"), ("rr", "R"), ("ss", "S"), ("qu", "K"),
            ("gue", "Ge"), ("gui", "Gi"))


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Portuguese spelling: no k, w, y or foreign letter
    groups (sh th ph ck), no doubled letters other than rr ss ee oo aa, onsets of one consonant
    or obstruent + l/r, codas of one consonant inside a word (or n/r/b + s), and a vowel or one of
    s r l z m x n at the end (weekend, chat, update are not Portuguese)."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(f in w for f in FOREIGN):
        return False
    if any(a == b and a + b not in DOUBLES for a, b in pairwise(w)):
        return False
    for d, r in DIGRAPHS:
        w = w.replace(d, r)
    runs = consonant_runs(w, y_vowel=False)
    return runs is not None and clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_pt(text: str) -> list[str]:
    """Letters the Portuguese front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
