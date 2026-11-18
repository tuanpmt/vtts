"""One teacher training list for a language pair from several synthesis runs.

Usage (zh-en, nu-10, run from the repo root with the data under data/):
  uv run python scripts/data/pair_train_list.py --out data/zh/pair_nu10 --root data \
    --source sentences=data/zh/sentences.jsonl,synth=data/zh/synth_nu10 \
    --source sentences=data/zh/mixed.jsonl,synth=data/zh/synth_nu10_mixed \
    --source sentences=data/bilingual/sentences.jsonl,synth=data/bilingual/synth_nu10,only=en,hours=35
  uv run python scripts/teacher/train_teacher.py --data data/zh/pair_nu10 --wavs data ...

Source fields: sentences= (jsonl), synth= (run dir with manifest.jsonl and audio/), only=LANG (keep
rows of one lang), lang=LANG (write this lang), hours=H (seeded random subset of about H hours,
e.g. hours=30 on the main-language source for the data-budget experiment). Rows are
uid|text|dur|lang|audio with audio relative to --root, which must be the --wavs directory given
to train_teacher.py (paths outside --root are written absolute). See vtts.data.train_list.
"""

import argparse
from pathlib import Path

from vtts.data.train_list import build_rows, parse_source, row_hours


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="writes OUT/train.csv")
    ap.add_argument("--root", type=Path, default=Path("data"),
                    help="audio paths are written relative to this dir (= train_teacher.py --wavs)")
    ap.add_argument("--source", action="append", required=True, type=parse_source)
    ap.add_argument("--seed", type=int, default=0, help="seed of the hours= subsets")
    a = ap.parse_args()
    rows = build_rows(a.source, a.root, a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "train.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    hours = row_hours(rows)
    print(f"{len(rows)} rows, {sum(hours.values()):.1f} h:",
          ", ".join(f"{k} {v:.1f} h" for k, v in sorted(hours.items())))


if __name__ == "__main__":
    main()
