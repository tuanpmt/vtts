"""Score synthesized Mandarin clips with Whisper and list the ones to leave out of training.

Usage: uv run python scripts/data/asr_filter.py --sentences data/zh/sentences.jsonl \
       --synth data/zh/synth_nu10 [--model openai/whisper-large-v3]
Writes SYNTH/asr.jsonl (one row per clip, resumable) and SYNTH/rejected.txt (ids), which
scripts/data/synth_to_csv.py --reject leaves out.
"""

import argparse
import json
from pathlib import Path

from vtts.data.asr_filter import _han, accept, zh_cer
from vtts.eval.asr import AsrTranscriber


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--synth", type=Path, required=True)
    ap.add_argument("--model", default="openai/whisper-large-v3")
    ap.add_argument("--batch-size", type=int, default=16)
    a = ap.parse_args()
    text = {}
    for line in a.sentences.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            text[r["id"]] = r["text"]
    dur = {}
    for line in (a.synth / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["status"] == "ok" and r["id"] in text:
                dur[r["id"]] = r["dur"]
    out = a.synth / "asr.jsonl"
    done = {json.loads(x)["id"] for x in out.read_text().splitlines()} if out.exists() else set()
    todo = [i for i in sorted(dur) if i not in done]
    print(f"{len(done)} scored, {len(todo)} to go", flush=True)
    asr = AsrTranscriber(a.model, language="zh")
    with out.open("a", encoding="utf-8") as f:
        for k in range(0, len(todo), 256):
            ids = todo[k:k + 256]
            hyps = asr.transcribe([a.synth / "audio" / f"{i}.flac" for i in ids], batch_size=a.batch_size)
            for i, h in zip(ids, hyps):
                c = zh_cer(text[i], h)
                f.write(json.dumps({"id": i, "cer": round(c, 4), "hyp": h}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{len(done) + k + len(ids)}/{len(dur)}", flush=True)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    bad = [r["id"] for r in rows if not accept(r["cer"], dur[r["id"]], len(_han(text[r["id"]])))]
    (a.synth / "rejected.txt").write_text("\n".join(bad) + "\n")
    mean = sum(r["cer"] for r in rows) / max(1, len(rows))
    print(f"mean CER {mean:.3f}; rejected {len(bad)} of {len(rows)} clips")


if __name__ == "__main__":
    main()
