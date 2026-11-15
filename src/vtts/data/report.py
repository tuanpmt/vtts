"""Dataset statistics: hours, counts, duration histogram, tone distribution."""

from __future__ import annotations

from collections import Counter

from vtts.frontend.g2p import g2p
from vtts.frontend.normalize import normalize

from .filter import Row

TONE_NAMES = {"T1": "ngang", "T2": "huyền", "T3": "sắc", "T4": "hỏi", "T5": "ngã", "T6": "nặng"}


def dataset_report(splits: dict[str, list[Row]]) -> dict:
    rep: dict = {}
    for name, rows in splits.items():
        hist = Counter(int(r.duration_s) for r in rows)
        rep[name] = {"count": len(rows), "hours": sum(r.duration_s for r in rows) / 3600,
                     "duration_hist_s": dict(sorted(hist.items()))}
    tones: Counter[str] = Counter()
    for r in splits.get("train", []):
        tones.update(TONE_NAMES[t] for t in g2p(normalize(r.text)) if t in TONE_NAMES)
    rep["tones"] = {name: tones.get(name, 0) for name in TONE_NAMES.values()}
    return rep
