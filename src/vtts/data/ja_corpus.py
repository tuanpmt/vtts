"""Japanese sentence selection for speech synthesis.

Sentences are kept only when they are plain Japanese: kanji, kana and the marks 、。！？「」・,
10-60 kana/kanji characters, ending with 。！？. Digits, Latin letters and brackets are left out so
the text needs no normalization before synthesis, and every kanji must have a reading in the
front-end tables (word table or per-kanji default), so the ids always match the audio. Duration is
estimated at 7.5 morae/s from the front-end's reading.
"""

from __future__ import annotations

import re

JA_RATE = 7.5  # morae per second for read Japanese
MIN_CHARS, MAX_CHARS = 10, 60
JA_CHAR = re.compile(r"[一-鿿々〆ヶぁ-ゖァ-ヺーゝゞヽヾ]")
ALLOWED = re.compile(r"^[一-鿿々〆ヶぁ-ゖァ-ヺーゝゞヽヾ、。！？「」・]+$")
SPLIT = re.compile(r"(?<=[。！？])")
BAD_MARKS = re.compile(r"[、。！？・]{2,}|^[、。！？・」]|「[^」]*$|^[^「]*」")


def split_ja(paragraph: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(paragraph.strip()) if s.strip()]


def char_count(text: str) -> int:
    return len(JA_CHAR.findall(text))


def ja_morae(text: str) -> int:
    from vtts.frontend.ja.g2p_ja import ja_phonemes
    from vtts.frontend.ja.kana import mora_count

    return mora_count(ja_phonemes(text))


def ja_seconds(text: str) -> float:
    return ja_morae(text) / JA_RATE


def plain_ja(sentence: str) -> bool:
    """Script, length and punctuation checks (no reading check)."""
    if not ALLOWED.match(sentence) or sentence[-1] not in "。！？" or BAD_MARKS.search(sentence):
        return False
    if sentence.count("「") != sentence.count("」"):
        return False
    return MIN_CHARS <= char_count(sentence) <= MAX_CHARS


def accept_ja(sentence: str) -> bool:
    from vtts.frontend.ja.g2p_ja import unreadable_ja

    return plain_ja(sentence) and not unreadable_ja(sentence)
