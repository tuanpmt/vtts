"""Assemble a student from stage checkpoints and export it (fp32 or int8).

Usage: uv run python scripts/student/export_student.py --front F.pt --dec D.pt [--joint J.pt] \
   --out model.vtts [--int8]
The decoder comes from --joint when given (it also refines the acoustic model), else --dec.
"""

import argparse
from pathlib import Path

import torch

from vtts.export.format import write_model
from vtts.export.quant import write_model_int8
from vtts.student.config import StudentConfig
from vtts.student.model import Student


def assemble(front: Path, dec: Path, joint: Path | None) -> Student:
    f = torch.load(front, map_location="cpu", weights_only=False)
    cfg = StudentConfig(**{k: tuple(v) if isinstance(v, list) else v for k, v in f["config"].items()})
    m = Student(cfg)
    sd = {k: v for k, v in f["student"].items() if not k.startswith("decoder.")}
    last = torch.load(joint or dec, map_location="cpu", weights_only=False)["student"]
    sd.update({k: v for k, v in last.items() if k.startswith("decoder.")})
    if joint:
        sd.update({k: v for k, v in last.items() if k.startswith("acoustic.")})
    m.load_state_dict(sd)
    return m.eval()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--front", type=Path, required=True)
    ap.add_argument("--dec", type=Path, required=True)
    ap.add_argument("--joint", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--int8", action="store_true")
    a = ap.parse_args()
    m = assemble(a.front, a.dec, a.joint)
    (write_model_int8 if a.int8 else write_model)(m, a.out)
    print(f"wrote {a.out} ({a.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
