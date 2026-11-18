"""Korean sentence selection for speech synthesis.

Sentences are kept only when they are plain Korean: Hangul syllables, spaces and the marks
, . ? ! (plus quotes), 6-30 words (어절), ending with . ? !. Digits, Latin letters, brackets,
Hanja, bare jamo and stray particles are left out so the text needs no normalization before
synthesis. Duration is estimated at 5.5 syllables/s.
"""

from __future__ import annotations

import re

KO_RATE = 5.5  # syllables per second for read Korean
MIN_WORDS, MAX_WORDS = 6, 30
HANGUL = re.compile(r"[가-힣]")
ALLOWED = re.compile(r"^[가-힣 ,.?!“”‘’'\"]+$")
SPLIT = re.compile(r"(?<=[.?!])\s+")
# A particle standing alone is left over from a formula or a name the dump removed
# ("즉, 는 스칼라장 의 기울기"); 이 is also a determiner and stays allowed.
STRAY_PARTICLES = frozenset(("은", "는", "을", "를", "의", "가", "와", "과", "에", "에서", "로", "으로", "도",
                             "만"))
BAD_MARKS = re.compile(r"[,.?!]{2,}|\s[,.?!]")  # ellipses, marks detached from a word


def split_ko(paragraph: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(paragraph.strip()) if s.strip()]


def syllable_count(text: str) -> int:
    return len(HANGUL.findall(text))


def ko_seconds(text: str) -> float:
    return syllable_count(text) / KO_RATE


def accept_ko(sentence: str) -> bool:
    if not ALLOWED.match(sentence) or sentence[-1] not in ".?!" or BAD_MARKS.search(sentence):
        return False
    words = sentence.split()
    if any(w.strip(",.?!“”‘’'\"") in STRAY_PARTICLES for w in words):
        return False
    return MIN_WORDS <= len(words) <= MAX_WORDS and all(HANGUL.search(w) for w in words)
