"""Per-word language tagging for bilingual (Vietnamese + English) text.

Modes: "vi" (default for Vietnamese devices), "en", "auto" (decided per sentence) for the vi-en
token set, and "zh" for the zh-en token set.
- A word with Vietnamese letters (diacritics or đ) is always Vietnamese.
- Words with digits or symbols are "neutral" and are read in the sentence's language.
- In "vi" mode a plain Latin word stays Vietnamese when it is a valid syllable (so unaccented
  Vietnamese still reads as Vietnamese), a known loanword or abbreviation, or a short all-caps
  acronym (spelled the Vietnamese way); any other Latin word is English.
- In "en" mode every plain Latin word is English.
- In "zh" mode a word with Han characters is Chinese and every plain Latin word is English.
  Chinese is written without spaces, so boundaries are first inserted between Han characters,
  Chinese punctuation and other text ("打开Wi-Fi设置" -> 打开 / Wi-Fi / 设置).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from .lexicon import ABBREVIATIONS, LOANWORDS
from .syllable import parse_syllable

EDGE = ".,;:!?\"'()[]{}…“”‘’«»–—"
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+|(?<=[。！？；])\s*")
VI_RATIO = 0.2


def _core(chunk: str) -> str:
    return chunk.strip(EDGE)


def _has_vietnamese_letters(word: str) -> bool:
    return any(ch.isalpha() and not ch.isascii() for ch in unicodedata.normalize("NFC", word))


def _is_plain_latin(word: str) -> bool:
    return bool(word) and all(ch.isascii() and (ch.isalpha() or ch in "-'") for ch in word) \
        and any(ch.isalpha() for ch in word)


def _has_han(word: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in word)


def _script_class(ch: str) -> int:
    if "\u4e00" <= ch <= "\u9fff":
        return 1
    if "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef" or ch in "“”‘’…—·":
        return 2
    return 0


def split_scripts(sentence: str) -> str:
    """Spaces between Han, Chinese punctuation and other text (Chinese has no spaces)."""
    out: list[str] = []
    prev = None
    for ch in sentence:
        if ch.isspace():
            prev = None
            out.append(ch)
            continue
        cls = _script_class(ch)
        if prev is not None and cls != prev:
            out.append(" ")
        out.append(ch)
        prev = cls
    return "".join(out)


# Languages each mode can produce (its token set): a script rule for another language is skipped.
MODE_LANGS = {"vi": ("vi", "en"), "en": ("vi", "en"), "auto": ("vi", "en"), "zh": ("zh", "en")}


def sentence_lang(sentence: str, mode: str) -> str:
    if mode in ("vi", "en", "zh"):
        return mode
    words = [_core(c) for c in sentence.split()]
    words = [w for w in words if any(ch.isalpha() for ch in w)]
    if not words:
        return "vi"
    ratio = sum(_has_vietnamese_letters(w) for w in words) / len(words)
    return "vi" if ratio >= VI_RATIO else "en"


# Words written in a language's own script or letters belong to it in every mode whose token set
# has that language. A language with its own script adds its rule before "vi", whose rule is
# "any non-ASCII letter" (so Han text in a vi-en mode is handled exactly as before). Plain Latin
# words are decided by the rules below.
SCRIPT_RULES: list[tuple[str, Callable[[str], bool]]] = [
    ("zh", _has_han),
    ("vi", _has_vietnamese_letters),
]


def word_lang(core: str, mode: str) -> str:
    if not core:
        return "neutral"
    allowed = MODE_LANGS.get(mode, ("vi", "en"))
    for code, rule in SCRIPT_RULES:
        if code in allowed and rule(core):
            return code
    if not _is_plain_latin(core):
        return "neutral"
    if mode in ("en", "zh"):
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
    if mode == "zh":
        sentence = split_scripts(sentence)
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
