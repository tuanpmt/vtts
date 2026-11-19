"""Build the Russian stress tables lexicons/ru/stress_suffixes.tsv and lexicons/ru/stress.tsv.

Source: Koziev/NLP_Datasets Stress/all_accents.tsv (CC0-1.0, https://github.com/Koziev/NLP_Datasets,
1.68 million word forms, "word<TAB>w^ord" with ^ before the stressed vowel; ё is written е).
Russian Wikipedia word counts are used only to weight and choose entries; no text is included.

  uv run python scripts/frontend/build_ru_stress.py freq --out ru_freq.tsv [--articles 20000]
  uv run python scripts/frontend/build_ru_stress.py build --accents all_accents.tsv --freq ru_freq.tsv

1. Suffix table: for every word form of the source with two or more vowels, the stressed vowel
   counted from the end (0 = last vowel). Suffixes of 1-7 letters seen with a weight of at least 3
   (weight 1 + sqrt(Wikipedia count) per form) keep their most common position when it differs
   from that of the next shorter suffix (a pruned suffix tree); "-" is the empty suffix.
2. Word table: forms the suffix table gets wrong that occur at least --min-count times in the
   Wikipedia counts, written with "+" before the stressed vowel; plus words whose ё the text
   usually omits: a form written with ё in more than half of its Wikipedia occurrences (and 3
   times or more) is stored with its ё (ё is always stressed), which also corrects source entries
   whose stress was put on the wrong е (^еще -> ещё).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

OUT = Path(__file__).parents[2] / "src" / "vtts" / "frontend" / "lexicons" / "ru"
VOWELS = frozenset("аеиоуыэюяё")
MAX_SUFFIX, MIN_WEIGHT = 7, 3
YO_SHARE, YO_MIN = 0.5, 3
LETTERS = re.compile(r"[а-яё]+")
WORD = re.compile(r"[а-яё]+(?:-[а-яё]+)*")


def count_words(out: Path, articles: int) -> None:
    from datasets import load_dataset

    ds = load_dataset("wikimedia/wikipedia", "20231101.ru", split="train", streaming=True)
    c: collections.Counter[str] = collections.Counter()
    for i, art in enumerate(ds.shuffle(seed=1, buffer_size=10000)):
        if i >= 2 * articles:
            break
        if i % 2 == 0:  # odd articles are held out for scripts/frontend/eval_ru_g2p.py
            c.update(WORD.findall(art["text"].lower()))
    out.write_text("".join(f"{w}\t{n}\n" for w, n in c.most_common()), encoding="utf-8")


def from_end(marked: str) -> tuple[str, int] | None:
    """(word, stressed vowel counted from the end) of a source entry like мол^око."""
    s = marked.replace("ѐ", "е").replace("ѝ", "и")
    if s.count("^") != 1:
        return None
    k = s.index("^")
    word = s.replace("^", "")
    if k >= len(word) or word[k] not in VOWELS:
        return None
    return word, sum(ch in VOWELS for ch in word[k + 1:])


def mark(word: str, back: int) -> str:
    """Word with + before the vowel `back` vowels from the end."""
    idx = [i for i, ch in enumerate(word) if ch in VOWELS]
    k = idx[len(idx) - 1 - back]
    return word[:k] + "+" + word[k:]


def build(accents: Path, freq_path: Path, min_count: int) -> None:
    freq: collections.Counter[str] = collections.Counter()
    yo: collections.Counter[str] = collections.Counter()
    for line in freq_path.read_text(encoding="utf-8").splitlines():
        w, n = line.split("\t")
        freq[w.replace("ё", "е")] += int(n)
        if "ё" in w:
            yo[w] += int(n)
    data: dict[str, int] = {}
    for line in accents.read_text(encoding="utf-8").splitlines():
        w, s = line.split("\t")
        r = from_end(s)
        if r and r[0] == w and LETTERS.fullmatch(w) and sum(ch in VOWELS for ch in w) >= 2:
            data[w] = r[1]

    counts: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    for w, pos in data.items():
        wt = 1 + freq.get(w, 0) ** 0.5
        for n in range(min(MAX_SUFFIX, len(w)) + 1):
            counts[w[len(w) - n:]][pos] += wt
    pred = {"": counts[""].most_common(1)[0][0]}
    table = {"": pred[""]}
    for n in range(1, MAX_SUFFIX + 1):
        for suf in sorted(s for s in counts if len(s) == n):
            c = counts[suf]
            if sum(c.values()) < MIN_WEIGHT:
                continue
            parent = suf[1:]
            while parent not in pred:
                parent = parent[1:]
            best = c.most_common(1)[0][0]
            pred[suf] = best
            if best != pred[parent]:
                table[suf] = best

    def predict(w: str) -> int:
        for n in range(min(MAX_SUFFIX, len(w)), -1, -1):
            if w[len(w) - n:] in table:
                return table[w[len(w) - n:]]
        return 0

    words: dict[str, str] = {}
    for w, pos in data.items():
        if freq.get(w, 0) >= min_count and predict(w) != pos:
            words[w] = mark(w, pos)
    n_yo = 0
    for w, n in yo.items():
        plain = w.replace("ё", "е")
        if not LETTERS.fullmatch(w) or n < YO_MIN or n <= YO_SHARE * freq[plain] or w.count("ё") != 1:
            continue
        words[plain] = w.replace("ё", "+ё")
        n_yo += 1
    with (OUT / "stress_suffixes.tsv").open("w", encoding="utf-8") as f:
        f.write("# Russian stress by word ending: suffix (\"-\" + letters, ё written е) <TAB> stressed\n"
                "# vowel counted from the end of the word (0 = last vowel). Longest matching suffix\n"
                "# wins. Generated by scripts/frontend/build_ru_stress.py from Koziev/NLP_Datasets\n"
                "# Stress/all_accents.tsv (CC0-1.0).\n")
        for suf in sorted(table, key=lambda s: (s[::-1])):
            f.write(f"-{suf}\t{table[suf]}\n")
    with (OUT / "stress.tsv").open("w", encoding="utf-8") as f:
        f.write("# Russian stress of word forms the suffix table gets wrong, and words whose ё is\n"
                "# usually written е: word (ё written е) <TAB> word with + before the stressed vowel.\n"
                "# Generated by scripts/frontend/build_ru_stress.py from Koziev/NLP_Datasets\n"
                "# Stress/all_accents.tsv (CC0-1.0); Russian Wikipedia counts chose the entries.\n")
        for w in sorted(words):
            f.write(f"{w}\t{words[w]}\n")
    ok = tot = 0
    for w, pos in data.items():
        f_ = freq.get(w, 0)
        tot += f_
        ok += f_ * (w in words or predict(w) == pos)
    print(json.dumps({"suffixes": len(table), "words": len(words), "yo": n_yo,
                      "token_agreement_with_source": round(ok / max(tot, 1), 4)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freq")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--articles", type=int, default=20000)
    b = sub.add_parser("build")
    b.add_argument("--accents", type=Path, required=True)
    b.add_argument("--freq", type=Path, required=True)
    b.add_argument("--min-count", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "freq":
        count_words(a.out, a.articles)
    else:
        build(a.accents, a.freq, a.min_count)


if __name__ == "__main__":
    main()
