"""Japanese Wikipedia text for building and evaluating the Japanese reading tables.

Writes OUT/train.txt (sentences for word frequencies: Japanese characters and marks only, 5-200
characters) and OUT/heldout.txt (sentences from other articles, filtered like the synthesis corpus
by vtts.data.ja_corpus.plain_ja, at most 3 per article). Every --heldout-every-th article goes to
the held-out set and is never used for training.

Usage: uv run --extra gpu python scripts/frontend/fetch_ja_text.py --out data/ja/lexicon \
       [--train 400000] [--heldout 2000]
"""

import argparse
import os
import re
from pathlib import Path

from vtts.data.ja_corpus import plain_ja, split_ja

TRAIN_ALLOWED = re.compile(r"^[一-鿿々〆ヶぁ-ゖァ-ヺーゝゞヽヾ、。！？「」・]{5,200}$")


def main() -> None:
    from datasets import load_dataset

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--train", type=int, default=400000)
    ap.add_argument("--heldout", type=int, default=2000)
    ap.add_argument("--heldout-every", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    ds = load_dataset("wikimedia/wikipedia", "20231101.ja", split="train", streaming=True)
    ds = ds.shuffle(seed=a.seed, buffer_size=10000)
    train, held, seen = [], [], set()
    for n, art in enumerate(ds):
        is_held = n % a.heldout_every == 0
        taken = 0
        for para in art["text"].split("\n"):
            for s in split_ja(para):
                if s in seen:
                    continue
                if is_held:
                    if len(held) < a.heldout and taken < 3 and plain_ja(s):
                        held.append(s)
                        taken += 1
                elif len(train) < a.train and TRAIN_ALLOWED.match(s):
                    train.append(s)
                seen.add(s)
        if len(train) >= a.train and len(held) >= a.heldout:
            break
    (a.out / "train.txt").write_text("\n".join(train) + "\n", encoding="utf-8")
    (a.out / "heldout.txt").write_text("\n".join(held) + "\n", encoding="utf-8")
    print(f"{len(train)} training sentences, {len(held)} held-out sentences", flush=True)
    os._exit(0)  # the streaming iterator can hang on exit


if __name__ == "__main__":
    main()
