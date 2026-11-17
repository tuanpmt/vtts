"""Character/word error rates on normalized text (Vietnamese tones kept).

lang "vi" (default): the Vietnamese normalizer. "en": the English normalizer. "mixed": words are
kept as written (lower case, punctuation dropped) and only tokens with digits or symbols go
through the Vietnamese normalizer, so English words in Vietnamese sentences are not spelled out.
The same normalization is applied to the reference and to the ASR output."""

from __future__ import annotations

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


def prep_for_cer(text: str, lang: str = "vi") -> str:
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


def cer(ref: str, hyp: str, lang: str = "vi") -> float:
    r, h = prep_for_cer(ref, lang), prep_for_cer(hyp, lang)
    return _edits(r, h) / max(len(r), 1)


def wer(ref: str, hyp: str, lang: str = "vi") -> float:
    r, h = prep_for_cer(ref, lang).split(), prep_for_cer(hyp, lang).split()
    return _edits(r, h) / max(len(r), 1)


def corpus_cer(pairs: list[tuple[str, str]], lang: str = "vi") -> float:
    errs = total = 0
    for ref, hyp in pairs:
        r, h = prep_for_cer(ref, lang), prep_for_cer(hyp, lang)
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
