"""Evaluate teacher checkpoints as they appear; keep best.pt -> lowest OOD CER.

Usage (GPU box, alongside training):
  uv run python scripts/teacher/eval_checkpoints.py --run artifacts/teacher/run1 \
      --sets eval/sets/ood.jsonl eval/sets/heldout.jsonl --watch
"""

import argparse
import gc
import json
import time
from pathlib import Path

import soundfile as sf
import torch

from vtts.eval.asr import AsrTranscriber
from vtts.eval.run_eval import evaluate
from vtts.teacher.infer import Teacher


def _evaluate_ckpt(ckpt: Path, sets: list[Path], asr: AsrTranscriber, device: str, mos: bool,
                   noise_scale: float) -> dict:
    step = int(ckpt.stem.split("_")[1])
    teacher = Teacher.load(ckpt, device)
    teacher.cfg.noise_scale = noise_scale
    summary: dict = {"step": step, "ckpt": ckpt.name, "noise_scale": noise_scale}
    for set_path in sets:
        rows = [json.loads(x) for x in set_path.read_text(encoding="utf-8").splitlines() if x]
        audio_dir = ckpt.parent / "eval" / f"{step:07d}" / set_path.stem
        audio_dir.mkdir(parents=True, exist_ok=True)
        for r in rows:
            sf.write(audio_dir / f"{r['id']}.wav", teacher.synthesize(r["text"]), 22050)
        rep = evaluate(f"teacher@{step}", set_path.stem, audio_dir, rows, asr.transcribe, mos=mos)
        summary[set_path.stem] = {"cer": rep.corpus_cer, "wer": rep.corpus_wer,
                                  "utmos": rep.mean_utmos, "dnsmos": rep.mean_dnsmos,
                                  "whistle": rep.mean_whistle}
        (audio_dir.parent / f"{set_path.stem}.json").write_text(json.dumps(
            [c.__dict__ for c in rep.clips], ensure_ascii=False, indent=1))
    del teacher
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return summary


def _update_best(run: Path, results: list[dict], key: str) -> None:
    scored = [r for r in results if key in r and (run / r["ckpt"]).exists()]
    if not scored:
        return
    best = min(scored, key=lambda r: r[key]["cer"])
    link = run / "best.pt"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(best["ckpt"])
    (run / "best.json").write_text(json.dumps(best, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--sets", type=Path, nargs="+", required=True)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--poll", type=int, default=300)
    ap.add_argument("--no-mos", action="store_true")
    ap.add_argument("--device", default=None, help="ASR device (default: cuda > mps > cpu)")
    ap.add_argument("--tts-device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--asr-model", default="vinai/PhoWhisper-large")
    ap.add_argument("--noise-scale", type=float, default=0.333,
                    help="0.333 measured best: CER 0.029 vs 0.062 at 0.667, no buzz unlike 0.0")
    args = ap.parse_args()
    results_path = args.run / "eval_results.jsonl"
    asr = AsrTranscriber(args.asr_model, device=args.device)
    while True:
        done = set()
        results = []
        if results_path.exists():
            results = [json.loads(x) for x in results_path.read_text().splitlines() if x]
            done = {r["ckpt"] for r in results}
        todo = [c for c in sorted(args.run.glob("ckpt_*.pt")) if c.name not in done]
        for ckpt in todo:
            summary = _evaluate_ckpt(ckpt, args.sets, asr, args.tts_device, not args.no_mos,
                                     args.noise_scale)
            with results_path.open("a") as f:
                f.write(json.dumps(summary) + "\n")
            results.append(summary)
            print(json.dumps(summary), flush=True)
            _update_best(args.run, results, args.sets[0].stem)
        if not args.watch:
            break
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
