"""Build the sentence list for speech synthesis from Wikipedia (CC BY-SA) for es, id, pt, th, hi.

Articles are split into sentences (Thai: space-separated chunks) and filtered by
vtts.data.wiki_corpus.accept (plain text that needs no normalization; nothing else is filtered).
At most --per-article sentences are taken from one article so the list covers many topics. Hours
are estimated at the rates in vtts.data.wiki_corpus. Ids are <lang>000000...; pt uses the "pt"
dump and is used as Brazilian Portuguese (sentences with European-Portuguese markers are rejected).
Thai rows are utterances of joined space-separated chunks.

Usage: uv run python scripts/data/build_wiki_corpus.py --lang es --out data/es/sentences.jsonl \
       [--hours 30]
"""

import argparse
import json
import random
from pathlib import Path

from vtts.data.wiki_corpus import LANGS, accept, accept_plain, seconds, split_sentences


def main() -> None:
    from datasets import load_dataset

    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=LANGS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=30)
    ap.add_argument("--per-article", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    budget, total, out, seen = a.hours * 3600, 0.0, [], set()
    checked = passed = eu = 0
    ds = load_dataset("wikimedia/wikipedia", f"20231101.{a.lang}", split="train", streaming=True)
    ds = ds.shuffle(seed=a.seed, buffer_size=10000)
    for art in ds:
        taken = 0
        for para in art["text"].split("\n"):
            for s in split_sentences(para, a.lang):
                checked += 1
                if not accept(s, a.lang):
                    eu += a.lang == "pt" and accept_plain(s, a.lang)
                    continue
                passed += 1
                if taken >= a.per_article or s in seen:
                    continue
                seen.add(s)
                out.append(s)
                taken += 1
                total += seconds(s, a.lang)
            if taken >= a.per_article:
                break
        if total >= budget:
            break
    random.Random(a.seed).shuffle(out)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for i, s in enumerate(out):
            f.write(json.dumps({"id": f"{a.lang}{i:06d}", "text": s, "lang": a.lang}, ensure_ascii=False) + "\n")
    print(f"{a.lang} {len(out)} sentences, about {total / 3600:.1f} h; "
          f"acceptance {passed}/{checked} = {100 * passed / max(checked, 1):.1f}%"
          + (f"; European Portuguese rejected {eu} of {eu + passed} readable "
             f"({100 * eu / max(eu + passed, 1):.1f}%)" if a.lang == "pt" else ""))


if __name__ == "__main__":
    main()
