"""Teacher training lists from one or more synthesis runs.

A row is uid|text|dur|lang[|audio]. The optional fifth column is the audio file, relative to the
teacher's --wavs directory (or absolute), so one list can draw on several synthesis runs
(teacher/data.py); without it the audio is WAVS/<uid>.wav or .flac as before.

A source is a sentence list (jsonl with id, text, lang) plus a synthesis run (SYNTH/manifest.jsonl
and SYNTH/audio/<id>.flac), or, for a run whose manifest is not at hand, an existing list made by
scripts/data/synth_to_csv.py (csv=, uid|text|dur|lang) plus the run's audio. Options per source:
only (keep rows of one lang), lang (write this lang instead of the sentence's), hours (keep a
seeded random subset of about this many hours). Rows are left out when the manifest status is not
ok, the audio file is missing, the text holds "|", or (pair languages) the text has characters
the pair front-end cannot read, so the ids always match the audio.
"""

from __future__ import annotations

import importlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

LIST_FIELDS = ("sentences", "csv", "synth", "only", "lang", "hours")


# Pair language -> (module, function) listing the characters of a text its front-end cannot read.
UNREADABLE = {
    "zh": ("vtts.frontend.zh.g2p_zh", "unknown_han"),
    "ko": ("vtts.frontend.ko.g2p_ko", "unreadable_ko"),
    "ja": ("vtts.frontend.ja.g2p_ja", "unreadable_ja"),
    "es": ("vtts.frontend.es.g2p_es", "unreadable_es"),
    "id": ("vtts.frontend.id.g2p_id", "unreadable_id"),
    "pt": ("vtts.frontend.pt.g2p_pt", "unreadable_pt"),
    "hi": ("vtts.frontend.hi.g2p_hi", "unreadable_hi"),
    "th": ("vtts.frontend.th.g2p_th", "unreadable_th"),
    "de": ("vtts.frontend.de.g2p_de", "unreadable_de"),
    "it": ("vtts.frontend.it.g2p_it", "unreadable_it"),
    "tr": ("vtts.frontend.tr.g2p_tr", "unreadable_tr"),
    "ru": ("vtts.frontend.ru.g2p_ru", "unreadable_ru"),
    "pl": ("vtts.frontend.pl.g2p_pl", "unreadable_pl"),
    "ar": ("vtts.frontend.ar.g2p_ar", "unreadable_ar"),
}
UNREADABLE["fr"] = ("vtts.frontend.fr.g2p_fr", "unreadable_fr")
UNREADABLE["fi"] = ("vtts.frontend.fi.g2p_fi", "unreadable_fi")
UNREADABLE["el"] = ("vtts.frontend.el.g2p_el", "unreadable_el")
UNREADABLE["ms"] = ("vtts.frontend.ms.g2p_ms", "unreadable_ms")
UNREADABLE["tl"] = ("vtts.frontend.tl.g2p_tl", "unreadable_tl")
UNREADABLE["sw"] = ("vtts.frontend.sw.g2p_sw", "unreadable_sw")
UNREADABLE["nl"] = ("vtts.frontend.nl.g2p_nl", "unreadable_nl")
UNREADABLE["sv"] = ("vtts.frontend.sv.g2p_sv", "unreadable_sv")
UNREADABLE["no"] = ("vtts.frontend.no.g2p_no", "unreadable_no")


def unreadable(text: str, lang: str) -> bool:
    """True when the pair front-end would skip characters of the text (no reading)."""
    if lang not in UNREADABLE:
        return False
    module, fn = UNREADABLE[lang]
    return bool(getattr(importlib.import_module(module), fn)(text))


@dataclass(frozen=True)
class Source:
    sentences: Path | None
    synth: Path
    only: str | None = None
    lang: str | None = None
    hours: float | None = None
    csv: Path | None = None


def parse_source(spec: str) -> Source:
    """"sentences=PATH|csv=PATH,synth=DIR[,only=en][,lang=zh][,hours=30]"."""
    kv: dict[str, str] = {}
    for part in spec.split(","):
        key, sep, val = part.partition("=")
        if not sep or key.strip() not in LIST_FIELDS:
            raise ValueError(f"bad source field {part!r} (fields: {', '.join(LIST_FIELDS)})")
        kv[key.strip()] = val.strip()
    if ("sentences" in kv) == ("csv" in kv) or "synth" not in kv:
        raise ValueError(f"source needs synth= and one of sentences= or csv=: {spec!r}")
    return Source(Path(kv["sentences"]) if "sentences" in kv else None, Path(kv["synth"]),
                  kv.get("only"), kv.get("lang"), float(kv["hours"]) if "hours" in kv else None,
                  Path(kv["csv"]) if "csv" in kv else None)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _audio_ref(path: Path, root: Path) -> str:
    p, r = path.resolve(), root.resolve()
    return p.relative_to(r).as_posix() if p.is_relative_to(r) else str(p)


def _texts_and_durations(src: Source) -> tuple[dict[str, tuple[str, str]], dict[str, float]]:
    text: dict[str, tuple[str, str]] = {}
    dur: dict[str, float] = {}
    if src.csv is not None:
        for line in src.csv.read_text(encoding="utf-8").splitlines():
            if line.strip():
                uid, t, d, lang, *_ = line.split("|")
                if src.only is None or lang == src.only:
                    text[uid], dur[uid] = (t, lang), float(d)
        return text, dur
    text = {r["id"]: (r["text"], r["lang"]) for r in _jsonl(src.sentences)
            if src.only is None or r["lang"] == src.only}
    for r in _jsonl(src.synth / "manifest.jsonl"):
        if r["status"] == "ok" and r["id"] in text:
            dur[r["id"]] = r["dur"]
    return text, dur


def source_rows(src: Source, root: Path, seed: int = 0) -> list[tuple[str, str, float, str, str]]:
    """(uid, text, dur, lang, audio) of one source, sorted by uid."""
    text, dur = _texts_and_durations(src)
    rows = []
    for uid in sorted(dur):
        t, lang = text[uid]
        lang = src.lang or lang
        audio = src.synth / "audio" / f"{uid}.flac"
        if "|" in t or not audio.exists() or unreadable(t, lang):
            continue
        rows.append((uid, t, dur[uid], lang, _audio_ref(audio, root)))
    if src.hours is not None:
        order = rows[:]
        random.Random(seed).shuffle(order)
        keep, total = set(), 0.0
        for r in order:
            if total + r[2] > src.hours * 3600:
                break
            keep.add(r[0])
            total += r[2]
        rows = [r for r in rows if r[0] in keep]
    return rows


def build_rows(sources: list[Source], root: Path, seed: int = 0) -> list[str]:
    """train.csv lines for all sources; uids must be unique across sources (spectrogram cache)."""
    out, seen = [], set()
    for src in sources:
        for uid, text, dur, lang, audio in source_rows(src, root, seed):
            if uid in seen:
                raise ValueError(f"duplicate id {uid} in {src.csv or src.sentences}")
            seen.add(uid)
            out.append(f"{uid}|{text}|{dur:.3f}|{lang}|{audio}")
    return out


def row_hours(rows: list[str]) -> dict[str, float]:
    """Hours per lang column."""
    hours: dict[str, float] = {}
    for r in rows:
        _, _, dur, lang, *_ = r.split("|")
        hours[lang] = hours.get(lang, 0.0) + float(dur) / 3600
    return hours
