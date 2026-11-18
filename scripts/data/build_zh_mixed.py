"""Mandarin sentences with one English term each (code-switching) for speech synthesis.

Usage: uv run python scripts/data/build_zh_mixed.py --out data/zh/mixed.jsonl [--hours 5]
Templates are scripts/data/bilingual/templates_zh.txt ({T} = term), terms are the shared
scripts/data/bilingual/terms_en.txt. Rows have lang "zh" (token set zh-en reads both).
Hours are estimated at 4.5 Han characters/s plus 2.6 English words/s.
"""

import argparse
import json
import random
from pathlib import Path

from vtts.data.zh_corpus import han_count

HERE = Path(__file__).parent / "bilingual"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=5)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    terms = [t for t in (HERE / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (HERE / "templates_zh.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    combos = [(tp.replace("{T}", tm), tm) for tp in temps for tm in terms]
    random.Random(a.seed).shuffle(combos)
    budget, total, rows = a.hours * 3600, 0.0, []
    for s, tm in combos:
        if total >= budget:
            break
        rows.append({"id": f"zm{len(rows):06d}", "text": s, "lang": "zh"})
        total += han_count(s) / 4.5 + len(tm.split()) / 2.6
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} sentences, about {total / 3600:.1f} h")


if __name__ == "__main__":
    main()
