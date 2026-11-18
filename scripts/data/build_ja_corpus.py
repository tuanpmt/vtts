"""Build the Japanese sentence list for speech synthesis from Japanese Wikipedia (CC BY-SA).

Articles are split into sentences and filtered by vtts.data.ja_corpus.accept_ja (plain kana and
kanji, 10-60 characters, ending with 。！？, every kanji readable by the front-end tables). At most
--per-article sentences are taken from one article so the list covers many topics. Hours are
estimated at 7.5 morae/s.

Usage: uv run --extra gpu python scripts/data/build_ja_corpus.py --out data/ja/sentences.jsonl \
       [--hours 30]
"""

import argparse
import json
import os
import random
from pathlib import Path

from vtts.data.ja_corpus import accept_ja, ja_seconds, split_ja


def main() -> None:
    from datasets import load_dataset

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=30)
    ap.add_argument("--per-article", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    budget, total, out, seen = a.hours * 3600, 0.0, [], set()
    ds = load_dataset("wikimedia/wikipedia", "20231101.ja", split="train", streaming=True)
    ds = ds.shuffle(seed=a.seed, buffer_size=10000)
    for art in ds:
        taken = 0
        for para in art["text"].split("\n"):
            for s in split_ja(para):
                if taken >= a.per_article or s in seen or not accept_ja(s):
                    continue
                seen.add(s)
                out.append(s)
                taken += 1
                total += ja_seconds(s)
            if taken >= a.per_article:
                break
        if total >= budget:
            break
    random.Random(a.seed).shuffle(out)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for i, s in enumerate(out):
            f.write(json.dumps({"id": f"ja{i:06d}", "text": s, "lang": "ja"}, ensure_ascii=False) + "\n")
    print(f"ja {len(out)} sentences, about {total / 3600:.1f} h", flush=True)
    os._exit(0)  # the datasets streaming iterator can hang on exit


if __name__ == "__main__":
    main()
