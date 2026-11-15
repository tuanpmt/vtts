"""Score every prepared clip with ASR + DNSMOS; resumable (skips ids already in --out).

Usage: uv run python scripts/score_dataset.py --prepared data/infore1/prepared --out data/infore1/scores.jsonl
"""

import argparse
import json
import time
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import soundfile as sf

from vtts.eval.asr import AsrTranscriber
from vtts.eval.mos import dnsmos


def _init_worker() -> None:
    import torch

    torch.set_num_threads(1)


def _dnsmos_file(path: Path) -> float:
    x, sr = sf.read(path, dtype="float32")
    return dnsmos(x, sr, num_threads=1)["ovrl"]  # one thread per worker process


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--chunk", type=int, default=256)
    ap.add_argument("--dnsmos-workers", type=int, default=max(1, (os.cpu_count() or 4) - 4))
    ap.add_argument("--asr-model", default="vinai/PhoWhisper-small",
                    help="small is ~6x faster than large on MPS; enough for data filtering")
    args = ap.parse_args()

    ids = [ln.split("|", 1)[0] for ln in (args.prepared / "metadata.csv").read_text(
        encoding="utf-8").splitlines() if ln]
    done = set()
    if args.out.exists():
        done = {json.loads(ln)["id"] for ln in args.out.read_text(encoding="utf-8").splitlines()}
    todo = [i for i in ids if i not in done]
    print(f"total={len(ids)} done={len(done)} todo={len(todo)}", flush=True)

    # create workers before CUDA is initialised in this process (fork safety)
    pool = ProcessPoolExecutor(max_workers=args.dnsmos_workers, initializer=_init_worker)
    pool.submit(int).result()
    asr = AsrTranscriber(args.asr_model)
    t0 = time.time()
    with args.out.open("a", encoding="utf-8") as f:
        for start in range(0, len(todo), args.chunk):
            chunk = todo[start: start + args.chunk]
            paths = [args.prepared / "wavs" / f"{i}.wav" for i in chunk]
            dns = pool.map(_dnsmos_file, paths, chunksize=8)  # CPU, overlaps with ASR on the GPU
            texts = asr.transcribe(paths, batch_size=args.batch_size)
            for uid, text, ovrl in zip(chunk, texts, dns):
                f.write(json.dumps({"id": uid, "asr": text, "dnsmos_ovrl": ovrl},
                                   ensure_ascii=False) + "\n")
            f.flush()
            n = start + len(chunk)
            rate = n / (time.time() - t0)
            print(f"{n}/{len(todo)} {rate:.2f} clips/s eta {(len(todo) - n) / rate / 60:.1f} min",
                  flush=True)


if __name__ == "__main__":
    main()
