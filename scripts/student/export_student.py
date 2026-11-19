"""Assemble a student from stage checkpoints and export it (fp32 or int8).

Usage: uv run python scripts/student/export_student.py --front F.pt --dec D.pt [--joint J.pt] \
   --out model.vtts [--int8] [--token-set vi-en|zh-en|ko-en|ja-en|es-en|id-en|pt-en|th-en|hi-en|fr-en|de-en|it-en|tr-en|ru-en|pl-en|ar-en|fi-en|el-en|ms-en|tl-en|sw-en|nl-en|sv-en|no-en|da-en|lo-en|km-en|my-en|v1]
The decoder comes from --joint when given (it also refines the acoustic model), else --dec.
The token set is recorded in the file header (dim token_set, docs/model-format.md): --token-set,
else a "token_set" entry of the front checkpoint, else the set the vocab names (65 -> v1,
107 -> vi-en, 171 -> zh-en, 153 -> ko-en, 144 -> ja-en, 138 -> es-en, 141 -> id-en,
150 -> pt-en, 162 -> th-en, 157 -> hi-en, 143 -> fr-en, 167 -> de-en, 142 -> it-en, 146 -> tr-en, 154 -> ru-en, 151 -> pl-en, 149 -> ar-en, 145 -> ms-en, 147 -> sw-en, 159 -> nl-en, 155 -> sv-en, 156 -> no-en); fi-en and it-en (142), el-en and tl-en (139) (142) and other vocab
sizes need
--token-set.
"""

import argparse
from pathlib import Path

import torch

from vtts.export.format import TOKEN_SET_CODES, resolve_token_set, write_model
from vtts.export.quant import write_model_int8
from vtts.student.config import StudentConfig
from vtts.student.model import Student


def checkpoint_token_set(front: Path) -> str | None:
    """A token set recorded by training (top-level "token_set" or in "config"), if any."""
    f = torch.load(front, map_location="cpu", weights_only=False)
    return f.get("token_set") or f.get("config", {}).get("token_set")


def assemble(front: Path, dec: Path, joint: Path | None) -> Student:
    f = torch.load(front, map_location="cpu", weights_only=False)
    cfg = StudentConfig(**{k: tuple(v) if isinstance(v, list) else v for k, v in f["config"].items()
                           if k != "token_set"})
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
    ap.add_argument("--token-set", choices=sorted(TOKEN_SET_CODES), default=None,
                    help="token set to record (default: from the checkpoint or the vocab)")
    a = ap.parse_args()
    m = assemble(a.front, a.dec, a.joint)
    ts = resolve_token_set(m.cfg.vocab, a.token_set or checkpoint_token_set(a.front))
    if ts is None:
        ap.error(f"vocab {m.cfg.vocab} names no token set; pass --token-set")
    (write_model_int8 if a.int8 else write_model)(m, a.out, token_set=ts)
    print(f"wrote {a.out} ({a.out.stat().st_size} bytes, token set {ts})")


if __name__ == "__main__":
    main()
