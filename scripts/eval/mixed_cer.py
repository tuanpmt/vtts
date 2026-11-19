"""Fairer CER for a mixed set (main language + English words) from eval_dir.py reports.

Usage: uv run python scripts/eval/mixed_cer.py --lang ko --ref-voice reports/eval/voxcpm2-nu-ko-mixed_ko.json \
           reports/eval/koen-ko-M-mixed_ko.json reports/eval/koen-ko-S-mixed_ko.json
For each report: plain CER against the text, CER over the main-script characters only
(vtts.eval.cer.main_script_cer: English words and what the ASR writes for them are skipped), and,
with --ref-voice (the same set synthesized by the reference voice and scored the same way), the CER
of the student's transcript against the reference voice's transcript, which cancels the ASR's
spelling habits for English words (Google Drive -> 구글 드라이브) as long as both are read alike.
"""

import argparse
import json
from pathlib import Path

from vtts.eval.cer import corpus_cer, main_script_cer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    ap.add_argument("--ref-voice", type=Path, default=None)
    ap.add_argument("reports", type=Path, nargs="+")
    a = ap.parse_args()
    ref_hyp = None
    if a.ref_voice:
        ref_hyp = {c["id"]: c["hyp"] for c in json.loads(a.ref_voice.read_text(encoding="utf-8"))["clips"]}
    print("system | CER (text) | CER (main script) | CER vs reference voice transcript")
    for p in ([a.ref_voice] if a.ref_voice else []) + a.reports:
        rep = json.loads(p.read_text(encoding="utf-8"))
        pairs = [(c["ref"], c["hyp"]) for c in rep["clips"]]
        row = [rep["system"], f"{corpus_cer(pairs, a.lang):.3f}", f"{main_script_cer(pairs, a.lang):.3f}"]
        if ref_hyp and p != a.ref_voice:
            row.append(f"{corpus_cer([(ref_hyp[c['id']], c['hyp']) for c in rep['clips']], a.lang):.3f}")
        print(" | ".join(row))


if __name__ == "__main__":
    main()
