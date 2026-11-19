"""Character/word error rates on normalized text (Vietnamese tones kept).

lang "vi" (default): the Vietnamese normalizer. "en": the English normalizer. "mixed": words are
kept as written (lower case, punctuation dropped) and only tokens with digits or symbols go
through the Vietnamese normalizer, so English words in Vietnamese sentences are not spelled out.
The same normalization is applied to the reference and to the ASR output.

Pair languages "zh", "ko", "ja", "th" (main-language and mixed sets of the zh-en, ko-en, ja-en pairs):
the text goes through the pair front-end's own normalizers (sentence split, script tagging,
numbers read in the main language, Latin words through the English normalizer), punctuation
dropped. Chinese is converted to Simplified and Japanese katakana to hiragana. CER counts
characters with spaces removed (Han characters, Hangul syllables, kana and kanji, Latin letters),
so the spacing of Korean words and of English terms ("Wi-Fi" / "WiFi") is not an error. WER counts
words: for zh and ja (written without spaces) each Han character or kana is one word and each
Latin word one word (a mixed error rate); for ko the space-separated words (어절), so Korean WER
also counts spacing differences. Japanese CER is orthographic: Whisper writing a word in kanji
where the reference has kana (or the other way round) counts as an error. Thai CER counts Thai
characters (spaces removed); Thai WER counts the words of the front-end's word segmentation.

Latin-script pair languages (LATIN_PAIR_LANGS: es id pt de it tr pl fi ms tl sw nl sv no) go through their pair front-end the same
way (numbers read in the main language, English words through the English normalizer, accents
kept, lower case); CER counts characters with the spaces between words, WER counts words. Hindi
("hi") is scored the same way (Devanagari words separated by spaces, numbers read in Hindi), and
Russian ("ru"; ё counted as е, since Whisper and writers often omit it; the one-letter
prepositions joined by the normalizer, в-доме, count as one word on both sides), and so is Arabic ("ar": words without vowel marks or tatweel, numbers read in Arabic)."""

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


LATIN_PAIR_LANGS = ("es", "id", "pt", "de", "it", "tr", "pl", "fi", "ms", "tl", "sw", "nl", "sv", "no")
SPACED_PAIR_LANGS = (*LATIN_PAIR_LANGS, "hi", "ru", "ar", "el")  # words separated by spaces: CER keeps them
PAIR_LANGS = ("zh", "ko", "ja", "th", *SPACED_PAIR_LANGS)
WHISPER_LANGUAGE = {"vi": "vi", "en": "en", "mixed": "vi", "zh": "zh", "ko": "ko", "ja": "ja",
                    "th": "th",
                    **{code: code for code in SPACED_PAIR_LANGS}}
# French (fr-en): a Latin-script pair (liaison consonants written by the normalizer, z'amis, count
# on both sides alike).
LATIN_PAIR_LANGS = (*LATIN_PAIR_LANGS, "fr")
SPACED_PAIR_LANGS = (*SPACED_PAIR_LANGS, "fr")
PAIR_LANGS = (*PAIR_LANGS, "fr")
WHISPER_LANGUAGE["fr"] = "fr"


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or ch in "々〆ヶ"


def _pair_words(text: str, lang: str) -> list[str]:
    from vtts.frontend.lang import runs, split_sentences_raw
    from vtts.frontend.languages import LANGUAGES

    if lang == "zh":
        from vtts.data.zh_corpus import to_simplified

        text = to_simplified(text)
    words: list[str] = []
    for sentence in split_sentences_raw(unicodedata.normalize("NFC", text), lang):
        for run, code in runs(sentence, lang):
            words += [w for w in LANGUAGES[code].normalize(run).split() if w not in PUNCTUATION]
    if lang == "ru":
        words = [w.replace("ё", "е") for w in words]
    if lang == "ja":
        from vtts.frontend.ja.kana import to_hiragana

        words = [to_hiragana(w) for w in words]
    if lang == "ar":  # ASR output rarely has vowel marks: compare the letters
        from vtts.frontend.ar.g2p_ar import is_arabic_word, strip_marks

        return [strip_marks(w) if is_arabic_word(w) else w for w in words]
    if lang == "ko" or lang in SPACED_PAIR_LANGS:
        return words
    if lang == "th":  # Thai runs cut into words by the front-end's word segmentation
        from vtts.frontend.th.g2p_th import segment
        from vtts.frontend.th.normalize_th import is_thai_word

        return [p for w in words for p in (segment(w.replace("ๆ", "")) if is_thai_word(w) else [w])]
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
    return p.replace(" ", "") if lang in PAIR_LANGS and lang not in SPACED_PAIR_LANGS else p


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


_SCRIPT = {"ko": lambda ch: "가" <= ch <= "힣",
           "zh": lambda ch: "一" <= ch <= "鿿",
           "ja": _is_cjk,
           "th": lambda ch: "฀" <= ch <= "๿"}


def _script_edits(ref: str, hyp: str, own) -> tuple[int, int]:
    """Edits charged to the reference's main-script characters: a substitution or deletion of
    such a character, and an insertion between two of them. Reference characters of other
    scripts (English words) and whatever the ASR writes in their place are not counted."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    errs, i, j = 0, n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            errs += own(ref[i - 1]) and ref[i - 1] != hyp[j - 1]
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            errs += own(ref[i - 1])
            i -= 1
        else:  # insertion between ref[i - 1] and ref[i]
            errs += 0 < i < n and own(ref[i - 1]) and own(ref[i])
            j -= 1
    return errs, sum(map(own, ref))


def main_script_cer(pairs: list[tuple[str, str]], lang: str) -> float:
    """Corpus CER over the main-language characters only (Hangul for ko, Han for zh, kana and
    kanji for ja, Thai for th), for mixed sets: the ASR writes English words in the main script
    (Google Drive -> 구글 드라이브), which plain CER counts as errors even for a perfect reading.
    Each reference character of the main script counts once; English words are skipped."""
    own = _SCRIPT[lang]
    errs = total = 0
    for ref, hyp in pairs:
        e, t = _script_edits(_chars(ref, lang), _chars(hyp, lang), own)
        errs += e
        total += t
    return errs / max(total, 1)


def _ja_kana(text: str) -> str:
    """Japanese text as its reading in hiragana (the ja front-end's tables: kanji, kana, numbers
    read in Japanese), Latin words kept; spaces removed."""
    from vtts.frontend.ja.g2p_ja import ja_reading
    from vtts.frontend.ja.kana import to_hiragana
    from vtts.frontend.lang import runs, split_sentences_raw
    from vtts.frontend.languages import LANGUAGES

    out = []
    for sentence in split_sentences_raw(unicodedata.normalize("NFC", text), "ja"):
        for run, code in runs(sentence, "ja"):
            for w in LANGUAGES[code].normalize(run).split():
                if w in PUNCTUATION:
                    continue
                out.append(to_hiragana(ja_reading(w)) if any(_is_cjk(ch) for ch in w) else w)
    return "".join(out)


def ja_reading_cer(pairs: list[tuple[str, str]], main_only: bool = False) -> float:
    """Japanese CER on readings: reference and transcript are both converted to hiragana by the
    ja front-end, so spelling choices of the ASR (kanji or kana, 十五 or 15, 沸く or 湧く) are not
    errors, only a different reading is. Counted in kana (about two per kanji), so it is not
    comparable with the orthographic CER. main_only: count only the errors on the reference's kana
    (English words and what the ASR writes for them skipped, as in main_script_cer)."""
    errs = total = 0
    for ref, hyp in pairs:
        r, h = _ja_kana(ref), _ja_kana(hyp)
        if main_only:
            e, t = _script_edits(r, h, _is_cjk)
        else:
            e, t = _edits(r, h), len(r)
        errs += e
        total += t
    return errs / max(total, 1)
