"""Render a sentence set through the C runtime (host build) for evaluation.

Usage: uv run python scripts/student/render_student_c.py --model model.vtts --set eval/sets/ood.jsonl --out DIR
Multi-chunk texts are rendered chunk by chunk and joined with 150 ms of silence.
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from vtts.frontend.g2p import encode, g2p
from vtts.frontend.text import split_sentences

CLI = Path(__file__).resolve().parents[2] / "runtime" / "build" / "vtts_cli"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--length-scale", type=float, default=1.0)
    ap.add_argument("--expr", type=float, default=None, help="expressiveness (prosody models only)")
    a = ap.parse_args()
    subprocess.run(["make", "-s", "-C", str(CLI.parents[1]), "build/vtts_cli"], check=True)
    rows = [json.loads(x) for x in a.set.read_text(encoding="utf-8").splitlines() if x]
    a.out.mkdir(parents=True, exist_ok=True)
    lines, owners = [], []
    for r in rows:
        for chunk in split_sentences(r["text"]):
            lines.append(" ".join(map(str, encode(g2p(chunk)))))
            owners.append(r["id"])
    with tempfile.TemporaryDirectory() as tmp:
        extra = [str(a.length_scale)] + ([str(a.expr)] if a.expr is not None else [])
        subprocess.run([str(CLI), str(a.model), f"{tmp}/c", *extra], input="\n".join(lines) + "\n",
                       text=True, check=True)
        parts: dict[str, list[np.ndarray]] = {}
        for k, owner in enumerate(owners):
            x, sr = sf.read(f"{tmp}/c{k}.wav", dtype="float32")
            parts.setdefault(owner, []).append(x)
    gap = np.zeros(int(0.15 * 22050), np.float32)
    for owner, chunks in parts.items():
        audio = np.concatenate([c if i == 0 else np.concatenate([gap, c]) for i, c in enumerate(chunks)])
        sf.write(a.out / f"{owner}.wav", audio, 22050)
    print(f"rendered {len(parts)} clips to {a.out}")


if __name__ == "__main__":
    main()
