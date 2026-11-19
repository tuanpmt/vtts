"""Estimate the ESP32-P4 RTF of student presets before training them.

Usage: uv run --extra gpu python scripts/student/estimate_rtf.py [--preset L-vocos-p-bi ...] [--bench]

Two estimates:
- analytic: count_macs() mapped through the P4 `bench` RTF of the v0.4.0 S and M models
  (vtts.student.macs.estimate_p4_rtf);
- --bench: the host C runtime (runtime/bench/bench.c, reference kernels, int8 export of a
  random-weight model, same seed for every preset so durations match) relative to
  M-vocos-p-bi, scaled by the P4 RTF of M (0.26). It checks the analytic line with the real
  layer code (for S it gives 0.16 against the measured 0.17-0.19).
"""

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import torch

from vtts.export.quant import write_model_int8
from vtts.student.config import PRESETS
from vtts.student.macs import P4_CALIBRATION, count_macs, estimate_p4_rtf
from vtts.student.model import Student

ROOT = Path(__file__).resolve().parents[2]
RT = ROOT / "runtime"
REF = "M-vocos-p-bi"


def build_bench(tmp: Path) -> Path:
    exe = tmp / "bench"
    src = [RT / "src" / f for f in ("vtts_model.c", "vtts_synth.c", "vtts_kernels_ref.c")]
    subprocess.run(["cc", "-std=c99", "-O2", f"-I{RT / 'include'}", *map(str, src),
                    str(RT / "bench" / "bench.c"), "-lm", "-o", str(exe)], check=True)
    return exe


def host_rtf(exe: Path, preset: str, tmp: Path, tokens: int, repeats: int) -> float:
    torch.manual_seed(0)
    m = Student(PRESETS[preset]).eval()
    path = tmp / f"{preset}.vtts"
    write_model_int8(m, path, token_set="vi-en")
    mmac = count_macs(m.cfg)["per_second"] / 1e6
    best = float("inf")
    for _ in range(repeats):
        out = subprocess.run([str(exe), str(path), str(tokens), "6", f"{mmac:.1f}"], check=True,
                             capture_output=True, text=True).stdout
        audio, sec = map(float, re.search(r"audio ([0-9.]+)s compute ([0-9.]+)s", out).groups())
        best = min(best, sec / audio)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", action="append", default=None)
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--tokens", type=int, default=3000)
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()
    presets = a.preset or ["S-vocos-p-bi", REF, "L-vocos-p-bi"]
    print(f"calibration (MMAC/s, P4 RTF): {P4_CALIBRATION}")
    host = {}
    if a.bench:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            exe = build_bench(tmp)
            for p in dict.fromkeys([REF, *presets]):
                host[p] = host_rtf(exe, p, tmp, a.tokens, a.repeats)
    p4_ref = P4_CALIBRATION[1][1]
    print("| preset | params | MMAC/s | P4 RTF (analytic) | host RTF | P4 RTF (host ratio x M) |")
    print("|---|---:|---:|---:|---:|---:|")
    for p in presets:
        cfg = PRESETS[p]
        n = sum(x.numel() for x in Student(cfg).parameters())
        mm = count_macs(cfg)["per_second"] / 1e6
        hb = f"{host[p]:.5f} | {p4_ref * host[p] / host[REF]:.3f}" if host else "- | -"
        print(f"| {p} | {n / 1e6:.2f}M | {mm:.1f} | {estimate_p4_rtf(cfg):.3f} | {hb} |")


if __name__ == "__main__":
    main()
