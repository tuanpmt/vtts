"""Main-language sentences with one English term each (code-switching) for speech synthesis.

Usage: uv run python scripts/data/build_mixed.py --lang zh --out data/zh/mixed.jsonl [--hours 5]
       (--lang ko -> data/ko/mixed.jsonl, ids km...; --lang ja -> data/ja/mixed.jsonl, ids jm...;
       es em..., id im..., pt pm..., th tm..., hi hm...)
Templates are scripts/data/bilingual/templates_<lang>.txt ({T} = term), terms are the shared
scripts/data/bilingual/terms_en.txt; see vtts.data.mixed. Rows have lang = the pair language,
so the pair token set (zh-en, ko-en, ja-en) reads both. With the same seed and hours, --lang zh
gives the same rows as the former build_zh_mixed.py.
"""

import argparse
import json
from pathlib import Path

from vtts.data.mixed import ID_PREFIX, mixed_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=sorted(ID_PREFIX))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=5)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rows, total = mixed_rows(a.lang, a.hours, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} sentences, about {total / 3600:.1f} h")


if __name__ == "__main__":
    main()
