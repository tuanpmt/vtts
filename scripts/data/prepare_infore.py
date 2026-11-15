"""Download (optional) and prepare InfoRe1 into 22.05 kHz wavs + metadata.csv.

Usage: uv run python scripts/prepare_infore.py --raw data/infore1/raw --out data/infore1/prepared [--download]
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from vtts.data.infore import prepare_infore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/infore1/raw"))
    ap.add_argument("--out", type=Path, default=Path("data/infore1/prepared"))
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    if args.download:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id="doof-ferb/infore1_25hours", repo_type="dataset",
                          local_dir=args.raw, max_workers=8)
    report = prepare_infore(args.raw, args.out)
    (args.out / "prepare_report.json").write_text(json.dumps(asdict(report), indent=1))
    print(f"in={report.n_in} out={report.n_out} hours={report.hours:.2f} skipped={len(report.skipped)}")


if __name__ == "__main__":
    main()
