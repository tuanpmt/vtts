"""Per-word language tagging for bilingual (Vietnamese + English) text.

Modes: "vi" (default for Vietnamese devices), "en", "auto" (decided per sentence).
- A word with Vietnamese letters (diacritics or đ) is always Vietnamese.
- Words with digits or symbols are "neutral" and are read in the sentence's language.
- In "vi" mode a plain Latin word stays Vietnamese when it is a valid syllable (so unaccented
  Vietnamese still reads as Vietnamese), a known loanword or abbreviation, or a short all-caps
  acronym (spelled the Vietnamese way); any other Latin word is English.
- In "en" mode every plain Latin word is English.
"""

from __future__ import annotations

import re
import unicodedata

from .lexicon import ABBREVIATIONS, LOANWORDS
from .syllable import parse_syllable

EDGE = ".,;:!?\"'()[]{}…“”‘’«»–—"
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")
VI_RATIO = 0.2


def _core(chunk: str) -> str:
    return chunk.strip(EDGE)


def _has_vietnamese_letters(word: str) -> bool:
    return any(ch.isalpha() and not ch.isascii() for ch in unicodedata.normalize("NFC", word))


def _is_plain_latin(word: str) -> bool:
    return bool(word) and all(ch.isascii() and (ch.isalpha() or ch in "-'") for ch in word) \
        and any(ch.isalpha() for ch in word)


def sentence_lang(sentence: str, mode: str) -> str:
    if mode in ("vi", "en"):
        return mode
    words = [_core(c) for c in sentence.split()]
    words = [w for w in words if any(ch.isalpha() for ch in w)]
    if not words:
        return "vi"
    ratio = sum(_has_vietnamese_letters(w) for w in words) / len(words)
    return "vi" if ratio >= VI_RATIO else "en"


def word_lang(core: str, mode: str) -> str:
    if not core or _has_vietnamese_letters(core):
        return "vi" if core else "neutral"
    if not _is_plain_latin(core):
        return "neutral"
    if mode == "en":
        return "en"
    parts = [p for p in re.split(r"[-']", core) if p]
    if all(parse_syllable(p.lower()) is not None for p in parts):
        return "vi"
    if core.lower() in LOANWORDS or core in ABBREVIATIONS:
        return "vi"
    if all(p.isupper() and len(p) <= 5 for p in parts):
        return "vi"
    return "en"


def tag_words(sentence: str, mode: str) -> list[tuple[str, str]]:
    """(whitespace-separated chunk, "vi" | "en" | "neutral") for one sentence."""
    lang = sentence_lang(sentence, mode)
    return [(c, word_lang(_core(c), lang)) for c in sentence.split()]


def runs(sentence: str, mode: str) -> list[tuple[str, str]]:
    """Consecutive chunks of one language joined back into text; neutral chunks take the
    sentence's language."""
    lang = sentence_lang(sentence, mode)
    out: list[tuple[str, str]] = []
    for chunk, tag in tag_words(sentence, mode):
        tag = lang if tag == "neutral" else tag
        if out and out[-1][1] == tag:
            out[-1] = (out[-1][0] + " " + chunk, tag)
        else:
            out.append((chunk, tag))
    return out


def split_sentences_raw(text: str) -> list[str]:
    return [s for s in SENTENCE_END.split(text.strip()) if s.strip()]
