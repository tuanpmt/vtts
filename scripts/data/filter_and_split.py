"""Filter scored InfoRe1 rows, split them, write CSVs + report.json.

Usage: uv run python scripts/filter_and_split.py --prepared data/infore1/prepared \
       --scores data/infore1/scores.jsonl --out data/infore1/final [--cer-max 0.10]
"""

import argparse
import json
from pathlib import Path

from vtts.data.filter import Row, apply_filters
from vtts.data.report import dataset_report
from vtts.data.splits import make_splits

MIN_TRAIN_HOURS = 18.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--scores", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cer-max", type=float, default=0.10)
    ap.add_argument("--dnsmos-min", type=float, default=3.0)
    args = ap.parse_args()

    scores = {}
    for ln in args.scores.read_text(encoding="utf-8").splitlines():
        s = json.loads(ln)
        scores[s["id"]] = s
    rows = []
    for ln in (args.prepared / "metadata.csv").read_text(encoding="utf-8").splitlines():
        if not ln:
            continue
        uid, text, dur = ln.split("|")
        s = scores.get(uid, {})
        rows.append(Row(uid, text, float(dur), s.get("asr"), s.get("dnsmos_ovrl")))

    kept, reasons = apply_filters(rows, cer_max=args.cer_max, dnsmos_min=args.dnsmos_min)
    splits = make_splits(kept)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, part in splits.items():
        (args.out / f"{name}.csv").write_text(
            "".join(f"{r.id}|{r.text}|{r.duration_s:.3f}\n" for r in part), encoding="utf-8")
    report = {"n_in": len(rows), "n_kept": len(kept), "rejected": reasons,
              "thresholds": {"cer_max": args.cer_max, "dnsmos_min": args.dnsmos_min},
              **dataset_report(splits)}
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps({k: report[k] for k in ("n_in", "n_kept", "rejected")}, ensure_ascii=False))
    print(f"train hours: {report['train']['hours']:.2f}")
    if report["train"]["hours"] < MIN_TRAIN_HOURS:
        print(f"WARNING: train < {MIN_TRAIN_HOURS} h; rerun with a looser --cer-max (e.g. 0.15)")


if __name__ == "__main__":
    main()
