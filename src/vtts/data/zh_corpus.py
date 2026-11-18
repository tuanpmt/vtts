"""Mandarin sentence selection for speech synthesis.

Sentences are kept only when they are plain Simplified Chinese: Han characters and Chinese
punctuation, 8-40 characters, ending with 。！？. Digits, Latin letters and brackets are left out
so the text needs no normalization before synthesis. Duration is estimated at 4.5 characters/s.
"""

from __future__ import annotations

import re
from functools import lru_cache

ZH_RATE = 4.5  # characters per second for read Mandarin
MIN_HAN, MAX_HAN = 8, 40
HAN = re.compile(r"[一-鿿]")
ALLOWED = re.compile(r"^[一-鿿，、；：。！？“”]+$")
SPLIT = re.compile(r"(?<=[。！？])")


@lru_cache(maxsize=1)
def _t2s():
    from opencc import OpenCC

    return OpenCC("t2s")


def to_simplified(text: str) -> str:
    return _t2s().convert(text)


def split_zh(paragraph: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(paragraph.strip()) if s.strip()]


def han_count(text: str) -> int:
    return len(HAN.findall(text))


def zh_seconds(text: str) -> float:
    return han_count(text) / ZH_RATE


def accept_zh(sentence: str) -> bool:
    if not ALLOWED.match(sentence) or sentence[-1] not in "。！？":
        return False
    if not MIN_HAN <= han_count(sentence) <= MAX_HAN:
        return False
    return to_simplified(sentence) == sentence
