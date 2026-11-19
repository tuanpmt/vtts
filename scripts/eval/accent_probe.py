"""Accent probe for a synthesis voice: Whisper large-v3 CER (forced language) and the share of
clips Whisper identifies as the target language.

Usage: uv run python scripts/eval/accent_probe.py --lang es --voice nu-es \
           --sentences eval/sets/ood_es.jsonl --out DIR [--n 20] [--synth]
With --synth, N sentences are first synthesized into DIR through the VoxCPM2 service
(~/.config/vtts/voxcpm.env), retrying 503 busy / 429 rate_limited as the service documents.
Target for a native-sounding voice: identified as the language in >= 90% of clips.
"""

import argparse
import json
import random
import re
import time
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf

LID = ("vi", "en", "zh", "ko", "ja", "es", "pt", "id", "ms", "th", "hi", "it", "gl", "ca", "de", "fr", "ru", "ar", "tr", "pl",
       "nl", "da", "sv", "no", "fi", "el", "he", "tl", "my", "km", "lo", "sw", "uk", "fa", "ur")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t.lower())
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def edits(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def synth(rows: list[dict], voice: str, out: Path) -> None:
    import requests

    from vtts.data.voxcpm_client import build_request, load_env, parse_response

    url, key = load_env()
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    for r in rows:
        p = out / f"{r['id']}.wav"
        if p.exists():
            continue
        start = time.monotonic()
        for attempt in range(5):
            b = s.post(f"{url}/v1/audio/speech", json=build_request(r["text"], voice),
                       headers={"Authorization": f"Bearer {key}"}, timeout=180)
            if b.status_code == 200:
                x, sr = parse_response(b.content)
                sf.write(p, x, sr)
                break
            try:
                code = b.json().get("error")
            except ValueError:
                code = None
            retry = (b.status_code == 503 and code == "busy") or (b.status_code == 429 and code == "rate_limited")
            wait = max(float(b.headers.get("Retry-After", 0)), 0.5 * 2 ** attempt * random.uniform(0.5, 1.5))
            if not retry or attempt == 4 or time.monotonic() - start + wait > 30:
                b.raise_for_status()
                raise RuntimeError(f"{r['id']}: http {b.status_code} {code}")
            time.sleep(wait)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--synth", action="store_true")
    a = ap.parse_args()
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines() if x.strip()]
    random.Random(1).shuffle(rows)
    rows = rows[:a.n]
    if a.synth:
        synth(rows, a.voice, a.out)

    import librosa
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    dev = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.float16 if dev != "cpu" else torch.float32
    proc = WhisperProcessor.from_pretrained("openai/whisper-large-v3")
    model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-large-v3", dtype=dtype).to(dev).eval()
    tok = {lang: proc.tokenizer.convert_tokens_to_ids(f"<|{lang}|>") for lang in LID}
    err = chars = 0
    probs, worst = [], []
    for r in rows:
        p = a.out / f"{r['id']}.wav"
        if not p.exists():
            continue
        x, sr = sf.read(p, dtype="float32")
        x = librosa.resample(x.mean(1) if x.ndim > 1 else x, orig_sr=sr, target_sr=16000)
        feats = proc(x, sampling_rate=16000, return_tensors="pt").input_features.to(dev, dtype)
        with torch.no_grad():
            start = torch.tensor([[model.config.decoder_start_token_id]], device=dev)
            lp = model(input_features=feats, decoder_input_ids=start).logits[0, -1].float().softmax(-1)
            pl = {lang: lp[t].item() for lang, t in tok.items()}
            total = sum(pl.values())
            probs.append({lang: v / total for lang, v in pl.items()})
            ids = model.generate(feats, language=a.lang, task="transcribe", max_new_tokens=220)
        hyp = proc.batch_decode(ids, skip_special_tokens=True)[0]
        ref, h = norm(r["text"]), norm(hyp)
        e = edits(ref, h)
        err += e
        chars += len(ref)
        worst.append((e / max(1, len(ref)), r["text"], hyp))
    mean = {lang: float(np.mean([q[lang] for q in probs])) for lang in LID}
    top = sorted(mean.items(), key=lambda kv: -kv[1])[:3]
    share = float(np.mean([max(q, key=q.get) == a.lang for q in probs]))
    print(f"{a.lang} {a.voice}: n={len(probs)} CER={err / max(1, chars):.4f} identified={share:.2f} "
          f"top: {', '.join(f'{k} {v:.2f}' for k, v in top)}")
    for c, ref, hyp in sorted(worst, reverse=True)[:3]:
        print(f"  {c:.2f} | {ref[:70]} | {hyp[:70]}")


if __name__ == "__main__":
    main()
