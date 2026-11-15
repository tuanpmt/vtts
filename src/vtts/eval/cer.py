"""Character/word error rates on normalized Vietnamese text (tones kept)."""

from __future__ import annotations

from collections.abc import Sequence

from vtts.frontend.normalize import normalize
from vtts.frontend.phoneme_set import PUNCTUATION


def prep_for_cer(text: str) -> str:
    return " ".join(w for w in normalize(text).split() if w not in PUNCTUATION)


def _edits(ref: Sequence, hyp: Sequence) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    r, h = prep_for_cer(ref), prep_for_cer(hyp)
    return _edits(r, h) / max(len(r), 1)


def wer(ref: str, hyp: str) -> float:
    r, h = prep_for_cer(ref).split(), prep_for_cer(hyp).split()
    return _edits(r, h) / max(len(r), 1)


def corpus_cer(pairs: list[tuple[str, str]]) -> float:
    errs = total = 0
    for ref, hyp in pairs:
        r, h = prep_for_cer(ref), prep_for_cer(hyp)
        errs += _edits(r, h)
        total += len(r)
    return errs / max(total, 1)


def corpus_wer(pairs: list[tuple[str, str]]) -> float:
    errs = total = 0
    for ref, hyp in pairs:
        r, h = prep_for_cer(ref).split(), prep_for_cer(hyp).split()
        errs += _edits(r, h)
        total += len(r)
    return errs / max(total, 1)
