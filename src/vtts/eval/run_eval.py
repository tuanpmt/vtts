"""Score a directory of rendered clips against a sentence set."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from .cer import cer, corpus_cer, corpus_wer, wer
from .whistle import whistle_score


@dataclass
class ClipScore:
    id: str
    group: str
    ref: str
    hyp: str
    cer: float
    wer: float
    whistle: float
    utmos: float | None = None
    dnsmos_ovrl: float | None = None


@dataclass
class EvalReport:
    system: str
    set_name: str
    corpus_cer: float
    corpus_wer: float
    mean_whistle: float
    mean_utmos: float | None
    mean_dnsmos: float | None
    clips: list[ClipScore] = field(default_factory=list)


def _mean(vals: list[float | None]) -> float | None:
    vals = [v for v in vals if v is not None]
    return float(np.mean(vals)) if vals else None


def evaluate(system: str, set_name: str, audio_dir: Path, sentences: list[dict],
             asr: Callable[[list[Path]], list[str]], mos: bool = True, lang: str = "vi") -> EvalReport:
    paths = [Path(audio_dir) / f"{s['id']}.wav" for s in sentences]
    missing = [s["id"] for s, p in zip(sentences, paths) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing audio for ids: {missing}")
    hyps = asr(paths)
    clips = []
    for s, p, hyp in zip(sentences, paths, hyps):
        x, sr = sf.read(p, dtype="float32", always_2d=True)
        x = x.mean(axis=1)
        clip = ClipScore(s["id"], s.get("group", ""), s["text"], hyp, cer(s["text"], hyp, lang),
                         wer(s["text"], hyp, lang), whistle_score(x, sr))
        if mos:
            from .mos import dnsmos, utmos

            clip.utmos = utmos(x, sr)
            clip.dnsmos_ovrl = dnsmos(x, sr)["ovrl"]
        clips.append(clip)
    pairs = [(c.ref, c.hyp) for c in clips]
    return EvalReport(system, set_name, corpus_cer(pairs, lang), corpus_wer(pairs, lang),
                      float(np.mean([c.whistle for c in clips])),
                      _mean([c.utmos for c in clips]), _mean([c.dnsmos_ovrl for c in clips]), clips)
