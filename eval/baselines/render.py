"""Render a sentence set with a black-box baseline voice.

Runs in its own venv (eval/baselines). Input text is normalized by vtts through a
subprocess, so every system reads numbers/abbreviations identically, and nothing
from these GPL tools is imported into vtts.

Usage (from eval/baselines):
  uv run python render.py --system sanotts-vi --set ../sets/ood.jsonl --out ../../artifacts/baselines/sanotts-vi/ood
  uv run python render.py --system piper-25h  --set ../sets/ood.jsonl --out ../../artifacts/baselines/piper-25h/ood
"""

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
PIPER_VOICE = "vi_VN-25hours_single-low"
PIPER_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/"
             "25hours_single/low/vi_VN-25hours_single-low.onnx")


def normalized(texts: list[str]) -> list[str]:
    code = ("import json,sys;from vtts.frontend.normalize import normalize;"
            "print(json.dumps([normalize(t) for t in json.load(sys.stdin)],ensure_ascii=False))")
    out = subprocess.run(["uv", "run", "--project", str(ROOT), "python", "-c", code],
                         input=json.dumps(texts), capture_output=True, text=True, check=True,
                         cwd=ROOT)
    return json.loads(out.stdout.strip().splitlines()[-1])


def render_sanotts(texts, ids, out: Path) -> None:
    import sanotts

    for uid, text in zip(ids, texts):
        r = sanotts.synthesize(text, voice="vi")
        sf.write(out / f"{uid}.wav", np.asarray(r.audio, dtype=np.float32), r.sample_rate)


def render_piper(texts, ids, out: Path) -> None:
    from urllib.request import urlretrieve

    from piper import PiperVoice

    cache = ROOT / "artifacts" / "baselines" / "models"
    cache.mkdir(parents=True, exist_ok=True)
    onnx = cache / f"{PIPER_VOICE}.onnx"
    for suffix, url in ((".onnx", PIPER_URL), (".onnx.json", PIPER_URL + ".json")):
        dst = cache / f"{PIPER_VOICE}{suffix}"
        if not dst.exists():
            urlretrieve(url, dst)
    voice = PiperVoice.load(str(onnx))
    for uid, text in zip(ids, texts):
        with wave.open(str(out / f"{uid}.wav"), "wb") as wf:
            voice.synthesize_wav(text, wf)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=["sanotts-vi", "piper-25h"], required=True)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rows = [json.loads(ln) for ln in args.set.read_text(encoding="utf-8").splitlines() if ln]
    args.out.mkdir(parents=True, exist_ok=True)
    texts = normalized([r["text"] for r in rows])
    ids = [r["id"] for r in rows]
    {"sanotts-vi": render_sanotts, "piper-25h": render_piper}[args.system](texts, ids, args.out)
    print(f"rendered {len(ids)} clips to {args.out}")


if __name__ == "__main__":
    main()
