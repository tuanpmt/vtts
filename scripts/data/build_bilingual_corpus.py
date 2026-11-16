"""Build the bilingual sentence list for speech synthesis.

- vi: sentences from the Vietnamese corpus (data/corpus/sentences.txt) without digits or spelled
  words, chosen greedily so every syllable seen in the corpus appears >= --min-count times, then
  filled at random up to the hour target.
- en: English Wikipedia sentences (CC BY-SA), 6-30 words, letters only (no digits, no all-caps
  words, no brackets), streamed with `datasets`.
- mixed: Vietnamese templates with one English term (scripts/data/bilingual/*.txt).

Hours are estimated from text length (vi 4.2 syllables/s, en 2.6 words/s, mixed 3.8 words/s).
The output is shuffled with a fixed seed so any prefix of it has the same language mix.

Usage: uv run python scripts/data/build_bilingual_corpus.py --vi-corpus data/corpus/sentences.txt \
       --out data/bilingual/sentences.jsonl [--hours-vi 45 --hours-en 35 --hours-mixed 8]
"""

import argparse
import collections
import json
import random
import re
from pathlib import Path

from vtts.frontend.normalize import normalize, spelled_words
from vtts.frontend.phoneme_set import PUNCTUATION

HERE = Path(__file__).parent / "bilingual"
DIGIT = re.compile(r"\d")
EN_OK = re.compile(r"^[A-Za-z][A-Za-z ,.'?!;:-]+[.?!]$")
SPLIT = re.compile(r"(?<=[.!?])\s+")


def syllables(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w not in PUNCTUATION]


def pick_vi(lines: list[str], hours: float, min_count: int, rng: random.Random) -> list[str]:
    cands = []
    for s in lines:
        s = s.strip()
        if not s or DIGIT.search(s) or spelled_words(s):
            continue
        syl = syllables(s)
        if 6 <= len(syl) <= 40:
            cands.append((s, syl))
    rng.shuffle(cands)
    freq = collections.Counter(x for _, syl in cands for x in syl)
    seen: collections.Counter = collections.Counter()
    budget, total, out, used = hours * 3600, 0.0, [], set()
    for i, (s, syl) in enumerate(sorted(cands, key=lambda c: min(freq[x] for x in c[1]))):
        if total >= budget * 0.5:
            break
        if any(seen[x] < min_count for x in syl):
            out.append(s); used.add(s); seen.update(syl); total += len(syl) / 4.2
    for s, syl in cands:
        if total >= budget:
            break
        if s not in used:
            out.append(s); used.add(s); total += len(syl) / 4.2
    return out


def pick_en(hours: float, rng: random.Random) -> list[str]:
    from datasets import load_dataset

    budget, total, out, seen = hours * 3600, 0.0, [], set()
    ds = load_dataset("wikimedia/wikipedia", "20231101.en", split="train", streaming=True)
    for art in ds:
        for para in art["text"].split("\n"):
            for s in SPLIT.split(para.strip()):
                words = s.split()
                if not 6 <= len(words) <= 30 or s in seen or not EN_OK.match(s):
                    continue
                if any(len(w) > 1 and w.strip(",.?!;:'-").isupper() for w in words):
                    continue
                seen.add(s); out.append(s); total += len(words) / 2.6
                if total >= budget:
                    return out
    return out


def pick_mixed(hours: float, rng: random.Random) -> list[str]:
    terms = [t for t in (HERE / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (HERE / "templates_vi.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    combos = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    rng.shuffle(combos)
    budget, total, out = hours * 3600, 0.0, []
    for s in combos:
        if total >= budget:
            break
        out.append(s); total += len(s.split()) / 3.8
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vi-corpus", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours-vi", type=float, default=45)
    ap.add_argument("--hours-en", type=float, default=35)
    ap.add_argument("--hours-mixed", type=float, default=8)
    ap.add_argument("--min-count", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    vi = pick_vi(a.vi_corpus.read_text(encoding="utf-8").splitlines(), a.hours_vi, a.min_count, rng)
    mixed = pick_mixed(a.hours_mixed, rng)
    en = pick_en(a.hours_en, rng)
    rows = ([{"id": f"vi{i:06d}", "text": s, "lang": "vi"} for i, s in enumerate(vi)]
            + [{"id": f"en{i:06d}", "text": s, "lang": "en"} for i, s in enumerate(en)]
            + [{"id": f"mx{i:06d}", "text": s, "lang": "mixed"} for i, s in enumerate(mixed)])
    rng.shuffle(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"vi {len(vi)}  en {len(en)}  mixed {len(mixed)}  total {len(rows)}")


if __name__ == "__main__":
    main()
