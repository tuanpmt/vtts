"""Language modules of the bilingual (phoneme set v2) front-end.

Adding a language means adding one entry here (and its tagging rule in lang.py); sentence
splitting, chunk packing and the device protocol are shared. Each module provides:

- normalize(run_text) -> str: the words of one same-language run, lower case, with the
  punctuation tokens , . ? ! ; : separated by single spaces.
- word_tokens(word) -> list[str]: tokens (phoneme set v2) of one normalized word; [] when the
  word cannot be pronounced (it is then skipped).
- word_units(word) -> list[list[str]] (optional): the same tokens split into syllables, for
  languages written without spaces (zh): a "word" is then a whole Han run, its syllables are
  joined without the SPACE token and each counts as one word for chunk packing. Thai (th) does
  the same with the syllables of a Thai run (a space between Thai runs is a pause). Japanese (ja)
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


def _es_normalize(text: str) -> str:
    from .es.normalize_es import normalize_es

    return normalize_es(text)


def _es_word(word: str) -> list[str]:
    from .es.g2p_es import word_tokens_es

    return word_tokens_es(word)


def _id_normalize(text: str) -> str:
    from .id.normalize_id import normalize_id

    return normalize_id(text)


def _id_word(word: str) -> list[str]:
    from .id.g2p_id import word_tokens_id

    return word_tokens_id(word)


def _pt_normalize(text: str) -> str:
    from .pt.normalize_pt import normalize_pt

    return normalize_pt(text)


def _pt_word(word: str) -> list[str]:
    from .pt.g2p_pt import word_tokens_pt

    return word_tokens_pt(word)


def _hi_normalize(text: str) -> str:
    from .hi.normalize_hi import normalize_hi

    return normalize_hi(text)


def _hi_word(word: str) -> list[str]:
    """A Devanagari word; a Latin word (from a mixed chunk) is read in English."""
    from .hi.g2p_hi import is_devanagari_word, word_tokens_hi

    return word_tokens_hi(word) if is_devanagari_word(word) else _en_word(word)


def _th_normalize(text: str) -> str:
    from .th.normalize_th import normalize_th

    return normalize_th(text)


def _th_units(word: str) -> list[list[str]]:
    """Syllables of a Thai run (words found by the word list, see th/g2p_th.py); a Latin word is
    read by the English module."""
    from .th.g2p_th import thai_syllable_tokens
    from .th.normalize_th import is_thai_word

    if is_thai_word(word):
        return thai_syllable_tokens(word)
    toks = _en_word(word)
    return [toks] if toks else []


def _th_word(word: str) -> list[str]:
    return [t for unit in _th_units(word) for t in unit]


def _fr_normalize(text: str) -> str:
    from .fr.normalize_fr import normalize_fr

    return normalize_fr(text)


def _fr_word(word: str) -> list[str]:
    from .fr.g2p_fr import word_tokens_fr

    return word_tokens_fr(word)


def _de_normalize(text: str) -> str:
    from .de.normalize_de import normalize_de

    return normalize_de(text)


def _de_word(word: str) -> list[str]:
    from .de.g2p_de import word_tokens_de

    return word_tokens_de(word)


def _it_normalize(text: str) -> str:
    from .it.normalize_it import normalize_it

    return normalize_it(text)


def _it_word(word: str) -> list[str]:
    from .it.g2p_it import word_tokens_it

    return word_tokens_it(word)


def _tr_normalize(text: str) -> str:
    from .tr.normalize_tr import normalize_tr

    return normalize_tr(text)


def _tr_word(word: str) -> list[str]:
    from .tr.g2p_tr import word_tokens_tr

    return word_tokens_tr(word)


def _ru_normalize(text: str) -> str:
    from .ru.normalize_ru import normalize_ru

    return normalize_ru(text)


def _ru_word(word: str) -> list[str]:
    """A Cyrillic word; a Latin word (from a mixed chunk) is read in English."""
    from .ru.g2p_ru import is_ru_word, word_tokens_ru

    return word_tokens_ru(word) if is_ru_word(word) else _en_word(word)


def _pl_normalize(text: str) -> str:
    from .pl.normalize_pl import normalize_pl

    return normalize_pl(text)


def _pl_word(word: str) -> list[str]:
    from .pl.g2p_pl import word_tokens_pl

    return word_tokens_pl(word)


def _ar_normalize(text: str) -> str:
    from .ar.normalize_ar import normalize_ar

    return normalize_ar(text)


def _ar_word(word: str) -> list[str]:
    """An Arabic word (vowels restored, see ar/g2p_ar.py); a Latin word is read in English."""
    from .ar.g2p_ar import is_arabic_word, word_tokens_ar

    return word_tokens_ar(word) if is_arabic_word(word) else _en_word(word)


def _fi_normalize(text: str) -> str:
    from .fi.normalize_fi import normalize_fi

    return normalize_fi(text)


def _fi_word(word: str) -> list[str]:
    from .fi.g2p_fi import word_tokens_fi

    return word_tokens_fi(word)


def _el_normalize(text: str) -> str:
    from .el.normalize_el import normalize_el

    return normalize_el(text)


def _el_word(word: str) -> list[str]:
    """A Greek word; a Latin word (from a mixed chunk) is read in English."""
    from .el.g2p_el import is_greek_word, word_tokens_el

    return word_tokens_el(word) if is_greek_word(word) else _en_word(word)


def _ms_normalize(text: str) -> str:
    from .ms.normalize_ms import normalize_ms

    return normalize_ms(text)


def _ms_word(word: str) -> list[str]:
    from .ms.g2p_ms import word_tokens_ms

    return word_tokens_ms(word)


def _tl_normalize(text: str) -> str:
    from .tl.normalize_tl import normalize_tl

    return normalize_tl(text)


def _tl_word(word: str) -> list[str]:
    from .tl.g2p_tl import word_tokens_tl

    return word_tokens_tl(word)


def _sw_normalize(text: str) -> str:
    from .sw.normalize_sw import normalize_sw

    return normalize_sw(text)


def _sw_word(word: str) -> list[str]:
    from .sw.g2p_sw import word_tokens_sw

    return word_tokens_sw(word)


def _nl_normalize(text: str) -> str:
    from .nl.normalize_nl import normalize_nl

    return normalize_nl(text)


def _nl_word(word: str) -> list[str]:
    from .nl.g2p_nl import word_tokens_nl

    return word_tokens_nl(word)


def _sv_normalize(text: str) -> str:
    from .sv.normalize_sv import normalize_sv

    return normalize_sv(text)


def _sv_word(word: str) -> list[str]:
    from .sv.g2p_sv import word_tokens_sv

    return word_tokens_sv(word)


def _no_normalize(text: str) -> str:
    from .no.normalize_no import normalize_no

    return normalize_no(text)


def _no_word(word: str) -> list[str]:
    from .no.g2p_no import word_tokens_no

    return word_tokens_no(word)


LANGUAGES: dict[str, LanguageModule] = {
    "vi": LanguageModule("vi", _vi_normalize, _vi_word),
    "en": LanguageModule("en", _en_normalize, _en_word),
    "zh": LanguageModule("zh", _zh_normalize, _zh_word, _zh_units),
    "ko": LanguageModule("ko", _ko_normalize, _ko_word, _ko_units),
    "ja": LanguageModule("ja", _ja_normalize, _ja_word, _ja_units),
    "es": LanguageModule("es", _es_normalize, _es_word),
    "id": LanguageModule("id", _id_normalize, _id_word),
    "pt": LanguageModule("pt", _pt_normalize, _pt_word),
    "hi": LanguageModule("hi", _hi_normalize, _hi_word),
    "th": LanguageModule("th", _th_normalize, _th_word, _th_units),
    "it": LanguageModule("it", _it_normalize, _it_word),
    "tr": LanguageModule("tr", _tr_normalize, _tr_word),
    "ru": LanguageModule("ru", _ru_normalize, _ru_word),
    "pl": LanguageModule("pl", _pl_normalize, _pl_word),
    "ar": LanguageModule("ar", _ar_normalize, _ar_word),
}
LANGUAGES["nl"] = LanguageModule("nl", _nl_normalize, _nl_word)
LANGUAGES["sv"] = LanguageModule("sv", _sv_normalize, _sv_word)
LANGUAGES["no"] = LanguageModule("no", _no_normalize, _no_word)
LANGUAGES["fr"] = LanguageModule("fr", _fr_normalize, _fr_word)
LANGUAGES["de"] = LanguageModule("de", _de_normalize, _de_word)
LANGUAGES["fi"] = LanguageModule("fi", _fi_normalize, _fi_word)
LANGUAGES["el"] = LanguageModule("el", _el_normalize, _el_word)
LANGUAGES["ms"] = LanguageModule("ms", _ms_normalize, _ms_word)
LANGUAGES["tl"] = LanguageModule("tl", _tl_normalize, _tl_word)
LANGUAGES["sw"] = LanguageModule("sw", _sw_normalize, _sw_word)
