"""Evaluate rendered clips: CER/WER (PhoWhisper), whistle, UTMOS, DNSMOS.

Usage: uv run python scripts/eval/eval_dir.py --system NAME --set eval/sets/ood.jsonl \
       --audio DIR --out reports/NAME-ood.json [--no-mos]
English or mixed sets: --lang en|mixed --asr openai/whisper-large-v3 --asr-language en|vi
"""

import argparse
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from vtts.eval.asr import AsrTranscriber
from vtts.eval.cer import corpus_cer
from vtts.eval.run_eval import evaluate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--no-mos", action="store_true")
    ap.add_argument("--lang", default="vi", help="text normalization for CER/WER: vi | en | mixed")
    ap.add_argument("--asr", default="vinai/PhoWhisper-large")
    ap.add_argument("--asr-language", default=None, help="force the Whisper language (en, vi)")
    args = ap.parse_args()
    sents = [json.loads(ln) for ln in args.set.read_text(encoding="utf-8").splitlines() if ln]
    asr = AsrTranscriber(args.asr, language=args.asr_language)
    rep = evaluate(args.system, args.set.stem, args.audio, sents, asr.transcribe,
                   mos=not args.no_mos, lang=args.lang)
    by_group = defaultdict(list)
    for c in rep.clips:
        by_group[c.group].append((c.ref, c.hyp))
    out = asdict(rep) | {"group_cer": {g: corpus_cer(p, args.lang) for g, p in by_group.items()}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{args.system}/{args.set.stem}: CER={rep.corpus_cer:.4f} WER={rep.corpus_wer:.4f} "
          f"whistle={rep.mean_whistle:.1f} UTMOS={rep.mean_utmos} DNSMOS={rep.mean_dnsmos}")
    print("group CER:", {g: round(v, 4) for g, v in out["group_cer"].items()})


if __name__ == "__main__":
    main()
