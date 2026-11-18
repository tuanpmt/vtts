"""Build the Japanese reading tables in src/vtts/frontend/lexicons/ja/: words.tsv,
after_kanji.tsv, after_katakana.tsv and kanji.tsv.

Usage:
  uv run --extra gpu python scripts/frontend/fetch_ja_text.py --out data/ja/lexicon
  uv run python scripts/frontend/build_ja_lexicon.py --corpus data/ja/lexicon/train.txt \
      --heldout data/ja/lexicon/heldout.txt
  uv run python scripts/frontend/build_ja_lexicon.py --heldout data/ja/lexicon/heldout.txt \
      --eval-only            # agreement of the current tables

Source of every reading: Open JTalk with mecab-naist-jdic (BSD-3), through pyopenjtalk (MIT; a
dev dependency only, never used at run time). Japanese Wikipedia text (--corpus) only decides
which words are frequent; no text is stored. Steps:

1. Analyze the corpus with pyopenjtalk: words (surface, pronunciation, class of the previous
   character: kanji, katakana or other) and their counts.
2. kanji.tsv: the --kanji most frequent kanji, each with one default reading, found by aligning
   the readings of all-kanji compounds to their characters (EM over the possible splits; the
   reading used in most compound types wins, so it is usually the on-reading: 学 -> ガク).
3. words.tsv, base: the --base most frequent words containing kanji (and hiragana words
   pronounced unlike their spelling, such as the particle は -> ワ), each with its most frequent
   reading, kept only when the shorter kept words and the kanji defaults would misread them.
   after_kanji.tsv, after_katakana.tsv: the reading a word takes right after a kanji or a
   katakana word when it differs (国 クニ, but コク in 米国 when MeCab splits it; 人 ジン in
   アメリカ人).
4. Context entries: the corpus is read with the tables and compared with Open JTalk's reading;
   the text of each misread stretch (aligned on word boundaries, alone or with a neighbouring
   word) becomes a candidate, accepted when it fixes at least half of the occurrences of that
   text in the same context. Repeated --rounds times until --max-words entries.
5. lexicons/ja/overrides.tsv (hand-edited) wins over everything: surface -> reading.
Report: entries and bytes per table, mora agreement with pyopenjtalk on --heldout.
"""

from __future__ import annotations

import argparse
import itertools
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path

from vtts.frontend.ja.g2p_ja import (
    CONTEXTS,
    Segment,
    Tables,
    context,
    is_ja_char,
    is_kanji,
    segment,
    tables,
)
from vtts.frontend.ja.kana import V, kana_phonemes, to_katakana
from vtts.frontend.lexicons import load_table

OUT = Path(__file__).parents[2] / "src" / "vtts" / "frontend" / "lexicons" / "ja"
SMALL = set("ァィゥェォャュョヮヵヶッンー")
HIRAGANA_WORD = re.compile(r"^[ぁ-ゖー]+$")
KATAKANA_WORD = re.compile(r"^[ァ-ヺー]+$")


# ---------------- analysis ----------------

def clean_pron(pron: str) -> str:
    return pron.replace("’", "")


def analyze(corpus: Path, cache: Path) -> list[list[tuple[str, str]]]:
    """Per sentence, Open JTalk's words as (surface, pronunciation in katakana)."""
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    import pyopenjtalk

    out = []
    for line in corpus.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append([(n["string"], clean_pron(n["pron"])) for n in pyopenjtalk.run_frontend(line)])
    cache.write_bytes(pickle.dumps(out))
    return out


def gold_phonemes(text: str) -> list[str]:
    import pyopenjtalk

    # upper-case vowels are devoiced (not marked by vtts); N is the moraic nasal
    return [p.lower() if p in "AIUEO" else p for p in pyopenjtalk.g2p(text).split()
            if p not in ("pau", "sil")]


def morae(phonemes: list[str]) -> list[str]:
    out, cur = [], []
    for p in phonemes:
        cur.append(p)
        if p in V or p in ("N", "cl"):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def is_word(surface: str) -> bool:
    """A possible table key: Japanese characters only, not a katakana word (read as written)."""
    return bool(surface) and all(is_ja_char(c) for c in surface) and \
        not KATAKANA_WORD.match(surface)


def valid_pron(pron: str) -> bool:
    """Katakana that reads as phonemes (Open JTalk gives 、 or * for some unknown words)."""
    return bool(KATAKANA_WORD.match(pron)) and bool(kana_phonemes(pron))


# ---------------- per-kanji defaults ----------------

def kana_morae(reading: str) -> list[str]:
    """Katakana reading -> morae (small kana are attached to the previous mora; ッ ン ー are
    morae of their own but cannot start a kanji's reading)."""
    out: list[str] = []
    for ch in reading:
        if out and ch in SMALL and ch not in "ッンー":
            out[-1] += ch
        else:
            out.append(ch)
    return out


def splits(units: list[str], n: int, max_len: int = 4):
    """All ways to cut a mora list into n non-empty pieces of at most max_len morae; a piece may
    not start with ッ ン ー."""
    if not units or units[0] in "ッンー":
        return
    if n == 1:
        if len(units) <= max_len:
            yield ("".join(units),)
        return
    for k in range(1, min(max_len, len(units) - n + 1) + 1):
        for rest in splits(units[k:], n - 1, max_len):
            yield ("".join(units[:k]),) + rest


def kanji_defaults(words: Counter, char_freq: Counter, n_kanji: int, iterations: int = 8
                   ) -> dict[str, str]:
    """words: (surface, reading) -> count. Compound types count once each (frequent words are
    in the word table anyway; the default serves the rare compounds)."""
    compounds = set()
    singles: dict[str, Counter] = defaultdict(Counter)
    for (surface, pron), c in words.items():
        if not all(is_kanji(ch) for ch in surface) or not valid_pron(pron):
            continue
        if len(surface) == 1:
            singles[surface][pron] += c
        elif 2 <= len(surface) <= 4:
            compounds.add((surface, pron))
    options = {}
    for surface, pron in sorted(compounds):
        segs = list(splits(kana_morae(pron), len(surface)))
        if segs:
            options[(surface, pron)] = segs
    prob: dict[str, Counter] = defaultdict(Counter)
    for (surface, _), segs in options.items():
        for seg in segs:
            for ch, r in zip(surface, seg):
                prob[ch][r] += 1
    for _ in range(iterations):
        totals = {ch: sum(c.values()) for ch, c in prob.items()}
        counts: dict[str, Counter] = defaultdict(Counter)
        for (surface, _), segs in options.items():
            weights = []
            for seg in segs:
                w = 1.0
                for ch, r in zip(surface, seg):
                    w *= prob[ch][r] / totals[ch] if totals.get(ch) else 0.0
                weights.append(w)
            z = sum(weights)
            if z <= 0:
                continue
            for seg, w in zip(segs, weights):
                for ch, r in zip(surface, seg):
                    counts[ch][r] += w / z
        prob = counts
    out = {}
    for ch, _ in char_freq.most_common():
        if len(out) >= n_kanji:
            break
        cands = [(c, r) for r, c in prob.get(ch, Counter()).items()
                 if not r.endswith("ッ") and c >= 0.5]
        if cands:
            out[ch] = max(cands)[1]
        elif singles.get(ch):
            out[ch] = singles[ch].most_common(1)[0][0]
    return out


# ---------------- word tables ----------------

def phon(reading: str) -> tuple[str, ...]:
    return tuple(kana_phonemes(reading))


def read_text(text: str, t: Tables) -> tuple[str, ...]:
    return phon("".join(s.reading for s in segment(text, t)))


def empty_after() -> dict[str, dict[str, str]]:
    return {c: {} for c in CONTEXTS}


def base_words(words: Counter, kanji: dict[str, str], limit: int, min_freq: int = 1
               ) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """words: (surface, reading, context) -> count. Returns the main table and the context
    tables, reduced to entries that the shorter entries and the kanji defaults misread."""
    by_ctx: dict[str | None, dict[str, Counter]] = {c: defaultdict(Counter)
                                                    for c in (None, *CONTEXTS)}
    for (surface, pron, ctx), c in words.items():
        if is_word(surface) and valid_pron(pron) and not pron.startswith("ー"):
            by_ctx[ctx][surface][pron] += c
    freq: Counter = Counter()
    for dists in by_ctx.values():
        for s, dist in dists.items():
            freq[s] += sum(dist.values())
    main: dict[str, str] = {}
    after = empty_after()
    for surface in freq:
        free = by_ctx[None].get(surface)
        dist = free or next(by_ctx[c][surface] for c in CONTEXTS if surface in by_ctx[c])
        pron, top = dist.most_common(1)[0]
        has_kanji = any(is_kanji(ch) or ch == "々" for ch in surface)
        respelled = bool(HIRAGANA_WORD.match(surface)) and top >= 0.8 * sum(dist.values()) \
            and phon(pron) != phon(surface)
        if not (has_kanji or respelled):
            continue
        main[surface] = pron
        for ctx in CONTEXTS:
            bound = by_ctx[ctx].get(surface)
            if bound and free:
                bpron, btop = bound.most_common(1)[0]
                if btop >= 3 and btop >= 0.5 * sum(bound.values()) and phon(bpron) != phon(pron):
                    after[ctx][surface] = bpron
    ranked = sorted((s for s in main if freq[s] >= min_freq), key=lambda s: (-freq[s], s))[:limit]
    kept: dict[str, str] = {}
    t = Tables.make(kept, {}, kanji)
    for surface in sorted(ranked, key=lambda s: (len(s), s)):
        if read_text(surface, t) != phon(main[surface]):
            kept[surface] = main[surface]
            t = Tables(kept, t.after, kanji, max(t.max_len, len(surface)))
    t = Tables.make(kept, {}, kanji)
    chosen = set(ranked)
    kept_after = {c: {s: r for s, r in after[c].items() if s in chosen and
                      read_text(s, t) != phon(r)} for c in CONTEXTS}
    return kept, kept_after


def regions(nodes: list[tuple[str, str]], segs: list[Segment]) -> list[tuple[int, int, int, int]]:
    """Stretches between boundaries shared by the gold words and the table's segments:
    (start, end, first gold node, end gold node). A kana segment has a boundary at every kana."""
    gold_b, starts, pos = {0}, [], 0
    for s, _ in nodes:
        starts.append(pos)
        pos += len(s)
        gold_b.add(pos)
    seg_b, p = {0}, 0
    for s in segs:
        if s.kind == "kana":
            seg_b.update(range(p + 1, p + len(s.surface)))
        p += len(s.surface)
        seg_b.add(p)
    node_at = {q: k for k, q in enumerate(starts)}
    node_at[pos] = len(nodes)
    common = sorted(gold_b & seg_b)
    return [(a, b, node_at[a], node_at[b]) for a, b in itertools.pairwise(common)]


def _segs_in(segs: list[Segment], a: int, b: int) -> list[Segment]:
    """Segments (or kana pieces of segments) covering [a, b)."""
    out, pos = [], 0
    for s in segs:
        end = pos + len(s.surface)
        if s.kind == "kana":
            lo, hi = max(a, pos), min(b, end)
            if lo < hi:
                out.append(Segment(s.surface[lo - pos:hi - pos], s.reading[lo - pos:hi - pos],
                                   "kana"))
        elif pos >= a and end <= b:
            out.append(s)
        pos = end
    return out


def count_occurrences(sentences, keys: set[str], max_chars: int) -> Counter:
    """(text, context) -> occurrences in the corpus."""
    occur: Counter = Counter()
    for nodes in sentences:
        text = "".join(s for s, _ in nodes)
        for i in range(len(text)):
            ctx = context(text, i)
            for n in range(1, min(max_chars, len(text) - i) + 1):
                if text[i:i + n] in keys:
                    occur[(text[i:i + n], ctx)] += 1
    return occur


def context_entries(sentences, t: Tables, max_new: int, min_count: int, max_chars: int = 8
                    ) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """New entries (main table, context tables) from misread stretches."""
    fixes: Counter = Counter()
    for nodes in sentences:
        text = "".join(s for s, _ in nodes)
        segs = segment(text, t)
        for a, b, na, nb in regions(nodes, segs):
            gold = "".join(p for _, p in nodes[na:nb])
            ours = "".join(s.reading for s in _segs_in(segs, a, b))
            if not is_word(text[a:b]) or phon(ours) == phon(gold):
                continue
            spans = [(a, b, gold)]
            if na > 0:  # the stretch with its neighbouring word on either side
                spans.append((a - len(nodes[na - 1][0]), b, nodes[na - 1][1] + gold))
            if nb < len(nodes):
                spans.append((a, b + len(nodes[nb][0]), gold + nodes[nb][1]))
            for x, y, g in spans:
                span, ctx = text[x:y], context(text, x)
                if y - x <= max_chars and is_word(span) and valid_pron(g) and \
                        span not in (t.after[ctx] if ctx else t.words):
                    fixes[(span, g, ctx)] += 1
    best: dict[tuple[str, str | None], tuple[str, int]] = {}
    for (span, gold, ctx), c in fixes.items():
        if c >= min_count and ((span, ctx) not in best or c > best[(span, ctx)][1]):
            best[(span, ctx)] = (gold, c)
    occur = count_occurrences(sentences, {s for s, _ in best}, max_chars)
    good = sorted(((c, k) for k, (g, c) in best.items() if c >= 0.5 * occur[k]),
                  key=lambda x: (-x[0], x[1][0], x[1][1] or ""))
    main: dict[str, str] = {}
    after = empty_after()
    for _, (span, ctx) in good[:max_new]:
        (after[ctx] if ctx else main)[span] = best[(span, ctx)][0]
    return main, after


# ---------------- evaluation ----------------

def agreement(lines: list[str], t: Tables) -> dict:
    errors = total = exact = 0
    for line in lines:
        gold = morae(gold_phonemes(line))
        e = edit_distance(morae(list(read_text(line, t))), gold)
        errors += e
        total += len(gold)
        exact += e == 0
    return {"mora_agreement": round(1 - errors / max(total, 1), 4),
            "sentence_exact": round(exact / len(lines), 4), "sentences": len(lines),
            "morae": total}


def write(path: Path, rows: dict[str, str], what: str) -> None:
    import pyopenjtalk

    head = (f"# {what}. Generated by scripts/frontend/build_ja_lexicon.py from Open JTalk "
            f"(mecab-naist-jdic, BSD-3) via pyopenjtalk {pyopenjtalk.__version__}; do not edit, "
            f"put fixes in overrides.tsv.\n")
    body = "".join(f"{k}\t{v}\n" for k, v in sorted(rows.items()))
    path.write_text(head + body, encoding="utf-8")
    print(f"{path.name}: {len(rows)} entries, {path.stat().st_size} bytes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path)
    ap.add_argument("--heldout", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--kanji", type=int, default=3000)
    ap.add_argument("--base", type=int, default=120000, help="candidate words before reduction")
    ap.add_argument("--min-freq", type=int, default=1, help="corpus count of a base word")
    ap.add_argument("--max-words", type=int, default=60000, help="entries in both word tables")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--eval-only", action="store_true")
    a = ap.parse_args()
    held = [s for s in a.heldout.read_text(encoding="utf-8").splitlines() if s.strip()]
    if a.eval_only:
        print("held-out:", agreement(held, tables()))
        return
    sentences = analyze(a.corpus, a.corpus.with_suffix(".nodes.pkl"))
    print(f"{len(sentences)} sentences analyzed")
    words: Counter = Counter()
    plain: Counter = Counter()
    char_freq: Counter = Counter()
    for nodes in sentences:
        text, pos = "".join(s for s, _ in nodes), 0
        for s, p in nodes:
            words[(s, p, context(text, pos))] += 1
            plain[(s, p)] += 1
            char_freq.update(ch for ch in s if is_kanji(ch))
            pos += len(s)
    kanji = kanji_defaults(plain, char_freq, a.kanji)
    overrides = {k: to_katakana(v) for k, v in load_table("ja", "overrides").items()}
    kanji.update({k: v for k, v in overrides.items() if len(k) == 1 and is_kanji(k)})
    print(f"kanji defaults: {len(kanji)}; cover "
          f"{sum(char_freq[c] for c in kanji) / sum(char_freq.values()):.4f} of kanji in the corpus")
    main_t, after = base_words(words, kanji, a.base, a.min_freq)
    main_t.update(overrides)
    t = Tables.make(main_t, after, kanji)
    def sizes() -> str:
        return f"{len(main_t)} words + " + " + ".join(f"{len(after[c])} after {c}"
                                                      for c in CONTEXTS)

    print(f"base: {sizes()}", agreement(held[:500], t))
    for r in range(a.rounds):
        room = a.max_words - len(main_t) - sum(map(len, after.values()))
        if room <= 0:
            break
        new_main, new_after = context_entries(sentences, t, room, a.min_count)
        main_t.update(new_main)
        for c in CONTEXTS:
            after[c].update(new_after[c])
        main_t.update(overrides)
        t = Tables.make(main_t, after, kanji)
        print(f"round {r + 1}: {sizes()}", agreement(held[:500], t))
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / "kanji.tsv", kanji, "Default reading per kanji (katakana, as pronounced)")
    write(a.out / "words.tsv", main_t, "Word readings (katakana, as pronounced), forward longest "
          "match")
    for c in CONTEXTS:
        write(a.out / f"after_{c}.tsv", after[c], f"Readings used right after a {c} (they win "
              f"over words.tsv, see ja/g2p_ja.py)")
    print("held-out:", agreement(held, t))


if __name__ == "__main__":
    main()
