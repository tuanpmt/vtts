"""Code-switching sentences: main-language templates with one English term each.

Templates are scripts/data/bilingual/templates_<lang>.txt ({T} = term), terms are the shared
scripts/data/bilingual/terms_en.txt. Rows have the pair language as lang ("zh", "ko", "ja"), so
the pair token set reads both the main language and the English term. Durations are estimated
from the main-language part at the corpus rates (zh 4.5 Han characters/s, ko 5.5 syllables/s,
ja 7.5 morae/s) plus 2.6 English words/s.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "scripts" / "data" / "bilingual"
ID_PREFIX = {"zh": "zm", "ko": "km", "ja": "jm"}
EN_RATE = 2.6  # English words per second


def _seconds_fn(lang: str) -> Callable[[str], float]:
    if lang == "zh":
        from vtts.data.zh_corpus import zh_seconds

        return zh_seconds
    if lang == "ko":
        from vtts.data.ko_corpus import ko_seconds

        return ko_seconds
    if lang == "ja":
        from vtts.data.ja_corpus import ja_seconds

        return ja_seconds
    raise ValueError(f"no mixed templates for language {lang!r}")


def _lines(path: Path) -> list[str]:
    return [t for t in path.read_text(encoding="utf-8").splitlines() if t.strip()]


def load_templates(lang: str, template_dir: Path = TEMPLATE_DIR) -> list[str]:
    return _lines(template_dir / f"templates_{lang}.txt")


def load_terms(template_dir: Path = TEMPLATE_DIR) -> list[str]:
    return _lines(template_dir / "terms_en.txt")


def mixed_rows(lang: str, hours: float, seed: int = 0,
               template_dir: Path = TEMPLATE_DIR) -> tuple[list[dict], float]:
    """Shuffled template x term sentences up to about `hours`; returns (rows, estimated seconds)."""
    seconds = _seconds_fn(lang)
    prefix = ID_PREFIX[lang]
    combos = [(tp, tm) for tp in load_templates(lang, template_dir) for tm in load_terms(template_dir)]
    random.Random(seed).shuffle(combos)
    budget, total, rows = hours * 3600, 0.0, []
    for tp, tm in combos:
        if total >= budget:
            break
        rows.append({"id": f"{prefix}{len(rows):06d}", "text": tp.replace("{T}", tm), "lang": lang})
        total += seconds(tp.replace("{T}", "")) + len(tm.split()) / EN_RATE
    return rows, total
