"""Render a sentence set through the C runtime (host build) for evaluation.

Usage: uv run python scripts/student/render_student_c.py --model model.vtts --set eval/sets/ood.jsonl --out DIR
       [--lang vi|en|mixed]   (token set v2 for bilingual models; mixed is read in vi mode)
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
from vtts.frontend.text import split_sentences, text_to_ids

CLI = Path(__file__).resolve().parents[2] / "runtime" / "build" / "vtts_cli"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--length-scale", type=float, default=1.0)
    ap.add_argument("--expr", type=float, default=None, help="expressiveness (prosody models only)")
    ap.add_argument("--lang", choices=["vi", "en", "mixed"], default=None,
                    help="token set v2 front-end (bilingual models)")
    a = ap.parse_args()
    subprocess.run(["make", "-s", "-C", str(CLI.parents[1]), "build/vtts_cli"], check=True)
    rows = [json.loads(x) for x in a.set.read_text(encoding="utf-8").splitlines() if x]
    a.out.mkdir(parents=True, exist_ok=True)
    lines, owners = [], []
    for r in rows:
        if a.lang:
            chunks = text_to_ids(r["text"], "vi" if a.lang == "mixed" else a.lang)
        else:
            chunks = [encode(g2p(c)) for c in split_sentences(r["text"])]
        for ids in chunks:
            lines.append(" ".join(map(str, ids)))
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
