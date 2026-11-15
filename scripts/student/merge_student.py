"""Build an init checkpoint: duration + acoustic from a front-stage checkpoint, decoder from another.

Usage: uv run python scripts/student/merge_student.py --front F.pt --decoder D.pt --out init.pt
"""

import argparse
from pathlib import Path

import torch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--front", type=Path, required=True)
    ap.add_argument("--decoder", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    f = torch.load(a.front, map_location="cpu", weights_only=False)
    d = torch.load(a.decoder, map_location="cpu", weights_only=False)
    sd = {k: v for k, v in f["student"].items() if not k.startswith("decoder.")}
    sd.update({k: v for k, v in d["student"].items() if k.startswith("decoder.")})
    torch.save({"student": sd, "config": f["config"], "step": 0}, a.out)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
