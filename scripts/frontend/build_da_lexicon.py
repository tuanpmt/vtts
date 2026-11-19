"""Build the Danish word tables src/vtts/frontend/lexicons/da/{lexicon.tsv,words.txt}.

Usage: uv run python scripts/frontend/build_da_lexicon.py --nst PATH/dan030224NST.pron \
       --freq PATH/da_freq.json [--top 30000] [--min-count 20]

Sources (offline only, nothing is downloaded at run time):
- NST pronunciation lexicon for Danish (Nordic Language Technology, distributed by the National
  Library of Norway's Språkbanken under CC0 1.0): www.nb.no/sbfil/leksikalske_databaser/leksikon/
  da_leksikon.tar.gz, file dan030224NST.pron (ISO-8859-1, 51 ';'-separated fields; field 0 the
  spelling, 1 the part of speech, 11 the SAMPA transcription with " % stress, $ syllables, ? stød).
- Word counts of Danish Wikipedia (only the counts are used, to choose the frequent words):
  --freq, a JSON list of [word, count] pairs, lower case (see the --count option to make it from
  the wikimedia/wikipedia 20231101.da parquet files).

The --top most frequent words (count >= --min-count) that NST transcribes are kept. A word the
rules (vtts.frontend.da.g2p_da.rules) read exactly like NST goes to words.txt (a known word, for
compound splitting); any other word goes to lexicon.tsv with its NST reading in da-en tokens. For a
homograph the reading of the most frequent part of speech of written Danish wins (PRIORITY), and
proper names (PM) only when the word has no other reading.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

OUT = Path(__file__).parents[2] / "src" / "vtts" / "frontend" / "lexicons" / "da"
PRIORITY = ("PP", "KN", "DT", "PN", "AB", "VB", "RG", "JJ", "NN", "IN", "UO")
WORD = re.compile(r"[a-zæøåé]+")
VOWEL_SYMBOLS = "ieEaAy29uoOQ@6"
CONSONANT_MAP = {"p": "p", "t": "t", "k": "k", "b": "b", "d": "d", "g": "g", "f": "f", "v": "v",
                 "s": "s", "h": "h", "m": "m", "n": "n", "N": "N", "l": "l", "R": "R", "r": "R",
                 "j": "j", "D": "D", "w": "w"}


def nst_to_tokens(sampa: str) -> list[str] | None:
    """da-en token names of one NST transcription (one word), or None for a symbol not handled."""
    out: list[str] = []
    for syl in sampa.replace("¤", "").split("$"):
        stress = ""
        if syl.startswith('"'):
            stress, syl = ("%" if '"' in out else '"'), syl[1:]
        elif syl.startswith("%"):
            stress, syl = "%", syl[1:]
        if '"' in syl or "%" in syl or "_" in syl:
            return None
        seen_vowel = False
        i = 0
        while i < len(syl):
            ch = syl[i]
            if ch in VOWEL_SYMBOLS:
                long = i + 1 < len(syl) and syl[i + 1] == ":"
                if ch == "6" and seen_vowel:
                    tok = "6~"
                elif ch == "6":
                    tok = "V" if stress else "6"
                elif ch == "@":
                    tok = "@"
                else:
                    tok = ch + (":" if long else "")
                if ch in "@6" and long:
                    return None
                out.append(tok)
                if not seen_vowel and stress:
                    out.append(stress)
                seen_vowel = True
                i += 2 if long else 1
                continue
            if ch == "?":
                out.append("?")
            elif ch == "s" and i + 1 < len(syl) and syl[i + 1] == "'":
                out.append("s'")
                i += 1
            elif ch == "j" and seen_vowel:
                out.append("j~")
            elif ch in CONSONANT_MAP:
                out.append(CONSONANT_MAP[ch])
            else:
                return None
            i += 1
    return out


def load_nst(path: Path) -> dict[str, list[tuple[str, str]]]:
    """lower-case spelling -> [(SAMPA, part of speech)] of one-word entries."""
    lex: dict[str, list[tuple[str, str]]] = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        f = line.split(";")
        if len(f) < 12 or not f[11] or f[7] or not f[0] or "_" in f[0]:
            continue
        lex.setdefault(f[0].lower(), []).append((f[11], f[1].split("|")[0]))
    return lex


def best_reading(entries: list[tuple[str, str]]) -> str:
    def rank(e: tuple[str, str]) -> int:
        return PRIORITY.index(e[1]) if e[1] in PRIORITY else len(PRIORITY) + (e[1] == "PM")

    return min(entries, key=rank)[0]


def count_words(parquets: list[Path]) -> list[list]:
    import collections

    import pyarrow.parquet as pq

    c: collections.Counter = collections.Counter()
    for p in parquets:
        for text in pq.read_table(p, columns=["text"]).column("text").to_pylist():
            c.update(WORD.findall(text.lower()))
    return [[w, n] for w, n in c.most_common(400_000)]


def main() -> None:
    from vtts.frontend.da.g2p_da import rules

    ap = argparse.ArgumentParser()
    ap.add_argument("--nst", type=Path, required=True)
    ap.add_argument("--freq", type=Path, required=True)
    ap.add_argument("--count", type=Path, nargs="*", help="parquet files: write --freq from them")
    ap.add_argument("--top", type=int, default=30000)
    ap.add_argument("--min-count", type=int, default=20)
    a = ap.parse_args()
    if a.count:
        a.freq.write_text(json.dumps(count_words(a.count), ensure_ascii=False), encoding="utf-8")
    freq = json.loads(a.freq.read_text(encoding="utf-8"))
    nst = load_nst(a.nst)
    lexicon: dict[str, list[str]] = {}
    words: list[str] = []
    for w, n in freq:
        if len(lexicon) + len(words) >= a.top or n < a.min_count:
            break
        if not WORD.fullmatch(w) or w not in nst:
            continue
        toks = nst_to_tokens(best_reading(nst[w]))
        if toks is None:
            continue
        if rules(w) == toks:
            words.append(w)
        else:
            lexicon[w] = toks
    head = ("# Generated by scripts/frontend/build_da_lexicon.py from the NST pronunciation lexicon for\n"
            "# Danish (CC0 1.0) and Danish Wikipedia word counts. ")
    (OUT / "lexicon.tsv").write_text(
        head + "Words the rules misread: word<TAB>da-en tokens.\n"
        + "".join(f"{w}\t{' '.join(t)}\n" for w, t in sorted(lexicon.items())), encoding="utf-8")
    (OUT / "words.txt").write_text(
        head + "Words the rules read like NST (known words for compounds).\n"
        + "".join(f"{w}\n" for w in sorted(words)), encoding="utf-8")
    print(f"{len(lexicon)} lexicon entries, {len(words)} rule-read words "
          f"({100 * len(words) / max(1, len(words) + len(lexicon)):.1f}% read by the rules)")


if __name__ == "__main__":
    main()
