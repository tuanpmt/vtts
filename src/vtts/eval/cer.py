"""Character/word error rates on normalized text (Vietnamese tones kept).

lang "vi" (default): the Vietnamese normalizer. "en": the English normalizer. "mixed": words are
kept as written (lower case, punctuation dropped) and only tokens with digits or symbols go
through the Vietnamese normalizer, so English words in Vietnamese sentences are not spelled out.
The same normalization is applied to the reference and to the ASR output.

Pair languages "zh", "ko", "ja" (main-language and mixed sets of the zh-en, ko-en, ja-en pairs):
the text goes through the pair front-end's own normalizers (sentence split, script tagging,
numbers read in the main language, Latin words through the English normalizer), punctuation
dropped. Chinese is converted to Simplified and Japanese katakana to hiragana. CER counts
characters with spaces removed (Han characters, Hangul syllables, kana and kanji, Latin letters),
so the spacing of Korean words and of English terms ("Wi-Fi" / "WiFi") is not an error. WER counts
words: for zh and ja (written without spaces) each Han character or kana is one word and each
Latin word one word (a mixed error rate); for ko the space-separated words (어절), so Korean WER
also counts spacing differences. Japanese CER is orthographic: Whisper writing a word in kanji
where the reference has kana (or the other way round) counts as an error.

Latin-script pair languages (LATIN_PAIR_LANGS: es ...) go through their pair front-end the same
way (numbers read in the main language, English words through the English normalizer, accents
kept, lower case); CER counts characters with the spaces between words, WER counts words."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from vtts.frontend.normalize import normalize
from vtts.frontend.phoneme_set import PUNCTUATION

_STRIP = ".,;:!?\"'()[]{}…“”‘’«»–—-"


def _plain_words(text: str) -> list[str]:
    import unicodedata

    out = []
    for w in unicodedata.normalize("NFC", text).lower().split():
        w = w.strip(_STRIP)
        if w:
            out.append(w)
    return out


LATIN_PAIR_LANGS = ("es", "id", "pt")
PAIR_LANGS = ("zh", "ko", "ja", *LATIN_PAIR_LANGS)
WHISPER_LANGUAGE = {"vi": "vi", "en": "en", "mixed": "vi", "zh": "zh", "ko": "ko", "ja": "ja",
                    **{code: code for code in LATIN_PAIR_LANGS}}


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or ch in "々〆ヶ"


def _pair_words(text: str, lang: str) -> list[str]:
    from vtts.frontend.lang import runs, split_sentences_raw
    from vtts.frontend.languages import LANGUAGES

    if lang == "zh":
        from vtts.data.zh_corpus import to_simplified

        text = to_simplified(text)
    words: list[str] = []
    for sentence in split_sentences_raw(unicodedata.normalize("NFC", text)):
        for run, code in runs(sentence, lang):
            words += [w for w in LANGUAGES[code].normalize(run).split() if w not in PUNCTUATION]
    if lang == "ja":
        from vtts.frontend.ja.kana import to_hiragana

        words = [to_hiragana(w) for w in words]
    if lang == "ko" or lang in LATIN_PAIR_LANGS:
        return words
    out: list[str] = []
    for w in words:  # zh, ja: one unit per character of a CJK word, Latin words whole
        out += list(w) if any(_is_cjk(ch) for ch in w) else [w]
    return out


def prep_for_cer(text: str, lang: str = "vi") -> str:
    if lang in PAIR_LANGS:
        return " ".join(_pair_words(text, lang))
    if lang == "en":
        from vtts.frontend.en.normalize_en import normalize_en

        return " ".join(_plain_words(normalize_en(text)))
    if lang == "mixed":
        words: list[str] = []
        for w in text.split():
            if any(ch.isdigit() for ch in w) or any(ch in "%°$&@+=" for ch in w):
                words += [x for x in normalize(w).split() if x not in PUNCTUATION]
            else:
                words += _plain_words(w)
        return " ".join(words)
    return " ".join(w for w in normalize(text).split() if w not in PUNCTUATION)


def _edits(ref: Sequence, hyp: Sequence) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def _chars(text: str, lang: str) -> str:
    p = prep_for_cer(text, lang)
    return p.replace(" ", "") if lang in PAIR_LANGS and lang not in LATIN_PAIR_LANGS else p


def cer(ref: str, hyp: str, lang: str = "vi") -> float:
    r, h = _chars(ref, lang), _chars(hyp, lang)
    return _edits(r, h) / max(len(r), 1)


def wer(ref: str, hyp: str, lang: str = "vi") -> float:
    r, h = prep_for_cer(ref, lang).split(), prep_for_cer(hyp, lang).split()
    return _edits(r, h) / max(len(r), 1)


def corpus_cer(pairs: list[tuple[str, str]], lang: str = "vi") -> float:
    errs = total = 0
    for ref, hyp in pairs:
        r, h = _chars(ref, lang), _chars(hyp, lang)
        errs += _edits(r, h)
        total += len(r)
    return errs / max(total, 1)


def corpus_wer(pairs: list[tuple[str, str]], lang: str = "vi") -> float:
    errs = total = 0
    for ref, hyp in pairs:
        r, h = prep_for_cer(ref, lang).split(), prep_for_cer(hyp, lang).split()
        errs += _edits(r, h)
        total += len(r)
    return errs / max(total, 1)
