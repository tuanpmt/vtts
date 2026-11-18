"""Language modules of the bilingual (phoneme set v2) front-end.

Adding a language means adding one entry here (and its tagging rule in lang.py); sentence
splitting, chunk packing and the device protocol are shared. Each module provides:

- normalize(run_text) -> str: the words of one same-language run, lower case, with the
  punctuation tokens , . ? ! ; : separated by single spaces.
- word_tokens(word) -> list[str]: tokens (phoneme set v2) of one normalized word; [] when the
  word cannot be pronounced (it is then skipped).
- word_units(word) -> list[list[str]] (optional): the same tokens split into syllables, for
  languages written without spaces (zh): a "word" is then a whole Han run, its syllables are
  joined without the SPACE token and each counts as one word for chunk packing. Japanese (ja)
  does the same with table words, single kanji and short kana runs as units. Korean (ko)
  returns one unit per word and splits only a word too long for one chunk.

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


def _ko_normalize(text: str) -> str:
    from .ko.normalize_ko import normalize_ko

    return normalize_ko(text)


def _ko_word(word: str) -> list[str]:
    """A Korean word (어절) of Hangul syllables; a Latin word (code letters) is read in English."""
    from .ko.g2p_ko import word_tokens_ko
    from .ko.normalize_ko import is_hangul_word

    return word_tokens_ko(word) if is_hangul_word(word) else _en_word(word)


def _ko_units(word: str) -> list[list[str]]:
    """One unit per word; a word too long for one chunk is split into syllables so the chunk
    packer can cut it."""
    from .ko.g2p_ko import pronounce, syllable_tokens
    from .ko.normalize_ko import is_hangul_word
    from .text import _V2_MAX_TOKENS

    toks = _ko_word(word)
    if len(toks) <= _V2_MAX_TOKENS or not is_hangul_word(word):
        return [toks] if toks else []
    return [syllable_tokens(s) for s in pronounce(word)]


def _ja_normalize(text: str) -> str:
    from .ja.normalize_ja import normalize_ja

    return normalize_ja(text)


def _ja_units(word: str) -> list[list[str]]:
    """Units of a Japanese run (see ja/g2p_ja.ja_units); a Latin word is read in English."""
    from .ja.g2p_ja import ja_units
    from .ja.normalize_ja import is_ja_word

    if is_ja_word(word):
        return ja_units(word)
    toks = _en_word(word)
    return [toks] if toks else []


def _ja_word(word: str) -> list[str]:
    return [t for unit in _ja_units(word) for t in unit]


LANGUAGES: dict[str, LanguageModule] = {
    "vi": LanguageModule("vi", _vi_normalize, _vi_word),
    "en": LanguageModule("en", _en_normalize, _en_word),
    "zh": LanguageModule("zh", _zh_normalize, _zh_word, _zh_units),
    "ko": LanguageModule("ko", _ko_normalize, _ko_word, _ko_units),
    "ja": LanguageModule("ja", _ja_normalize, _ja_word, _ja_units),
}
