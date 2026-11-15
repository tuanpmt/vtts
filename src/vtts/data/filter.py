"""Quality filters over scored dataset rows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from vtts.eval.cer import cer
from vtts.frontend.g2p import g2p
from vtts.frontend.normalize import normalize, spelled_words


@dataclass
class Row:
    id: str
    text: str
    duration_s: float
    asr: str | None = None
    dnsmos_ovrl: float | None = None


def _text_ok(text: str) -> bool:
    try:
        return bool(g2p(normalize(text)))
    except ValueError:
        return False


def apply_filters(rows: list[Row], cer_max: float = 0.10, dnsmos_min: float = 3.0,
                  dur_min: float = 1.0, dur_max: float = 15.0) -> tuple[list[Row], dict[str, int]]:
    kept: list[Row] = []
    reasons: Counter[str] = Counter()
    for r in rows:
        if not _text_ok(r.text):
            reasons["invalid_text"] += 1
        elif spelled_words(r.text):
            # spelled letter by letter: the label no longer matches what the speaker said
            reasons["spelled_word"] += 1
        elif r.duration_s < dur_min:
            reasons["too_short"] += 1
        elif r.duration_s > dur_max:
            reasons["too_long"] += 1
        elif r.asr is None or r.dnsmos_ovrl is None:
            reasons["unscored"] += 1
        elif cer(r.text, r.asr) > cer_max:
            reasons["cer"] += 1
        elif r.dnsmos_ovrl < dnsmos_min:
            reasons["dnsmos"] += 1
        else:
            kept.append(r)
    return kept, dict(reasons)
