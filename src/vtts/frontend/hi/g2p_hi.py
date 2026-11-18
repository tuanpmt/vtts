"""Hindi word (Devanagari) -> hi-en tokens.

Inventory (50 tokens, HI: prefix; phoneme_set.TOKENS_HIEN):

| Group | Phonemes |
|---|---|
| Vowels (10) | a (schwa, अ) aa i ii u uu e ai (ऐ ॅ) o au (औ ऑ) |
| Nasalization (1) | ~ after a vowel (chandrabindu ँ, most anusvara ं) |
| Velar, palatal (10) | k kh g gh ng, c ch j jh ny (च छ ज झ ञ) |
| Retroflex, dental (10) | T Th D Dh N, t th d dh n |
| Labial, others (12) | p ph b bh m, y r l v, sh (श and ष), s, h |
| Flaps, nukta (7) | R Rh (ड़ ढ़), q x G z f (क़ ख़ ग़ ज़ फ़) |

Rules, in order:

1. Letters. A consonant letter carries the inherent schwa unless a matra (vowel sign) or the
   virama ् follows. The nukta ़ (or a precomposed nukta letter, U+0958-U+095F) changes the
   consonant: क़ q, ख़ x, ग़ G, ज़ z (also झ़), फ़ f, ड़ R, ढ़ Rh; on other letters it is ignored.
   ज्ञ is read g y, क्ष k sh (ष = sh); ऋ / ृ are r i, ॠ / ॄ r ii; ऑ ॉ are au, ऍ ॅ ai; ॐ is o m;
   visarga ः is h; avagraha ऽ, ZWJ and ZWNJ are ignored.
2. Nasals. Chandrabindu ँ nasalizes its vowel (~). Anusvara ं after a short vowel (a i u) before
   a stop or nasal is the nasal of that stop's place (ng ny N n m: हिंदी h i n d ii, ठंडा
   Th a N D aa); anywhere else (after a long vowel, before y r l v sh s h z f, at the end) it
   nasalizes the vowel (दांत d aa ~ t, संसार s a ~ s aa r, में m e ~).
3. Schwa deletion. Only inherent schwas without a nasal sign or visarga are deleted.
   a. Word-final: deleted, except in a word with one vowel (न) and after a cluster ending in y or
      r (सत्य, मित्र).
   b. Medial, right to left: a schwa in the context V C _ C V (one consonant on each side, a
      vowel beyond each) is deleted (कमला k a m l aa, समझना s a m a jh n aa: the schwa after jh
      goes first, so the one after m no longer has C V to its right).
   Words the rule gets wrong (prefix or compound boundaries, Sanskrit -aN words) are listed in
   lexicons/hi/overrides.tsv with their phonemes, matched on the whole word (NFC).
"""

from __future__ import annotations

import functools
import unicodedata

from ..lexicons import load_table

VOWELS = ("a", "aa", "i", "ii", "u", "uu", "e", "ai", "o", "au")
NASAL = "~"
CONSONANTS = ("k", "kh", "g", "gh", "ng", "c", "ch", "j", "jh", "ny",
              "T", "Th", "D", "Dh", "N", "t", "th", "d", "dh", "n",
              "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "sh", "s", "h",
              "R", "Rh", "q", "x", "G", "z", "f")
PHONEMES = VOWELS + (NASAL,) + CONSONANTS

LETTERS = dict(zip("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ", (
    "k", "kh", "g", "gh", "ng", "c", "ch", "j", "jh", "ny", "T", "Th", "D", "Dh", "N",
    "t", "th", "d", "dh", "n", "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "sh", "sh", "s",
    "h", "l"), strict=True))
NUKTA_LETTERS = {"क": "q", "ख": "x", "ग": "G", "ज": "z", "झ": "z", "फ": "f", "ड": "R", "ढ": "Rh",
                 "न": "n", "र": "r", "ळ": "l", "य": "y"}
# Precomposed nukta letters (NFC keeps them decomposed, but text may hold either form).
PRECOMPOSED = {"ऩ": "न", "ऱ": "र", "ऴ": "ळ", "क़": "क", "ख़": "ख",
               "ग़": "ग", "ज़": "ज", "ड़": "ड", "ढ़": "ढ", "फ़": "फ",
               "य़": "य"}
INDEPENDENT = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ए": "e", "ऐ": "ai",
               "ओ": "o", "औ": "au", "ऍ": "ai", "ऑ": "au", "ऎ": "e", "ऒ": "o", "ॲ": "ai",
               "ऋ": "r i", "ॠ": "r ii", "ऌ": "l i", "ॡ": "l ii", "ऄ": "a"}
MATRAS = {"ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "े": "e", "ै": "ai", "ो": "o",
          "ौ": "au", "ॅ": "ai", "ॉ": "au", "ॆ": "e", "ॊ": "o", "ृ": "r i", "ॄ": "r ii",
          "ॢ": "l i", "ॣ": "l ii", "ॏ": "au", "ॖ": "u", "ॗ": "uu"}
VIRAMA, NUKTA, ANUSVARA, CHANDRABINDU, VISARGA = "्", "़", "ं", "ँ", "ः"
IGNORED = frozenset("ऽ‌‍॒॑")
SHORT = frozenset(("a", "i", "u"))
# Anusvara before a consonant of a stop class -> the nasal of that class.
HOMORGANIC = {**dict.fromkeys(("k", "kh", "g", "gh", "q", "x", "G", "ng"), "ng"),
              **dict.fromkeys(("c", "ch", "j", "jh", "ny"), "ny"),
              **dict.fromkeys(("T", "Th", "D", "Dh", "R", "Rh", "N"), "N"),
              **dict.fromkeys(("t", "th", "d", "dh", "n"), "n"),
              **dict.fromkeys(("p", "ph", "b", "bh", "m"), "m")}
FINAL_KEEP = frozenset(("y", "r"))  # final schwa kept after a cluster ending in y / r


def is_devanagari(ch: str) -> bool:
    return "ऀ" <= ch <= "ॿ" or "꣠" <= ch <= "ꣿ"


def is_devanagari_word(word: str) -> bool:
    return any(is_devanagari(ch) and ch not in "।॥" and not "०" <= ch <= "९" for ch in word)


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("hi", "overrides")


class _Seg:
    """One sound: kind "C" or "V"; a V may be an inherent schwa and may carry a sign."""

    __slots__ = ("inherent", "kind", "ph", "sign")

    def __init__(self, kind: str, ph: str, inherent: bool = False):
        self.kind, self.ph, self.inherent, self.sign = kind, ph, inherent, ""


def _parse(word: str) -> list[_Seg]:
    chars: list[str] = []
    for ch in unicodedata.normalize("NFC", word):
        chars += [PRECOMPOSED[ch], NUKTA] if ch in PRECOMPOSED else [ch]
    segs: list[_Seg] = []
    i, n = 0, len(chars)

    def vowel(text: str, inherent: bool = False) -> None:
        *cons, v = text.split()
        segs.extend(_Seg("C", c) for c in cons)
        segs.append(_Seg("V", v, inherent))

    while i < n:
        ch = chars[i]
        if ch in LETTERS:
            nukta = i + 1 < n and chars[i + 1] == NUKTA
            i += 1 + nukta
            if ch == "ज" and not nukta and chars[i:i + 2] == [VIRAMA, "ञ"]:
                segs += [_Seg("C", "g"), _Seg("C", "y")]  # ज्ञ
                i += 2
            else:
                segs.append(_Seg("C", NUKTA_LETTERS.get(ch, LETTERS[ch]) if nukta else LETTERS[ch]))
            if i < n and chars[i] == VIRAMA:
                i += 1
            elif i < n and chars[i] in MATRAS:
                vowel(MATRAS[chars[i]])
                i += 1
            else:
                vowel("a", inherent=True)
            continue
        if ch in INDEPENDENT:
            vowel(INDEPENDENT[ch])
        elif ch in (ANUSVARA, CHANDRABINDU):
            if segs and segs[-1].kind == "V":
                segs[-1].sign = ch
        elif ch == VISARGA:
            if segs and segs[-1].kind == "V":
                segs[-1].sign = segs[-1].sign or ch
            segs.append(_Seg("C", "h"))
        elif ch == "ॐ":
            segs += [_Seg("V", "o"), _Seg("C", "m")]
        i += 1
    return segs


def _nasals(segs: list[_Seg]) -> list[_Seg]:
    out: list[_Seg] = []
    for k, s in enumerate(segs):
        out.append(s)
        if s.kind != "V" or s.sign != ANUSVARA:
            continue
        nxt = segs[k + 1] if k + 1 < len(segs) else None
        if s.ph in SHORT and nxt is not None and nxt.kind == "C" and nxt.ph in HOMORGANIC:
            out.append(_Seg("C", HOMORGANIC[nxt.ph]))
            s.sign = "N"  # kept, not nasalized
    return out


def _deletable(s: _Seg) -> bool:
    return s.kind == "V" and s.inherent and not s.sign


def _delete_schwas(segs: list[_Seg]) -> list[_Seg]:
    if (len(segs) >= 2 and _deletable(segs[-1]) and sum(s.kind == "V" for s in segs) > 1
            and not (len(segs) >= 3 and segs[-3].kind == "C" and segs[-2].ph in FINAL_KEEP)):
        segs = segs[:-1]
    for k in range(len(segs) - 3, 1, -1):
        if (_deletable(segs[k]) and segs[k - 1].kind == "C" and segs[k - 2].kind == "V"
                and segs[k + 1].kind == "C" and segs[k + 2].kind == "V"):
            del segs[k]
    return segs


@functools.lru_cache(maxsize=16384)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one Devanagari word ('कमला' -> k a m l aa), without the HI: prefix."""
    key = unicodedata.normalize("NFC", word)
    if key in override_table():
        return tuple(override_table()[key].split())
    return rule_phonemes(key)


def rule_phonemes(word: str) -> tuple[str, ...]:
    """Phonemes by the rules alone (no overrides table)."""
    out: list[str] = []
    for s in _delete_schwas(_nasals(_parse(unicodedata.normalize("NFC", word)))):
        out.append(s.ph)
        if s.kind == "V" and s.sign in (ANUSVARA, CHANDRABINDU):
            out.append(NASAL)
    return tuple(out)


def word_tokens_hi(word: str) -> list[str]:
    return [f"HI:{p}" for p in phonemes(word)]


def unreadable_hi(text: str) -> list[str]:
    """Letters the Hindi front-end cannot read (other scripts), to filter training sentences;
    Devanagari and Latin letters (with any accent, read by the English module) are readable."""
    def readable(ch: str) -> bool:
        if is_devanagari(ch):
            return True
        base = unicodedata.normalize("NFKD", ch)[:1]
        return base.isascii()

    return [ch for ch in text if ch.isalpha() and not readable(ch)]
