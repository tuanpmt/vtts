"""Hangul syllables <-> (onset, vowel, coda) jamo by Unicode arithmetic.

A precomposed syllable U+AC00 + (onset * 21 + vowel) * 28 + coda. Jamo are returned as
compatibility letters (ㄱ, ㅏ, ㄺ ...); the onset of a vowel-initial syllable is the silent ㅇ and
an empty coda is "".
"""

from __future__ import annotations

BASE, LAST = 0xAC00, 0xD7A3
ONSETS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
CODAS = ("", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ",
         "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ")
_CODA_INDEX = {c: i for i, c in enumerate(CODAS)}


def is_hangul_syllable(ch: str) -> bool:
    return len(ch) == 1 and BASE <= ord(ch) <= LAST


def decompose(ch: str) -> tuple[str, str, str]:
    """'닭' -> ('ㄷ', 'ㅏ', 'ㄺ'); ch must be a precomposed Hangul syllable."""
    i = ord(ch) - BASE
    return ONSETS[i // 588], VOWELS[i // 28 % 21], CODAS[i % 28]


def compose(onset: str, vowel: str, coda: str = "") -> str:
    return chr(BASE + (ONSETS.index(onset) * 21 + VOWELS.index(vowel)) * 28 + _CODA_INDEX[coda])
