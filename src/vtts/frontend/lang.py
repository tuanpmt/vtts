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
- In "th" mode a word with Thai letters is Thai and every plain Latin word is English. Thai is
  written without spaces between words; a space is put between Thai and Latin letters
  ("เปิดWi-Fiให้" -> เปิด / Wi-Fi / ให้). Spaces between Thai runs are pauses (th/normalize_th).
- In the Latin-script pair modes ("es", "id", "pt", "it", "tr", "pl", "fi", "ms", "tl",
  "sw", "da") a word with the language's own
  letters (á, ñ ...) is that language and a plain Latin word is decided by latin.latin_word_lang
  (word lists, CamelCase, acronyms, then whether its spelling fits the language); ¿ and ¡ are
  dropped. In "it" and "tr" ’ is read as ' and latin.split_elision splits an elided Italian word
  before an English one (sull'iPhone) and a Turkish suffix after an English word (iPhone'da).
- In "lo" mode a word with Lao letters is Lao and every plain Latin word is English; as in "th" a
  space is put between Lao and Latin letters, and a dot after a Lao letter does not end a sentence.
- In "km" mode a word with Khmer letters is Khmer and every plain Latin word is English; as in
  "th", a space is put between Khmer and Latin letters and spaces between Khmer runs are pauses.
  The Khmer full stops ។ ៕ end a sentence (in every mode).
- In "my" mode a word with Burmese letters (Unicode or Zawgyi) is Burmese and every plain Latin
  word is English; a space is put between Burmese and Latin letters. Spaces between Burmese runs
  are word boundaries (not pauses). The Burmese full stop ။ ends a sentence (in every mode).
- In "hi" mode a word with Devanagari is Hindi and a plain Latin word is English, except the
  multi-letter units and currency words of the Hindi normalizer (km, GB, Rs), which are read with
  their number in Hindi. The danda । and double danda ॥ end a sentence (in every mode).
- In "fr" mode words are tagged like the other Latin-script pairs (French letters à â æ ç é è ê ë
  î ï ô œ ù û ü ÿ), and an elided clitic takes the language of its word (_fr_tags).
- "de" is a Latin-script pair (own letters ä ö ü ß); its sentences are split by
  de.normalize_de.split_sentences_de, which does not cut after an ordinal dot (am 3. Mai) or an
  abbreviation (z. B.).
- In "ru" mode a word with Cyrillic letters is Russian and a plain Latin word is English, except
  the multi-letter units and currency codes of the Russian normalizer (km, GB, USD). A full stop
  followed by a lower-case Cyrillic letter does not end a sentence (т. е., г. москва, ул. ленина),
  in every mode.
- In "ar" mode a word with Arabic letters is Arabic and a plain Latin word is English, except the
  multi-letter units and currency words of the Arabic normalizer (km, GB, USD). Arabic is written
  right to left, but Unicode text is stored in reading order, so no reordering is needed. The
  Arabic question mark ؟, semicolon ؛ and full stop ۔ end a sentence like ? ; . (in every mode);
  the Arabic comma ، is stripped from word edges like ",".
- "nl", "sv" and "no" are Latin-script pairs (latin.py); their sentences are split by
  scan_norm.split_sentences, which does not cut after an abbreviation of the language's table
  (o.a., t.ex.), an initial or (no) an ordinal dot (17. mai).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from .latin import APOSTROPHE_MODES, LATIN_PAIRS, has_letters_of, latin_word_lang, split_elision
from .lexicon import ABBREVIATIONS, LOANWORDS
from .phoneme_set import PAIR_MODES
from .syllable import parse_syllable

EDGE = ".,;:!?\"'()[]{}…“”‘’«»–—،؛؟"
# A dot after a Thai letter ends an abbreviation (พ.ศ. 2567, 14.30 น.), not a sentence.
# A full stop before a lower-case Cyrillic letter ends an abbreviation (т. е., ул. ленина).
# The Khmer full stops ។ ៕ end a sentence; a dot after a Khmer letter ends an abbreviation (ព.ស.).
# The Burmese full stop ။ ends a sentence.
SENTENCE_END = re.compile(r"(?<=[!?;؟؛۔])\s+|(?<=\.)(?<![\u0e01-\u0e4e]\.)(?<![\u1780-\u17dd]\.)\s+(?![\sа-яё])"
                          r"|(?<=[。！？；।॥\u17d4\u17d5\u104b])\s*")
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


def _has_thai(word: str) -> bool:
    return any("\u0e01" <= ch <= "\u0e4e" for ch in word)


THAI_LATIN = re.compile(r"(?<=[\u0e01-\u0e4e])(?=[A-Za-z])|(?<=[A-Za-z])(?=[\u0e01-\u0e4e])")
_LAO = "\u0e81-\u0ecd\u0edc-\u0edf"
LAO_LATIN = re.compile(rf"(?<=[{_LAO}])(?=[A-Za-z])|(?<=[A-Za-z])(?=[{_LAO}])")


def _has_lao(word: str) -> bool:
    return any("\u0e81" <= ch <= "\u0ecd" or "\u0edc" <= ch <= "\u0edf" for ch in word)


def _has_khmer(word: str) -> bool:
    """Khmer letters or signs (not only digits or punctuation)."""
    from .km.g2p_km import is_khmer

    return any(is_khmer(ch) for ch in word)


def _has_burmese(word: str) -> bool:
    """Burmese letters or signs (U+1000..U+109F without the digits and ၊ ။: Zawgyi text too)."""
    return any("\u1000" <= ch <= "\u109f" and not "\u1040" <= ch <= "\u104b" for ch in word)


BURMESE_LATIN = re.compile(r"(?<=[\u1000-\u103f\u104c-\u109f])(?=[A-Za-z])"
                           r"|(?<=[A-Za-z])(?=[\u1000-\u103f\u104c-\u109f])")
KHMER_LATIN = re.compile(r"(?<=[\u1780-\u17d3\u17d7\u17dd])(?=[A-Za-z])"
                         r"|(?<=[A-Za-z])(?=[\u1780-\u17d3\u17d7\u17dd])")


def _has_japanese(word: str) -> bool:
    """Kana or kanji (a rule only in modes whose token set has Japanese, so Han text stays
    Chinese in the zh mode)."""
    return any(_script_class_ja(ch) == 1 for ch in word)


def _has_devanagari(word: str) -> bool:
    """Devanagari letters or signs (not only digits or the danda)."""
    from .hi.g2p_hi import is_devanagari_word

    return is_devanagari_word(word)


def _has_cyrillic(word: str) -> bool:
    return any("\u0400" <= ch <= "\u04ff" for ch in word)


def _has_arabic(word: str) -> bool:
    """Arabic letters (not only Arabic digits or punctuation)."""
    from .ar.g2p_ar import is_arabic_word

    return is_arabic_word(word)


def _has_greek(word: str) -> bool:
    """Greek letters (not only signs such as the ano teleia)."""
    from .el.g2p_el import is_greek_word

    return is_greek_word(word)


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
    ("th", _has_thai),
    ("ru", _has_cyrillic),
    ("ar", _has_arabic),
    ("el", _has_greek),
    *((code, has_letters_of(code)) for code in LATIN_PAIRS),
    ("vi", _has_vietnamese_letters),
]
SCRIPT_RULES.insert(len(SCRIPT_RULES) - 1, ("lo", _has_lao))  # before the catch-all "vi" rule
SCRIPT_RULES.insert(-1, ("km", _has_khmer))
SCRIPT_RULES.insert(-1, ("my", _has_burmese))


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
    if mode == "ru":
        from .ru.normalize_ru import LATIN_WORDS as RU_LATIN

        return "ru" if core in RU_LATIN else "en"
    if mode == "ar":
        from .ar.normalize_ar import LATIN_WORDS as AR_LATIN_WORDS

        return "ar" if core in AR_LATIN_WORDS else "en"
    if mode == "el":
        from .el.normalize_el import LATIN_WORDS as EL_LATIN_WORDS

        return "el" if core in EL_LATIN_WORDS else "en"
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
    elif mode == "th":  # เปิดWi-Fiให้ -> เปิด / Wi-Fi / ให้ (Thai words have no spaces)
        sentence = THAI_LATIN.sub(" ", sentence)
    elif mode == "lo":  # ເປີດWi-Fiໃຫ້ -> ເປີດ / Wi-Fi / ໃຫ້
        sentence = LAO_LATIN.sub(" ", sentence)
    elif mode == "km":  # បើកWi-Fi -> បើក / Wi-Fi (Khmer words have no spaces)
        sentence = KHMER_LATIN.sub(" ", sentence)
    elif mode == "my":  # ဖွင့်Wi-Fi -> ဖွင့် / Wi-Fi
        sentence = BURMESE_LATIN.sub(" ", sentence)
    elif mode in LATIN_PAIRS:  # ¿Abriste Netflix? -> Abriste / Netflix
        sentence = sentence.replace("¿", " ").replace("¡", " ")
    elif mode == "el":  # the Greek question mark ; (U+037E) -> ? (also for an English word before it)
        sentence = sentence.replace(";", "?").replace("\u037e", "?")
    if mode == "fr":
        return [t for c in sentence.split() for t in _fr_tags(c, lang)]
    if mode in APOSTROPHE_MODES:  # sull’iPhone -> sull' / iPhone (an English word after an elision)
        sentence = sentence.replace("’", "'")
        return [(c, word_lang(_core(c), lang)) for w in sentence.split() for c in split_elision(w, mode)]
    tags = [(c, word_lang(_core(c), lang)) for c in sentence.split()]
    if mode in CONTEXT_PAIRS:
        tags = _by_context(tags, mode)
    return tags


# Latin-script pairs whose most frequent words are also English words (Finnish on, he, home): a
# word in both lexicons/<mode>/native.txt and lexicons/latin/english.txt is English when the
# nearest tagged word on each side (or the only one) is English ("Turn on the light"), else the
# main language ("Spotify on hyvä").
CONTEXT_PAIRS = frozenset(("fi",))


def _by_context(tags: list[tuple[str, str]], mode: str) -> list[tuple[str, str]]:
    from .lexicons import load_words

    both = load_words(mode, "native") & load_words("latin", "english")
    amb = [_core(c).lower() in both and t == mode for c, t in tags]

    def side(k: int, step: int) -> str | None:
        k += step
        while 0 <= k < len(tags):
            if not amb[k] and tags[k][1] != "neutral":
                return tags[k][1]
            k += step
        return None

    out = []
    for k, (c, t) in enumerate(tags):
        if amb[k]:
            near = {x for x in (side(k, -1), side(k, 1)) if x is not None}
            if near == {"en"}:
                t = "en"
        out.append((c, t))
    return out


# French: an elided clitic (l' d' qu' jusqu' ...) takes the language of the word it is glued to,
# and is split from an English word (l'iPhone -> l' / iPhone); in a hyphenated word one-letter
# parts (a-t-il) are ignored and the word is French unless a part is English.
FR_ROMAN_ORDINAL = re.compile(r"[IVXLC]+(?:e|er|re|ème)")
FR_CLITICS = ("l", "d", "j", "m", "t", "s", "n", "c", "qu", "jusqu", "lorsqu", "puisqu", "quoiqu")
FR_ELISION = re.compile(r"^([\"“«(]*(?:" + "|".join(FR_CLITICS) + r")['’])(.+)$", re.IGNORECASE)


def _fr_tags(chunk: str, lang: str) -> list[tuple[str, str]]:
    m = FR_ELISION.match(chunk)
    if m and not chunk.lower().startswith(("aujourd'hui", "aujourd’hui")):
        rest = word_lang(_core(m.group(2)), lang)
        if rest == "en":
            return [(m.group(1), "fr"), (m.group(2), "en")]
        return [(chunk, rest)]
    core = _core(chunk)
    if FR_ROMAN_ORDINAL.fullmatch(core):  # XXIe siècle: read by the French normalizer
        return [(chunk, "neutral")]
    tag = word_lang(core, lang)
    if tag == "en" and "-" in core:
        parts = [p for p in core.split("-") if len(p) > 1]
        if parts and all(word_lang(p, lang) != "en" for p in parts):
            return [(chunk, "fr")]
    return [(chunk, tag)]


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


# tr: a dot after a number followed by a lower-case word is an ordinal (5. sınıf), not a sentence end.
SENTENCE_END_TR = re.compile(r"(?<=[!?;؟؛۔])\s+|(?<=\.)(?<![\u0e01-\u0e4e]\.)(?<![\u1780-\u17dd]\.)(?<!\d\.)\s+"
                             r"(?![\sа-яё])|(?<=\d\.)\s+(?![a-zçğıöşüâîû])(?!\s*[а-яё])"
                             r"|(?<=[。！？；।॥\u17d4\u17d5\u104b])\s*")


# Modes whose sentences start with a capital letter: a dot followed by a lower-case letter of the
# language or a digit 0-9 ends an abbreviation or an ordinal (fi: n. 50, esim. kissa,
# 3. toukokuuta; el: χλμ. σε; da: den 5. marts, kl. 14.30, ca. 3,5 %), not a sentence.
DOT_CONTINUES = {
    "fi": "0123456789abcdefghijklmnopqrstuvwxyzåäöšž",
    "el": "0123456789αβγδεζηθικλμνξοπρσςτυφχψωάέήίόύώϊϋΐΰ",
    "da": "0123456789abcdefghijklmnopqrstuvwxyzæøåé",
}
# Modes where a dot after a letter of the language ends an abbreviation, not a sentence (Lao ຄ.ສ.,
# as SENTENCE_END does for Thai in every mode).
DOT_AFTER_LETTER = {"lo": _has_lao}


def split_sentences_raw(text: str, mode: str | None = None) -> list[str]:
    """Sentences of a text; mode "tr" keeps an ordinal dot (5. sınıf) inside the sentence, "de" uses
    its own splitter as do "nl", "sv", "no" (scan_norm), "fi", "el" and "da" join a part that starts after a dot
    with a DOT_CONTINUES character, "lo" a part after a dot that follows a Lao letter (DOT_AFTER_LETTER)."""
    if mode == "de":  # ordinals and abbreviations end with a dot (am 3. Mai, z. B.)
        from .de.normalize_de import split_sentences_de

        return split_sentences_de(text)
    if mode in ("nl", "sv", "no"):  # abbreviations and (no) ordinals end with a dot
        import importlib

        from .scan_norm import split_sentences

        norm = importlib.import_module(f"vtts.frontend.{mode}.normalize_{mode}")
        return split_sentences(text, norm.spec())
    pattern = SENTENCE_END_TR if mode == "tr" else SENTENCE_END
    parts = [s for s in pattern.split(text.strip()) if s.strip()]
    if mode not in DOT_CONTINUES and mode not in DOT_AFTER_LETTER:
        return parts
    out: list[str] = []
    for p in parts:
        if out and out[-1].endswith(".") and (
            (mode in DOT_CONTINUES and p[0] in DOT_CONTINUES[mode])
            or (mode in DOT_AFTER_LETTER and len(out[-1]) >= 2 and DOT_AFTER_LETTER[mode](out[-1][-2]))
        ):
            out[-1] += " " + p
        else:
            out.append(p)
    return out
