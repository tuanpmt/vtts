"""Han characters -> numbered pinyin -> zh-en tokens.

Readings come from two tables in lexicons/zh/ (built by scripts/frontend/build_zh_lexicon.py):
chars.tsv holds one default reading per character, phrases.tsv holds 2-4 character phrases whose
reading differs from what the per-character defaults give. A run of Han characters is read by
forward maximum matching over phrases.tsv (longest phrase first), falling back to chars.tsv one
character at a time. Characters without a reading are skipped.
"""

from __future__ import annotations

import functools

from ..lexicons import load_table
from .pinyin import syllable_tokens

MAX_PHRASE = 4


def is_han(ch: str) -> bool:
    """CJK Unified Ideographs (the block the reading tables cover)."""
    return "一" <= ch <= "鿿"


@functools.cache
def char_table() -> dict[str, str]:
    return load_table("zh", "chars")


@functools.cache
def phrase_table() -> dict[str, tuple[str, ...]]:
    return {k: tuple(v.split()) for k, v in load_table("zh", "phrases").items()}


def read_han(text: str, chars: dict[str, str] | None = None,
             phrases: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Numbered pinyin per readable character of a Han run (forward maximum matching)."""
    chars = char_table() if chars is None else chars
    phrases = phrase_table() if phrases is None else phrases
    out: list[str] = []
    i = 0
    while i < len(text):
        for n in range(min(MAX_PHRASE, len(text) - i), 1, -1):
            reading = phrases.get(text[i:i + n])
            if reading is not None:
                out.extend(reading)
                i += n
                break
        else:
            if (r := chars.get(text[i])) is not None:
                out.append(r)
            i += 1
    return apply_sandhi(out)


def apply_sandhi(syllables: list[str]) -> list[str]:
    """Hook for tone sandhi rules (3-3 -> 2-3, yi1/bu4 before tone 4, ...).

    Version 1 applies none: the tables hold citation tones and the model learns the surface
    tones from the audio. Rules go here if evaluation shows tone errors; the C port must follow.
    """
    return syllables


def han_syllable_tokens(text: str) -> list[list[str]]:
    """Tokens per syllable of a Han run; unreadable characters are skipped."""
    out = []
    for syl in read_han(text):
        toks = syllable_tokens(syl)
        if toks:
            out.append(toks)
    return out


def unknown_han(text: str) -> list[str]:
    """Han characters of text that have no reading (to filter training sentences)."""
    chars = char_table()
    return [ch for ch in text if is_han(ch) and ch not in chars]
