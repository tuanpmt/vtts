"""Score one vi-en student (.vtts) the same way for every quality experiment.

Usage:
  uv run --extra gpu python scripts/eval/student_quality.py --model M.q8.vtts --out DIR [--name NAME]
      [--sets ood,mixed,ood_en] [--no-asr] [--no-mos] [--jobs 8]
  uv run --extra gpu python scripts/eval/student_quality.py --audio-root DIR --out DIR --name teacher
      (score renders that already exist as DIR/<set>/<id>.wav, e.g. the teacher's)
  uv run --extra gpu python scripts/eval/student_quality.py --table OUT1/summary.json OUT2/summary.json ...

1. Renders eval/sets/{ood,mixed,ood_en}.jsonl with the C runtime exactly as
   docs/reports/bilingual-student-eval.md: `runtime/build/vtts_say MODEL OUT.wav --lex lex_en.bin
   --lang auto TEXT`, one clip per row.
2. Scores each set with scripts/eval/eval_dir.py: ood with PhoWhisper-large (vi); ood_en with
   Whisper large-v3 (--lang en --asr-language en); mixed with Whisper large-v3 (--lang mixed
   --asr-language vi). CER, WER, UTMOS, DNSMOS, whistle.
3. Computes the 5-10 kHz noise metrics (vtts.eval.hfnoise: spectral flatness and HF energy ratio
   per 250 ms voiced window) pooled over each set.
Writes DIR/<set>/*.wav, DIR/<set>.json (eval_dir), DIR/hf_<set>.json and DIR/summary.json.
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import soundfile as sf

from vtts.eval.hfnoise import hf_noise, summarize

ROOT = Path(__file__).resolve().parents[2]
RT = ROOT / "runtime"
SAY, LEX = RT / "build" / "vtts_say", RT / "build" / "lex_en.bin"
SETS = {  # set -> eval_dir.py arguments (same as the v0.4.0 student report)
    "ood": [],
    "mixed": ["--lang", "mixed", "--asr", "openai/whisper-large-v3", "--asr-language", "vi"],
    "ood_en": ["--lang", "en", "--asr", "openai/whisper-large-v3", "--asr-language", "en"],
}


def render_set(model: Path, rows: list[dict], out: Path, jobs: int) -> None:
    out.mkdir(parents=True, exist_ok=True)

    def one(r: dict) -> None:
        wav = out / f"{r['id']}.wav"
        if wav.exists():
            return
        p = subprocess.run([str(SAY), str(model), str(wav.with_suffix(".tmp.wav")), "--lex", str(LEX),
                            "--lang", "auto", r["text"]], check=False, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"vtts_say failed on {r['id']}: {p.stderr.strip()}")
        wav.with_suffix(".tmp.wav").replace(wav)

    with ThreadPoolExecutor(jobs) as pool:
        list(pool.map(one, rows))


def hf_set(audio: Path, rows: list[dict]) -> dict:
    clips = {}
    for r in rows:
        p = audio / f"{r['id']}.wav"
        if p.exists():
            x, sr = sf.read(p, dtype="float32")
            clips[r["id"]] = hf_noise(x, sr)
    return {"summary": summarize(clips), "clips": clips}


def score(name: str, set_name: str, audio: Path, out: Path, no_mos: bool) -> dict:
    res = out / f"{set_name}.json"
    cmd = [sys.executable, str(ROOT / "scripts" / "eval" / "eval_dir.py"), "--system", name,
           "--set", str(ROOT / "eval" / "sets" / f"{set_name}.jsonl"), "--audio", str(audio),
           "--out", str(res), *SETS[set_name]] + (["--no-mos"] if no_mos else [])
    subprocess.run(cmd, check=True)
    d = json.loads(res.read_text())
    return {k: d.get(k) for k in ("corpus_cer", "corpus_wer", "mean_utmos", "mean_dnsmos", "mean_whistle")}


def table(paths: list[Path]) -> str:
    rows = [json.loads(p.read_text()) for p in paths]
    sets = [s for s in SETS if any(s in r["sets"] for r in rows)]

    def f(v, nd=3):
        return "-" if v is None else f"{v:.{nd}f}"

    head = ["system"] + [f"{s} {k}" for s in sets for k in ("CER", "UTMOS", "flat", "HF dB")]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cells = [r["name"]]
        for s in sets:
            d = r["sets"].get(s, {})
            cells += [f(d.get("corpus_cer")), f(d.get("mean_utmos"), 2), f(d.get("flatness_mean")),
                      f(d.get("hf_ratio_db_mean"), 1)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path)
    ap.add_argument("--audio-root", type=Path, help="score existing renders DIR/<set>/<id>.wav")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--name", default=None)
    ap.add_argument("--sets", default=",".join(SETS))
    ap.add_argument("--no-asr", action="store_true", help="only render + HF metrics")
    ap.add_argument("--no-mos", action="store_true")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--table", type=Path, nargs="+", help="print a comparison of summary.json files")
    a = ap.parse_args()
    if a.table:
        print(table(a.table))
        return
    if not a.out or (a.model is None) == (a.audio_root is None):
        ap.error("--out and exactly one of --model / --audio-root are required")
    name = a.name or (a.model.stem if a.model else a.audio_root.name)
    sets = [s for s in a.sets.split(",") if s]
    unknown = set(sets) - set(SETS)
    if unknown:
        ap.error(f"unknown sets {sorted(unknown)}")
    if a.model:
        subprocess.run(["make", "-s", "-C", str(RT), "build/vtts_say", "build/lex_en.bin"], check=True)
    a.out.mkdir(parents=True, exist_ok=True)
    summary = {"name": name, "model": str(a.model) if a.model else None, "sets": {}}
    for s in sets:
        rows = [json.loads(x) for x in (ROOT / "eval" / "sets" / f"{s}.jsonl").read_text(encoding="utf-8").splitlines() if x]
        audio = (a.audio_root / s) if a.audio_root else (a.out / s)
        if a.model:
            render_set(a.model, rows, audio, a.jobs)
        hf = hf_set(audio, rows)
        (a.out / f"hf_{s}.json").write_text(json.dumps(hf))
        d = dict(hf["summary"])
        if not a.no_asr:
            d.update(score(name, s, audio, a.out, a.no_mos))
        summary["sets"][s] = d
        print(s, json.dumps(d), flush=True)
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(table([a.out / "summary.json"]))


if __name__ == "__main__":
    main()
