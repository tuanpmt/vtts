"""Checks for synthesized training audio: ASR transcript against the source text.

A clip is kept when the ASR character error rate is below MAX_CER and its speaking rate is
plausible. The CER limit is loose because Whisper itself confuses homophones and rare names
(about 0.05-0.15 on clean synthetic Mandarin); it catches misread, truncated or garbled clips.
"""

from __future__ import annotations

import re

MAX_CER = 0.35
MIN_RATE, MAX_RATE = 1.5, 9.0  # units (Han characters) per second

_HAN = re.compile(r"[一-鿿]")


def _han(text: str) -> list[str]:
    from vtts.data.zh_corpus import to_simplified

    return _HAN.findall(to_simplified(text))


def _edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def zh_cer(ref: str, hyp: str) -> float:
    """Character error rate over Han characters only (punctuation, Latin and digits ignored)."""
    r, h = _han(ref), _han(hyp)
    return _edits(r, h) / max(1, len(r))


def accept(cer: float, dur: float, n_units: int) -> bool:
    rate = n_units / max(dur, 1e-6)
    return cer <= MAX_CER and MIN_RATE <= rate <= MAX_RATE
