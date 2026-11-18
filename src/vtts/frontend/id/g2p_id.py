"""Indonesian word -> id-en tokens (spelling rules, the two e's, stress).

Indonesian spelling is close to phonemic. The rules:

- Digraphs ng -> ng, ny -> ny, sy -> sy, kh -> kh; c -> c (as in "cara"), j -> j, v -> f, q -> k,
  x -> k s (s at the start of a word); k at the end of a word -> the glottal stop ? (anak), as
  does an apostrophe (ma'af, Jum'at); a doubled consonant letter is read once (Allah).
- The letter e is the schwa @ (besar, kecil) or e (enak). lexicons/id/overrides.tsv respells
  words whose e is not read by the defaults (in a reading, e is the schwa and é the other e); a
  word with a suffix or prefix uses the entry of its stem (mejanya, kereta-nya). Defaults: e
  next to another vowel is e (teori, video), e in the last syllable is e when it ends the word
  (sate, sore) or is closed by a consonant other than r (boleh, bebek, hotel, persen), and any
  other e is the schwa (besar, kemudian, komputer). The words ke and se keep the schwa.
- ai, au, oi, ei at the end of a word are a diphthong: the second vowel is the glide y / w
  (pantai, pulau); elsewhere every vowel is a syllable nucleus (baik, laut).
- Stress: the second-to-last nucleus, or the last one when the second-to-last is the schwa
  (besar -> be-SAR); one nucleus is stressed; function words (UNSTRESSED) are not.

valid_spelling() says whether a plain ASCII word could be Indonesian (latin.py uses it to tell
Indonesian from English words).
"""

from __future__ import annotations

import functools
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

VOWELS = "aiueoé"
LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzé")
FOLD = {"è": "é", "ê": "é", "ë": "e", "ç": "s", "ø": "o", "æ": "e", "œ": "e", "ß": "s"}
SUFFIXES = ("nya", "lah", "kah", "pun", "kan", "ku", "mu", "an", "i")
PREFIXES = ("ber", "ter", "per", "di", "ke", "se", "pe", "me")
UNSTRESSED = frozenset(("yang", "dan", "di", "ke", "dari", "pada", "untuk", "dengan", "atau",
                        "oleh", "bagi", "si", "sang", "para", "se"))


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("id", "overrides")


def fold(word: str) -> str:
    """Lower case; é (and è ê) kept as the e of "enak", other accents dropped, ' kept."""
    out = []
    for ch in word.lower():
        if ch in LETTERS or ch == "'":
            out.append(ch)
            continue
        base = FOLD.get(ch) or unicodedata.normalize("NFD", ch)[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def respell(w: str) -> tuple[str, bool]:
    """(word, explicit): the overrides entry of the word or of its stem (with its affixes kept);
    explicit means every plain e of the result is the schwa."""
    table = override_table()
    if w in table:
        return table[w], True
    for pre in ("", *PREFIXES):
        if not w.startswith(pre):
            continue
        rest = w[len(pre):]
        for suf in ("", *SUFFIXES):
            stem = rest[:len(rest) - len(suf)] if suf else rest
            if (pre or suf) and rest.endswith(suf) and len(stem) >= 3 and stem in table:
                return pre + table[stem] + suf, True
    return w, False


def _segments(w: str) -> list[list[str]]:
    """["C", phoneme] or ["V", vowel] per sound; the letter e is ["V", "E"] (decided later)."""
    out: list[list[str]] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        two = w[i:i + 2]
        if two in ("ng", "ny", "sy", "kh"):
            out.append(["C", two])
            i += 2
            continue
        if c in "aiuo":
            out.append(["V", c])
        elif c == "é":
            out.append(["V", "e"])
        elif c == "e":
            out.append(["V", "E"])
        elif c == "'":
            out.append(["C", "?"])
        elif c == "x":
            out += [["C", "s"]] if i == 0 else [["C", "k"], ["C", "s"]]
        elif i and c == w[i - 1] and c not in VOWELS:
            pass  # doubled consonant letter
        else:
            out.append(["C", {"v": "f", "q": "k"}.get(c, c)])
        i += 1
    if out and out[-1] == ["C", "k"]:
        out[-1] = ["C", "?"]
    return out


def _resolve_e(segs: list[list[str]], word: str, explicit: bool) -> None:
    vowels = [k for k, s in enumerate(segs) if s[0] == "V"]
    for k in vowels:
        if segs[k][1] != "E":
            continue
        if explicit or word in ("ke", "se"):
            segs[k][1] = "@"
            continue
        next_to_vowel = (k > 0 and segs[k - 1][0] == "V") or (k + 1 < len(segs) and segs[k + 1][0] == "V")
        last = k == vowels[-1]
        tail = [s[1] for s in segs[k + 1:]]
        open_end = last and not tail
        closed_end = last and tail and tail[-1] != "r"
        segs[k][1] = "e" if next_to_vowel or open_end or closed_end else "@"


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('besar' -> b @ s a1 r), without the ID: prefix."""
    w = fold(word)
    w, explicit = respell(w)
    w = fold(w)
    if not w.strip("'"):
        return ()
    segs = _segments(w)
    _resolve_e(segs, w, explicit)
    if len(segs) >= 2 and segs[-1][0] == segs[-2][0] == "V" and segs[-2][1] + segs[-1][1] in (
            "ai", "au", "oi", "ei"):
        segs[-1] = ["C", "y" if segs[-1][1] == "i" else "w"]
    nuclei = [k for k, s in enumerate(segs) if s[0] == "V"]
    stress = None
    if nuclei and w not in UNSTRESSED:
        stress = nuclei[-1] if len(nuclei) == 1 else nuclei[-2]
        if segs[stress][1] == "@":
            stress = nuclei[-1]
        if segs[stress][1] == "@":
            stress = None
    return tuple(s[1] + ("1" if k == stress else "") for k, s in enumerate(segs))


def word_tokens_id(word: str) -> list[str]:
    """id-en tokens of one word; a word without a vowel (dll, km) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in VOWELS for ch in w):
        from .normalize_id import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for t in word_tokens_id(NAMES[ch])]
    return [f"ID:{p}" for p in phonemes(word)]


# ---------------- spelling check (Indonesian or English?) ----------------

ONSETS = frozenset(["pr", "tr", "kr", "gr", "br", "dr", "fr", "bl", "kl", "gl", "pl", "fl", "sl",
                    "sp", "st", "sk", "sw", "sr", "str", "spr", "skr", "kw", "ps"])
CODAS = frozenset("bdfghklmnprstNK")
FINALS = frozenset("bdfghklmnprstzNK")
FOREIGN = ("th", "sh", "ph", "ch", "ck", "gh", "ou", "oo", "q", "x", "wh")
DOUBLES = frozenset(("aa", "ii", "uu", "nn", "kk"))
DIGRAPHS = (("ng", "N"), ("ny", "J"), ("sy", "S"), ("kh", "K"))


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Indonesian spelling: no foreign letter groups
    (th sh ph ch ck gh ou oo q x; ng, ny, sy, kh are read first, so menghabiskan is fine), c only
    before a vowel, no doubled letters other than aa ii uu nn kk ngg (saat, temannya, bapakku,
    tinggal) and ee after the prefixes ke-/se-, onsets of one consonant or a loanword cluster (pr,
    st, str ...), one consonant (or ng) between syllables, and no c j v w y at the end (party,
    Spotify)."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(c == "c" and (k + 1 == len(w) or w[k + 1] not in "aiueo") for k, c in enumerate(w)):
        return False
    if any(a == b and a + b not in DOUBLES and not (a == "e" and w[:3] in ("kee", "see"))
           for a, b in pairwise(w.replace("ngg", "ng"))):
        return False
    for d, r in DIGRAPHS:
        w = w.replace(d, r)
    if any(f in w for f in FOREIGN):
        return False
    runs = consonant_runs(w, y_vowel=False)
    return runs is not None and clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_id(text: str) -> list[str]:
    """Letters the Indonesian front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
