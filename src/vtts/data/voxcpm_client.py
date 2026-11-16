"""Client for an OpenAI-compatible speech API (the VoxCPM2 voice service) used to synthesize
training data: bounded concurrency, a request-rate cap, retries, and a resumable manifest.

Credentials come from an env file (VOXCPM_URL, VOXCPM_KEY) and never reach the manifest or logs.
Audio is kept at the service's native rate as FLAC; dataset preparation resamples later.
"""

from __future__ import annotations

import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

DEFAULT_ENV = Path("~/.config/vtts/voxcpm.env")
MIN_SECONDS = 0.3


def load_env(path: Path = DEFAULT_ENV) -> tuple[str, str]:
    vals = {}
    for line in Path(os.path.expanduser(str(path))).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals["VOXCPM_URL"].rstrip("/"), vals["VOXCPM_KEY"]


def build_request(text: str, voice: str) -> dict:
    return {"model": "tts-1", "voice": voice, "response_format": "wav", "input": text}


def parse_response(body: bytes) -> tuple[np.ndarray, int]:
    x, sr = sf.read(io.BytesIO(body), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x, sr


class RateLimiter:
    """At most `per_minute` acquisitions in any 60 s window (shared by worker threads)."""

    def __init__(self, per_minute: int):
        self.gap = 60.0 / per_minute
        self.next = 0.0
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            now = time.monotonic()
            wait = self.next - now
            self.next = max(now, self.next) + self.gap
        if wait > 0:
            time.sleep(wait)


@dataclass
class Result:
    id: str
    status: str  # ok | bad_audio | failed
    attempts: int
    dur: float = 0.0
    sr_in: int = 0
    error: str = ""


def synth_one(session: requests.Session, url: str, key: str, item: dict, voice: str, out_dir: Path,
              limiter: RateLimiter | None = None, max_attempts: int = 5, backoff: float = 2.0) -> Result:
    dst = out_dir / f"{item['id']}.flac"
    err = ""
    for attempt in range(1, max_attempts + 1):
        if limiter:
            limiter.acquire()
        try:
            r = session.post(f"{url}/v1/audio/speech", json=build_request(item["text"], voice),
                             headers={"Authorization": f"Bearer {key}"}, timeout=180)
        except requests.RequestException as e:
            err = type(e).__name__
            time.sleep(backoff * attempt)
            continue
        if r.status_code == 200:
            try:
                x, sr = parse_response(r.content)
            except (RuntimeError, sf.LibsndfileError) as e:
                return Result(item["id"], "bad_audio", attempt, error=f"decode: {type(e).__name__}")
            dur = len(x) / sr if sr else 0.0
            if dur < MIN_SECONDS or not np.isfinite(x).all() or float(np.abs(x).max(initial=0.0)) < 1e-4:
                return Result(item["id"], "bad_audio", attempt, dur, sr, "empty or silent")
            tmp = dst.with_suffix(".tmp.flac")
            sf.write(tmp, x, sr, subtype="PCM_16")
            tmp.replace(dst)
            return Result(item["id"], "ok", attempt, round(dur, 3), sr)
        err = f"http {r.status_code}"
        if r.status_code in (400, 401, 403, 413):
            break  # not retryable
        wait = float(r.headers.get("Retry-After", backoff * attempt))
        time.sleep(min(wait, 60.0))
    return Result(item["id"], "failed", attempt, error=err)


def done_ids(manifest: Path) -> set[str]:
    if not manifest.exists():
        return set()
    out = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("status") == "ok":
                out.add(rec["id"])
    return out


def run(items: list[dict], out_dir: Path, voice: str, workers: int = 4, per_minute: int = 110,
        env: Path = DEFAULT_ENV, log_every: int = 200) -> dict[str, int]:
    url, key = load_env(env)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audio").mkdir(exist_ok=True)
    manifest = out_dir / "manifest.jsonl"
    skip = done_ids(manifest)
    todo = [it for it in items if it["id"] not in skip]
    limiter = RateLimiter(per_minute)
    counts = {"ok": 0, "bad_audio": 0, "failed": 0, "skipped": len(items) - len(todo)}
    lock = threading.Lock()
    local = threading.local()

    def work(it: dict) -> None:
        if not hasattr(local, "s"):
            local.s = requests.Session()
        res = synth_one(local.s, url, key, it, voice, out_dir / "audio", limiter)
        rec = {**res.__dict__, "lang": it.get("lang", ""), "voice": voice}
        with lock:
            with manifest.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[res.status] += 1
            n = counts["ok"] + counts["bad_audio"] + counts["failed"]
            if log_every and n % log_every == 0:
                print(f"{n}/{len(todo)} {counts}", flush=True)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(work, todo))
    return counts
