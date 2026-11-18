"""Per-word language tagging for bilingual (Vietnamese + English) text.

Modes: "vi" (default for Vietnamese devices), "en", "auto" (decided per sentence) for the vi-en
token set, "zh" for the zh-en token set, "ko" for the ko-en token set and "ja" for the ja-en
token set.
- A word with Vietnamese letters (diacritics or đ) is always Vietnamese.
- Words with digits or symbols are "neutral" and are read in the sentence's language.
- In "vi" mode a plain Latin word stays Vietnamese when it is a valid syllable (so unaccented
  Vietnamese still reads as Vietnamese), a known loanword or abbreviation, or a short all-caps
  acronym (spelled the Vietnamese way); any other Latin word is English.
- In "en" mode every plain Latin word is English.
- In "zh" mode a word with Han characters is Chinese and every plain Latin word is English.
  Chinese is written without spaces, so boundaries are first inserted between Han characters,
  Chinese punctuation and other text ("打开Wi-Fi设置" -> 打开 / Wi-Fi / 设置).
- In "ko" mode a word with Hangul is Korean and every plain Latin word is English. Korean is
  written with spaces between words, so no boundaries are inserted ("Wi-Fi를" is one Korean
  word; the Korean normalizer hands its Latin part to the English normalizer).
- In "ja" mode a word with kana or kanji is Japanese and every plain Latin word is English.
  Japanese is written without spaces, so boundaries are inserted as for Chinese, with kana and
  kanji as one script ("Wi-Fiを設定" -> Wi-Fi / を設定).
- In the Latin-script pair modes ("es", "id", "pt") a word with the language's own letters (á, ñ ...)
  is that language and a plain Latin word is decided by latin.latin_word_lang (word lists,
  CamelCase, acronyms, then whether its spelling fits the language); ¿ and ¡ are dropped.
- In "hi" mode a word with Devanagari is Hindi and a plain Latin word is English, except the
  multi-letter units and currency words of the Hindi normalizer (km, GB, Rs), which are read with
  their number in Hindi. The danda । and double danda ॥ end a sentence (in every mode).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from .latin import LATIN_PAIRS, has_letters_of, latin_word_lang
from .lexicon import ABBREVIATIONS, LOANWORDS
from .phoneme_set import PAIR_MODES
from .syllable import parse_syllable

EDGE = ".,;:!?\"'()[]{}…“”‘’«»–—"
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+|(?<=[。！？；।॥])\s*")
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


def _has_hangul(word: str) -> bool:
    """Hangul syllables or compatibility jamo."""
    return any("\uac00" <= ch <= "\ud7a3" or "\u3131" <= ch <= "\u318e" for ch in word)


def _has_japanese(word: str) -> bool:
    """Kana or kanji (a rule only in modes whose token set has Japanese, so Han text stays
    Chinese in the zh mode)."""
    return any(_script_class_ja(ch) == 1 for ch in word)


def _has_devanagari(word: str) -> bool:
    """Devanagari letters or signs (not only digits or the danda)."""
    from .hi.g2p_hi import is_devanagari_word

    return is_devanagari_word(word)


def _script_class_ja(ch: str) -> int:
    """1: kanji, kana, 々 〆 ー; 2: Japanese and full-width punctuation (・ 「」 、。); 0: other."""
    if ("\u4e00" <= ch <= "\u9fff" or ("\u3040" <= ch <= "\u30ff" and ch != "・")
            or ch in "々〆" or "\uff66" <= ch <= "\uff9f"):
        return 1
    if "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef" or ch in "“”‘’…—・":
        return 2
    return 0


def _script_class(ch: str) -> int:
    if "\u4e00" <= ch <= "\u9fff":
        return 1
    if "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef" or ch in "“”‘’…—·":
        return 2
    return 0


def split_scripts(sentence: str, classify: Callable[[str], int] = _script_class) -> str:
    """Spaces between Han, Chinese punctuation and other text (Chinese has no spaces); with
    classify=_script_class_ja, between Japanese characters, Japanese punctuation and other text."""
    out: list[str] = []
    prev = None
    for ch in sentence:
        if ch.isspace():
            prev = None
            out.append(ch)
            continue
        cls = classify(ch)
        if prev is not None and cls != prev:
            out.append(" ")
        out.append(ch)
        prev = cls
    return "".join(out)


# Languages each mode can produce (its token set): a script rule for another language is skipped.
MODE_LANGS = {"vi": ("vi", "en"), "en": ("vi", "en"), "auto": ("vi", "en"),
              **{mode: (mode, "en") for mode in PAIR_MODES}}


def sentence_lang(sentence: str, mode: str) -> str:
    if mode in ("vi", "en") or mode in PAIR_MODES:
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
    ("ja", _has_japanese),
    ("zh", _has_han),
    ("ko", _has_hangul),
    ("hi", _has_devanagari),
    *((code, has_letters_of(code)) for code in LATIN_PAIRS),
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
    if mode in LATIN_PAIRS:
        return latin_word_lang(core, mode)
    if mode == "hi":
        from .hi.normalize_hi import LATIN_WORDS

        return "hi" if core in LATIN_WORDS else "en"
    if mode == "en" or mode in PAIR_MODES:
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
    elif mode == "ja":
        sentence = split_scripts(sentence, _script_class_ja)
    elif mode in LATIN_PAIRS:  # ¿Abriste Netflix? -> Abriste / Netflix
        sentence = sentence.replace("¿", " ").replace("¡", " ")
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
