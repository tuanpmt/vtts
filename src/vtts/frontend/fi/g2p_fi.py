"""Finnish word -> fi-en tokens (spelling rules, length, first-syllable stress).

Finnish spelling is phonemic: one letter, one sound, and a doubled letter is a long sound. A word
(lower case, after normalize_fi) is first replaced by its entry in lexicons/fi/overrides.tsv
(respellings in Finnish orthography for loanwords: pizza -> pitsa), then read letter by letter:

- Vowels a e i o u y ä ö (tokens a e i o u y ae oe; å is read o, ü y, é e, other accented letters
  are folded to their base letter). Diphthongs (ai, uo, yö, ...) are two vowel tokens.
- Length: a doubled letter is the sound followed by the length token ":" (saari s a1 : r i,
  kukka k u1 k : a). ng is the long velar nasal (kengät k e1 ng : ae t); ng before a consonant or
  at the end of a word, and n before k, is a short ng (Helsinki h e1 l s i ng k i); n before p b
  is m (kansanpuolue k a1 n s a m p u o l u e).
- Loan letters: c is s before e i y ä ö, else k (ck k :); q k (qu k v); w v; x k s; z t s
  (zz t : s); š sh, ž zh; ch and sch sh; ph f; th t. sh is s h (mostly a compound boundary:
  hengityshäiriö); loanwords with sh are respelled with š in overrides.tsv (shakki -> šakki). b d f g are kept (loan phonemes).
- Stress: the first vowel of a word is stressed (a1 ...). Number words written as one word
  (kaksisataakolmekymmentäneljä) are split into their parts and each part's first vowel is
  stressed (the secondary stresses of the compound). Short conjunctions (ja, tai, että, kuin
  ...: UNSTRESSED) have no stressed vowel. Other compounds (rautatieasema) are not split.

valid_spelling() says whether a plain ASCII word could be Finnish (latin.py uses it to tell
Finnish from English words).
"""

from __future__ import annotations

import functools
import unicodedata

from ..latin import clusters_fit, consonant_runs
from ..lexicons import load_table

VOWEL_LETTERS = {"a": "a", "e": "e", "i": "i", "o": "o", "u": "u", "y": "y", "ä": "ae", "ö": "oe",
                 "å": "o"}
FRONT = "eiyäö"
LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzåäöšž")
# Letters without a decomposition to a base letter.
FOLD = {"ø": "ö", "æ": "ä", "œ": "ö", "ß": "ss", "ł": "l", "đ": "d", "þ": "t", "ü": "y"}
SINGLE = {"c": "k", "q": "k", "w": "v", "š": "sh", "ž": "zh"}
UNSTRESSED = frozenset(("ja", "tai", "sekä", "kuin", "että", "mutta", "vaan", "eli", "jos", "kun"))

# Parts of number words (the normalizer's output and number words in running text), for the
# secondary stresses of a compound number.
NUMBER_PARTS = (
    "nolla", "yksi", "kaksi", "kolme", "neljä", "viisi", "kuusi", "seitsemän", "kahdeksan",
    "yhdeksän", "kymmenen", "toista", "kymmentä", "sata", "sataa", "tuhat", "tuhatta",
    "ensimmäinen", "toinen", "kolmas", "neljäs", "viides", "kuudes", "seitsemäs", "kahdeksas",
    "yhdeksäs", "kymmenes", "yhdes", "kahdes", "sadas", "tuhannes",
)


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("fi", "overrides")


def fold(word: str) -> str:
    """Lower case, Finnish letters kept, other accented letters reduced to their base letter
    (é -> e, ü -> y, ø -> ö), anything else dropped."""
    out = []
    for ch in word.lower():
        if ch in LETTERS:
            out.append(ch)
            continue
        if ch in FOLD:
            out.append(FOLD[ch])
            continue
        base = (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _segments(w: str) -> list[tuple[str, str]]:
    """("V", vowel) / ("C", consonant) / ("L", ":") per sound, in order."""
    out: list[tuple[str, str]] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        nxt = w[i + 1] if i + 1 < n else ""
        nxt2 = w[i + 2] if i + 2 < n else ""
        if c in VOWEL_LETTERS:
            out.append(("V", VOWEL_LETTERS[c]))
            if nxt == c:
                out.append(("L", ":"))
                i += 2
            else:
                i += 1
            continue
        if c == "n" and nxt == "g":
            out.append(("C", "ng"))
            if nxt2 in VOWEL_LETTERS:
                out.append(("L", ":"))
            i += 2
            continue
        if c == "n" and nxt == "k":
            out.append(("C", "ng"))
            i += 1
            continue
        if c == "n" and nxt and nxt in "pb":
            out.append(("C", "m"))
            i += 1
            continue
        pair = c + nxt
        if c + nxt + nxt2 == "sch":
            out.append(("C", "sh"))
            i += 3
            continue
        if pair == "ch":
            out.append(("C", "sh"))
            i += 2
            continue
        if pair == "ph":
            out.append(("C", "f"))
            i += 2
            continue
        if pair == "th":
            out.append(("C", "t"))
            i += 2
            continue
        if pair == "ck":
            out += [("C", "k"), ("L", ":")]
            i += 2
            continue
        if pair == "qu":
            out += [("C", "k"), ("C", "v")]
            i += 2
            continue
        if c == "x":
            out += [("C", "k"), ("C", "s")]
            i += 1
            continue
        if c == "z":
            out.append(("C", "t"))
            if nxt == "z":
                out.append(("L", ":"))
                i += 1
            out.append(("C", "s"))
            i += 1
            continue
        if c == "c":
            out.append(("C", "s" if nxt in FRONT else "k"))
        else:
            out.append(("C", SINGLE.get(c, c)))
        if nxt == c:
            out.append(("L", ":"))
            i += 2
        else:
            i += 1
    return out


@functools.cache
def _all_number_parts() -> tuple[str, ...]:
    """NUMBER_PARTS and the elative and illative parts of the normalizer's ranges, longest first."""
    from .normalize_fi import ELATIVE, ILLATIVE

    return tuple(sorted({*NUMBER_PARTS, *ELATIVE.values(), *ILLATIVE.values()}, key=len, reverse=True))


def number_parts(w: str) -> list[str] | None:
    """A word made only of number parts, split (kaksisataakolme -> kaksi sataa kolme); None for
    any other word or a single part."""
    @functools.cache
    def split(k: int) -> tuple[str, ...] | None:
        if k == len(w):
            return ()
        for p in _all_number_parts():
            if w.startswith(p, k):
                rest = split(k + len(p))
                if rest is not None:
                    return (p, *rest)
        return None

    parts = split(0)
    return list(parts) if parts and len(parts) > 1 else None


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('kukka' -> k u1 k : a), without the FI: prefix."""
    w = fold(word)
    w = fold(override_table().get(w, w))
    if not w:
        return ()
    out: list[str] = []
    for part in number_parts(w) or [w]:
        stressed = w not in UNSTRESSED
        for kind, p in _segments(part):
            if kind == "V" and stressed:
                out.append(p + "1")
                stressed = False
            else:
                out.append(p)
    return tuple(out)


def word_tokens_fi(word: str) -> list[str]:
    """fi-en tokens of one word; a word without a vowel (km, pst) is spelled letter by letter."""
    w = fold(word)
    if w and not any(ch in VOWEL_LETTERS for ch in w):
        from .normalize_fi import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_fi(n)]
    return [f"FI:{p}" for p in phonemes(word)]


# ---------------- spelling check (Finnish or English?) ----------------

ONSETS = frozenset(["pr", "tr", "kr", "br", "dr", "gr", "fr", "pl", "kl", "bl", "gl", "fl", "sp", "st",
                    "sk", "str", "spr", "skr", "sl", "sm", "sn", "sv", "kv"])
CODAS = frozenset("bdfghjklmnprstv") | {"ns", "rs", "ls", "ks", "ts", "rt", "nt", "lt", "rk", "lk",
                                         "lm", "rm", "hk", "ht", "st", "mp", "lp", "rp", "nk", "kk",
                                         "tt", "pp", "ss", "ll", "mm", "nn", "rr"}
FINALS = frozenset("ntslr")
FOREIGN = ("th", "ph", "ch", "ck", "gh", "c", "q", "w", "x", "z")
# y next to a back vowel: no Finnish diphthong or long vowel (play, boy, you; compounds such as
# yliopisto keep y apart from a o u).
DISHARMONY = ("ay", "oy", "uy", "ya", "yo", "yu")


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Finnish spelling: no foreign letters or letter groups
    (c q w x z, th ph ck ..., sh at the start), no y next to a o u (ay oy ya ...), no letter three times
    in a row, onsets of one consonant (or a loan cluster: pr tr kr st sp ...), codas of one or two
    consonants inside a word (ng counts as one) and a vowel or one of n t s l r at the end."""
    if not w or not w.isascii() or not w.isalpha():
        return False
    if any(f in w for f in FOREIGN) or w.startswith("sh"):
        return False
    if any(d in w for d in DISHARMONY):
        return False
    if any(a == b == c for a, b, c in zip(w, w[1:], w[2:], strict=False)):
        return False
    runs = consonant_runs(w.replace("ng", "N"), vowels="aeiouy", y_vowel=False)
    if runs is None:
        return False
    return clusters_fit(runs, ONSETS, CODAS | {"N", "nN"}, FINALS) and all(
        len(r) <= 3 for r, _, _ in runs)


def unreadable_fi(text: str) -> list[str]:
    """Letters the Finnish front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
