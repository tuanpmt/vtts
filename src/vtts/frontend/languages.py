"""Language modules of the bilingual (phoneme set v2) front-end.

Adding a language means adding one entry here (and its tagging rule in lang.py); sentence
splitting, chunk packing and the device protocol are shared. Each module provides:

- normalize(run_text) -> str: the words of one same-language run, lower case, with the
  punctuation tokens , . ? ! ; : separated by single spaces.
- word_tokens(word) -> list[str]: tokens (phoneme set v2) of one normalized word; [] when the
  word cannot be pronounced (it is then skipped).
- word_units(word) -> list[list[str]] (optional): the same tokens split into syllables, for
  languages written without spaces (zh): a "word" is then a whole Han run, its syllables are
  joined without the SPACE token and each counts as one word for chunk packing.

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
    word_units: Callable[[str], list[list[str]]] | None = None


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


def _zh_normalize(text: str) -> str:
    from .zh.normalize_zh import normalize_zh

    return normalize_zh(text)


def _zh_units(word: str) -> list[list[str]]:
    """Syllables of a Han run; a Latin word (letters of a code) is read by the English module."""
    from .zh.g2p_zh import han_syllable_tokens
    from .zh.normalize_zh import is_han_word

    if is_han_word(word):
        return han_syllable_tokens(word)
    toks = _en_word(word)
    return [toks] if toks else []


def _zh_word(word: str) -> list[str]:
    return [t for unit in _zh_units(word) for t in unit]


LANGUAGES: dict[str, LanguageModule] = {
    "vi": LanguageModule("vi", _vi_normalize, _vi_word),
    "en": LanguageModule("en", _en_normalize, _en_word),
    "zh": LanguageModule("zh", _zh_normalize, _zh_word, _zh_units),
}
