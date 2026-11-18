"""Build the Korean sentence list for speech synthesis from Korean Wikipedia (CC BY-SA).

Articles are split into sentences and filtered by vtts.data.ko_corpus.accept_ko. At most
--per-article sentences are taken from one article so the list covers many topics. Hours are
estimated at 5.5 syllables/s.

Usage: uv run python scripts/data/build_ko_corpus.py --out data/ko/sentences.jsonl [--hours 30]
"""

import argparse
import json
import random
from pathlib import Path

from vtts.data.ko_corpus import accept_ko, ko_seconds, split_ko


def main() -> None:
    from datasets import load_dataset

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=30)
    ap.add_argument("--per-article", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    budget, total, out, seen = a.hours * 3600, 0.0, [], set()
    ds = load_dataset("wikimedia/wikipedia", "20231101.ko", split="train", streaming=True)
    ds = ds.shuffle(seed=a.seed, buffer_size=10000)
    for art in ds:
        taken = 0
        for para in art["text"].split("\n"):
            for s in split_ko(para):
                if taken >= a.per_article or s in seen or not accept_ko(s):
                    continue
                seen.add(s)
                out.append(s)
                taken += 1
                total += ko_seconds(s)
            if taken >= a.per_article:
                break
        if total >= budget:
            break
    random.Random(a.seed).shuffle(out)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for i, s in enumerate(out):
            f.write(json.dumps({"id": f"ko{i:06d}", "text": s, "lang": "ko"}, ensure_ascii=False) + "\n")
    print(f"ko {len(out)} sentences, about {total / 3600:.1f} h")


if __name__ == "__main__":
    main()
