"""Greek word (Greek script, lower case) -> el-en tokens.

Modern Greek spelling is historical but regular; the reading is rules and a small table
(lexicons/el/overrides.tsv: the phonemes of words read unlike the rules, mostly a glide the rules
do not see (διακόσια, βιολί), matched on the whole lower-case word). A word is read letter by
letter; each Greek letter is decomposed (NFD) into its base letter, a stress mark (tonos, oxia,
varia or perispomeni) and the dialytika; a separate combining mark U+0300-U+036F (decomposed
input) belongs to the Greek letter before it:

- Vowels: α a, ε e, η ι υ i, ο ω o. Digraphs: αι e, ει οι υι i, ου u, unless the second letter
  has a dialytika (λαϊκός) or the first a tonos (τσάι, άυλος). The tonos of a digraph is on its
  second letter (είναι, ούτε).
- αυ ευ ηυ: a e i + v before a vowel or a voiced consonant (αύριο, Ευρώπη), + f before a
  voiceless consonant θ κ ξ π σ τ φ χ ψ or at the end (αυτός, ευχαριστώ); a β or φ after it is
  the same sound (Εύβοια e1 v i a).
- Consonants: β v, γ gh (ɣ, ʝ before e/i), δ dh, ζ z, θ th, κ k, λ l, μ m, ν n, ξ k s, π p,
  ρ r, σ ς s (z before a voiced consonant: κόσμος), τ t, φ f, χ x, ψ p s. μπ b, ντ d, γκ g at the
  start of a word and ng g inside, γγ ng g, γχ ng x, γξ ng k s, τσ ts, τζ dz; a doubled letter is
  one sound (άλλος, Έλληνας).
- Glide: an unstressed i sound (ι, η, υ, ει, οι) between a single consonant and a vowel is the
  glide j when the next vowel is stressed (παιδιά, χωριό, δουλειά) or the i comes after the
  stressed vowel (ήλιος, σπίτια, διάρκεια), not after a consonant + ρ λ (τριάντα) and never before
  another i sound (χρησιμοποιείται); after γ (γιατί, γιαγιά) and in a word without a tonos (monosyllables by
  spelling: για, μια, ποιος, πιο) always.
- Stress: the vowel with a tonos (a word may have two: άνθρωπός μου); a word of one syllable
  without a tonos is stressed unless it is a function word (UNSTRESSED: articles, clitic
  pronouns, prepositions, conjunctions); a longer word without a tonos (capitals) is stressed on
  the second-to-last syllable.
"""

from __future__ import annotations

import functools
import re
import unicodedata

from ..lexicons import load_table

TONOS, DIALYTIKA = "\u0301", "\u0308"
STRESS_MARKS = ("\u0301", "\u0300", "\u0342")  # tonos / oxia, varia, perispomeni
VOWEL_LETTERS = {"α": "a", "ε": "e", "η": "i", "ι": "i", "ο": "o", "υ": "i", "ω": "o"}
DIGRAPHS = {("α", "ι"): "e", ("ε", "ι"): "i", ("ο", "ι"): "i", ("υ", "ι"): "i", ("ο", "υ"): "u"}
CONSONANTS = {"β": ["v"], "γ": ["gh"], "δ": ["dh"], "ζ": ["z"], "θ": ["th"], "κ": ["k"],
              "λ": ["l"], "μ": ["m"], "ν": ["n"], "ξ": ["k", "s"], "π": ["p"], "ρ": ["r"],
              "σ": ["s"], "ς": ["s"], "τ": ["t"], "φ": ["f"], "χ": ["x"], "ψ": ["p", "s"]}
VOICELESS = frozenset("θκξπσςτφχψ")
VOICED = frozenset("βγδζλμνρ")
I_SOUNDS = ("ι", "η", "υ", "ει", "οι")
UNSTRESSED = frozenset((
    "ο", "η", "το", "οι", "τα", "του", "της", "των", "τον", "την", "τη", "τις", "τους", "ένα",
    "μου", "σου", "μας", "σας", "τού", "σε", "στο", "στη", "στην", "στον", "στα", "στις", "στους",
    "στων", "με", "να", "θα", "και", "κι", "δε", "δεν", "μη", "μην", "αν", "ως", "πως", "που",
    "για", "προς", "απ", "σ", "τ", "ότι", "ή", "μα", "ούτε", "λες",
))


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("el", "overrides")


def is_greek(ch: str) -> bool:
    return "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff"


def is_greek_word(word: str) -> bool:
    return any(is_greek(ch) and ch.isalpha() for ch in word)


FINAL_SIGMA = re.compile(r"(?<=\w)σ(?!\w)")


def lower(word: str) -> str:
    """str.lower() (accented capitals: Ά -> ά) with Σ -> σ, then σ at the end of a word -> ς
    (ΟΔΟΣ -> οδος; a σ after a word character and before none)."""
    return FINAL_SIGMA.sub("ς", word.replace("Σ", "σ").lower())


@functools.cache
def decompose(ch: str) -> tuple[str, bool, bool]:
    """(base letter, stress mark, dialytika) of one character (NFD)."""
    d = unicodedata.normalize("NFD", ch)
    return d[0], any(m in d[1:] for m in STRESS_MARKS), DIALYTIKA in d[1:]


def _letters(word: str) -> list[tuple[str, bool, bool]]:
    """(base letter, stress mark, dialytika) per Greek letter (breathings are dropped; any accent
    counts as the tonos)."""
    out: list[tuple[str, bool, bool]] = []
    for ch in lower(word):
        if "\u0300" <= ch <= "\u036f":  # a separate combining mark: on the letter before it
            if out:
                base, acc, dia = out[-1]
                out[-1] = (base, acc or ch in STRESS_MARKS, dia or ch == DIALYTIKA)
            continue
        base, acc, dia = decompose(ch)
        if base in VOWEL_LETTERS or base in CONSONANTS:
            out.append((base, acc, dia))
    return out


def _segments(word: str) -> list[list]:
    """["V", vowel, stressed, i_sound] / ["C", consonant] in order."""
    lets = _letters(word)
    out: list[list] = []
    n = len(lets)
    i = 0
    while i < n:
        b, acc, _dia = lets[i]
        nb, nacc, ndia = lets[i + 1] if i + 1 < n else ("", False, False)
        if b in VOWEL_LETTERS:
            if (b, nb) in DIGRAPHS and not ndia and not acc:
                out.append(["V", DIGRAPHS[(b, nb)], nacc, b + nb in I_SOUNDS])
                i += 2
                continue
            if b in "αεη" and nb == "υ" and not ndia and not acc:
                after = lets[i + 2][0] if i + 2 < n else ""
                out.append(["V", VOWEL_LETTERS[b], nacc, b == "η"])
                out.append(["C", "f" if not after or after in VOICELESS else "v"])
                i += 3 if after in ("β", "φ") else 2  # Εύβοια, ευφυής: one v / f
                continue
            out.append(["V", VOWEL_LETTERS[b], acc, b in I_SOUNDS])
            i += 1
            continue
        pair = b + nb
        if pair in ("μπ", "ντ"):
            out.append(["C", "b" if b == "μ" else "d"])
            i += 2
            continue
        if pair == "γκ":
            out += [["C", "g"]] if i == 0 else [["C", "ng"], ["C", "g"]]
            i += 2
            continue
        if b == "γ" and nb in "γχξ" and nb:
            out.append(["C", "ng"])
            if nb == "γ":
                out.append(["C", "g"])
                i += 2
            else:
                i += 1
            continue
        if pair in ("τσ", "τς"):
            out.append(["C", "ts"])
            i += 2
            continue
        if pair == "τζ":
            out.append(["C", "dz"])
            i += 2
            continue
        if b in "σς" and nb and nb in VOICED:
            out.append(["C", "z"])
        else:
            out += [["C", c] for c in CONSONANTS[b]]
        i += 2 if nb == b else 1
    return out


def _glides(segs: list[list], has_tonos: bool) -> None:
    """Unstressed i sounds between a consonant and a vowel become the glide j (in place)."""
    vowels = [k for k, s in enumerate(segs) if s[0] == "V"]
    stressed = [k for k in vowels if segs[k][2]]
    first_stress = stressed[0] if stressed else None
    for k in vowels:
        s = segs[k]
        if s[2] or s[1] != "i" or not s[3] or k == 0 or segs[k - 1][0] != "C":
            continue
        if k + 1 >= len(segs) or segs[k + 1][0] != "V":
            continue
        after_gh = segs[k - 1][1] == "gh"
        # hiatus after a consonant + ρ λ (τριάντα, μακριά) and before another i sound (χρησιμοποιεί)
        liquid = k >= 2 and segs[k - 2][0] == "C" and segs[k - 1][1] in ("r", "l")
        if segs[k + 1][1] == "i":
            continue
        if not has_tonos or after_gh or (not liquid and (
                segs[k + 1][2] or (first_stress is not None and k > first_stress))):
            segs[k] = ["G", "j"]


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('παιδιά' -> p e dh j a1), without the EL: prefix."""
    w = lower(word)
    if w in override_table():
        return tuple(override_table()[w].split())
    segs = _segments(w)
    if not segs:
        return ()
    has_tonos = any(s[0] == "V" and s[2] for s in segs)
    _glides(segs, has_tonos)
    vowels = [k for k, s in enumerate(segs) if s[0] == "V"]
    if not has_tonos and vowels:
        plain = "".join(b for b, _, _ in _letters(w))
        if len(vowels) >= 2:
            segs[vowels[-2]][2] = True
        elif plain not in UNSTRESSED:
            segs[vowels[0]][2] = True
    return tuple(s[1] + ("1" if s[0] == "V" and s[2] else "") for s in segs)


def word_tokens_el(word: str) -> list[str]:
    """el-en tokens of one Greek word."""
    return [f"EL:{p}" for p in phonemes(word)]


def unreadable_el(text: str) -> list[str]:
    """Letters the Greek front-end cannot read: other scripts than Greek and Latin (Latin words
    are read in English), Greek letters outside the modern alphabet (ϝ ϙ ϡ)."""
    out = []
    for ch in text:
        if not ch.isalpha():
            continue
        if is_greek(ch):
            if not _letters(ch):
                out.append(ch)
        elif not ("a" <= unicodedata.normalize("NFKD", ch)[0].lower() <= "z"):
            out.append(ch)
    return out
