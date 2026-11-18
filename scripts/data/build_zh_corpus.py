"""Build the Mandarin sentence list for speech synthesis from Chinese Wikipedia (CC BY-SA).

Articles are converted to Simplified Chinese, split into sentences and filtered by
vtts.data.zh_corpus.accept_zh. At most --per-article sentences are taken from one article so the
list covers many topics. Hours are estimated at 4.5 characters/s.

Usage: uv run python scripts/data/build_zh_corpus.py --out data/zh/sentences.jsonl [--hours 40]
"""

import argparse
import json
import random
from pathlib import Path

from vtts.data.zh_corpus import accept_zh, split_zh, to_simplified, zh_seconds


def main() -> None:
    from datasets import load_dataset

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=40)
    ap.add_argument("--per-article", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    budget, total, out, seen = a.hours * 3600, 0.0, [], set()
    ds = load_dataset("wikimedia/wikipedia", "20231101.zh", split="train", streaming=True)
    ds = ds.shuffle(seed=a.seed, buffer_size=10000)
    for art in ds:
        taken = 0
        for para in to_simplified(art["text"]).split("\n"):
            for s in split_zh(para):
                if taken >= a.per_article or s in seen or not accept_zh(s):
                    continue
                seen.add(s); out.append(s); taken += 1; total += zh_seconds(s)
            if taken >= a.per_article:
                break
        if total >= budget:
            break
    random.Random(a.seed).shuffle(out)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for i, s in enumerate(out):
            f.write(json.dumps({"id": f"zh{i:06d}", "text": s, "lang": "zh"}, ensure_ascii=False) + "\n")
    print(f"zh {len(out)} sentences, about {total / 3600:.1f} h")


if __name__ == "__main__":
    main()
