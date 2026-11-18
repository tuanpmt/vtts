"""Spanish word -> es-en tokens (spelling rules, syllable nuclei, stress).

A word (lower case, after normalize_es) is first replaced by its entry in lexicons/es/overrides.tsv
(respellings in Spanish orthography: méxico -> méjico), then read letter by letter:

- c before e/i and z -> th; c, k, qu (u silent before e/i) -> k; ch -> ch; g before e/i, j -> x;
  gu before e/i -> g (u silent), gü -> g w; h is silent; ll -> ll; ñ -> ny; v -> b; w -> w;
  x -> k s (s at the start of a word); y before a vowel -> y, else the vowel i;
  r at the start of a word or after n, l, s, and rr -> rr, else r.
- Vowels: a e o and accented vowels are strong. In a run of vowels the strong ones are syllable
  nuclei; an unaccented i/u next to another vowel is a glide (j/w), and in i+u / u+i the second
  is the nucleus (ciudad, cuidado, muy).
- Stress: the vowel with a written accent; else the second-to-last nucleus when the word ends
  in a vowel, n or s, else the last nucleus. Function words (UNSTRESSED: articles, clitic
  pronouns, most prepositions and conjunctions) have no stressed vowel.

valid_spelling() says whether a plain ASCII word could be Spanish (latin.py uses it to tell
Spanish from English words).
"""

from __future__ import annotations

import functools
import unicodedata
from itertools import pairwise

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

VOWELS = "aeiouáéíóúü"
ACCENTED = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
FRONT = "eiéí"
LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzáéíóúüñ")
# Letters of other languages without a decomposition to a base letter (ç is read as s).
FOLD = {"ç": "s", "ø": "o", "æ": "e", "œ": "e", "ß": "s", "ł": "l", "đ": "d", "þ": "t"}

# Words without a stressed vowel (articles, clitic pronouns, prepositions, conjunctions, relative
# words without an accent).
UNSTRESSED = frozenset((
    "el", "la", "lo", "los", "las", "un", "unos", "del", "al", "a", "ante", "bajo", "con",
    "contra", "de", "desde", "en", "entre", "hacia", "hasta", "para", "por", "sin", "so",
    "sobre", "tras", "me", "te", "se", "le", "les", "nos", "os", "mi", "mis", "tu", "tus", "su",
    "sus", "nuestro", "y", "e", "o", "u", "ni", "que", "si", "pero", "mas", "aunque", "como",
    "cuando", "donde", "cual", "quien", "quienes", "porque", "pues",
))


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("es", "overrides")


def fold(word: str) -> str:
    """Lower case, Spanish letters kept, other accented letters reduced to their base letter
    (à -> a, ö -> o, ç -> s), anything else dropped."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
            continue
        base = FOLD.get(ch) or unicodedata.normalize("NFD", ch)[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _segments(w: str) -> list[list]:
    """["C", phoneme] or ["V", vowel, accented] per sound, in order."""
    out: list[list] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        nxt = w[i + 1] if i + 1 < n else ""
        nxt2 = w[i + 2] if i + 2 < n else ""
        prev = w[i - 1] if i else ""
        step = 1
        if c in VOWELS:
            out.append(["V", ACCENTED.get(c, "u" if c == "ü" else c), c in ACCENTED])
        elif c == "c":
            if nxt == "h":
                out.append(["C", "ch"])
                step = 2
            else:
                out.append(["C", "th" if nxt in FRONT else "k"])
        elif c == "q":
            out.append(["C", "k"])
            if nxt == "u" and nxt2 in FRONT:
                step = 2
        elif c == "g":
            if nxt in FRONT:
                out.append(["C", "x"])
            else:
                out.append(["C", "g"])
                if nxt == "u" and nxt2 in FRONT:
                    step = 2
        elif c == "l" and nxt == "l":
            out.append(["C", "ll"])
            step = 2
        elif c == "r":
            if nxt == "r":
                out.append(["C", "rr"])
                step = 2
            else:
                out.append(["C", "rr" if i == 0 or prev in "nls" else "r"])
        elif c == "y":
            if nxt and nxt in VOWELS:
                out.append(["C", "y"])
            else:
                out.append(["V", "i", False])
        elif c == "x":
            if i == 0:
                out.append(["C", "s"])
            else:
                out += [["C", "k"], ["C", "s"]]
        elif c == "h":
            pass
        else:
            out.append(["C", {"j": "x", "z": "th", "ñ": "ny", "v": "b"}.get(c, c)])
        i += step
    return out


def _nuclei(segs: list[list]) -> list[int]:
    """Indices of syllable nuclei; other vowels become glides in place."""
    nuclei: list[int] = []
    i = 0
    while i < len(segs):
        if segs[i][0] != "V":
            i += 1
            continue
        j = i
        while j < len(segs) and segs[j][0] == "V":
            j += 1
        run = list(range(i, j))
        strong = [k for k in run if segs[k][2] or segs[k][1] in "aeo"]
        if not strong:
            strong = [run[-1]]
        for k in run:
            if k not in strong:
                segs[k] = ["G", "j" if segs[k][1] == "i" else "w"]
        nuclei += strong
        i = j
    return nuclei


def stressed_nucleus(word: str, segs: list[list], nuclei: list[int]) -> int | None:
    if not nuclei or word in UNSTRESSED:
        return None
    marked = [k for k in nuclei if segs[k][2]]
    if marked:
        return marked[-1]
    if len(nuclei) == 1:
        return nuclei[0]
    return nuclei[-2] if word[-1] in "aeiouns" else nuclei[-1]


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('canción' -> k a n th j o1 n), without the ES: prefix."""
    w = fold(word)
    w = fold(override_table().get(w, w))
    if not w:
        return ()
    segs = _segments(w)
    nuclei = _nuclei(segs)
    stress = stressed_nucleus(w, segs, nuclei)
    out = []
    for k, s in enumerate(segs):
        out.append(s[1] + ("1" if k == stress else ""))
    return tuple(out)


def word_tokens_es(word: str) -> list[str]:
    """es-en tokens of one word; a word without a vowel (pst, km) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in VOWELS or ch == "y" for ch in w):
        from .normalize_es import LETTERS

        return [t for ch in w if ch in LETTERS for n in LETTERS[ch].split() for t in word_tokens_es(n)]
    return [f"ES:{p}" for p in phonemes(word)]


# ---------------- spelling check (Spanish or English?) ----------------

ONSETS = frozenset(["pl", "pr", "bl", "br", "fl", "fr", "cl", "cr", "gl", "gr", "dr", "tr", "kr", "ps",
                    "gn", "pn"])
CODAS = frozenset("bcdfgjklmnprstxz") | {"ns", "bs", "rs", "ds"}
FINALS = frozenset("nsrldzjxy")
DOUBLES = frozenset(["ll", "rr", "cc", "nn", "ee", "oo", "aa"])
FOREIGN = ("sh", "th", "ph", "ck", "gh", "kh", "tz", "wh", "w")


DIGRAPHS = (("ch", "C"), ("ll", "L"), ("rr", "R"), ("qu", "K"))


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Spanish spelling: no foreign letter groups
    (w, sh, th, ph, ck ...), no doubled letters other than ll rr cc nn ee oo aa, onsets of one
    consonant or obstruent + l/r (no s + consonant: smart, stream), codas of one consonant inside a
    word (or n/b/r/d + s), and a vowel or one of n s r l d z j x y at the end."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(f in w.replace("desh", "dez") for f in FOREIGN) or "q" in w.replace("qu", ""):
        return False
    if any(a == b and a + b not in DOUBLES for a, b in pairwise(w)):
        return False
    for d, r in DIGRAPHS:
        w = w.replace(d, r)
    runs = consonant_runs(w)
    return runs is not None and clusters_fit(runs, ONSETS, CODAS, FINALS)


def unreadable_es(text: str) -> list[str]:
    """Letters the Spanish front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
