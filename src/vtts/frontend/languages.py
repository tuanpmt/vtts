"""Language modules of the bilingual (phoneme set v2) front-end.

Adding a language means adding one entry here (and its tagging rule in lang.py); sentence
splitting, chunk packing and the device protocol are shared. Each module provides:

- normalize(run_text) -> str: the words of one same-language run, lower case, with the
  punctuation tokens , . ? ! ; : separated by single spaces.
- word_tokens(word) -> list[str]: tokens (phoneme set v2) of one normalized word; [] when the
  word cannot be pronounced (it is then skipped).

The C front-end has the same table (runtime/src/vtts_text.c, LANGS); see
docs/frontend/pronunciation-rules.md, "Adding a language".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageModule:
    code: str
    normalize: Callable[[str], str]
    word_tokens: Callable[[str], list[str]]


def _vi_word(word: str) -> list[str]:
    from .g2p import syllable_tokens
    from .syllable import parse_syllable

    syl = parse_syllable(word)
    return syllable_tokens(syl) if syl is not None else []


def _vi_normalize(text: str) -> str:
    from .normalize import normalize

    return normalize(text)


def _en_normalize(text: str) -> str:
    from .en.normalize_en import normalize_en

    return normalize_en(text)


def _en_word(word: str) -> list[str]:
    from .en.g2p_en import g2p_word_en

    return g2p_word_en(word)


LANGUAGES: dict[str, LanguageModule] = {
    "vi": LanguageModule("vi", _vi_normalize, _vi_word),
    "en": LanguageModule("en", _en_normalize, _en_word),
}
