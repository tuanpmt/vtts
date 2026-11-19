"""Agreement of the Polish front-end with eSpeak NG (a measuring stick only; nothing from eSpeak
is used by vtts).

  uv run python scripts/frontend/eval_pl_g2p.py sentences WIKI.jsonl SENTENCES.jsonl [--n 2000]
  uv run python scripts/frontend/eval_pl_g2p.py reference SENTENCES.jsonl REF.jsonl [--espeak espeak-ng]
  uv run python scripts/frontend/eval_pl_g2p.py compare REF.jsonl [--errors 30]

WIKI.jsonl has Wikipedia articles ({"text": ...}, one per line, e.g. a dump of the
wikimedia/wikipedia 20231101.pl stream shuffled with seed 1); "sentences" keeps sentences of the
odd-numbered articles that vtts.data.wiki_corpus accepts (the even ones were used to look for
exceptions). "reference" reads every word of the normalized sentences (normalize_pl; the
prepositions joined with a hyphen are split again) with `espeak-ng -v pl -x`, one word per
clause.

Both sides are compared on a coarse alphabet: consonants (sh zh ch dzh s' z' c' dz' n' w x ts dz
and k' g'; eSpeak's other palatalized consonants and ŋ are folded to the plain ones), vowels
a e i o u y and the nasal vowels on en, stress on one vowel. Metrics: stress (words with two or
more vowels), words read the same, phoneme error rate (Levenshtein / reference phonemes), all
over running words without the clitics of g2p_pl.UNSTRESSED (eSpeak stresses a lone clitic) and
words without a vowel.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

VOWELS = {"O~": "on", "E~": "en", "a#": "a", "E#": "e", "E": "e", "O": "o", "a": "a", "i": "i",
          "u": "u", "y": "y", "@": "e", "e": "e", "o": "o"}
CONS = {"tS": "ch", "dZ": "dzh", "ts;": "c'", "dz;": "dz'", "ts": "ts", "dz": "dz", "S;": "s'",
        "Z;": "z'", "s;": "s'", "z;": "z'", "S": "sh", "Z": "zh", "n^": "n'", "N": "n", "R": "r", "C": "x",
        "k;": "k'", "g;": "g'"}
PLAIN = "pbtdkgfvszxjlmnrw"
SYMS = sorted([*VOWELS, *CONS], key=len, reverse=True)


def espeak_coarse(s: str) -> list[str]:
    s = s.replace(",", "").replace(":", "").replace("_", "").replace("-", "")
    out: list[str] = []
    k, stress = 0, False
    while k < len(s):
        if s[k] == "'":
            stress = True
            k += 1
            continue
        for sym in SYMS:
            if s.startswith(sym, k):
                k += len(sym)
                if sym in VOWELS:
                    out.append(VOWELS[sym] + ("1" if stress else ""))
                    stress = False
                else:
                    out.append(CONS[sym])
                break
        else:
            if s[k] in PLAIN:
                out.append(s[k])
                k += 1
                if k < len(s) and s[k] == ";":
                    k += 1  # palatalized p b m f v ...: not marked in pl-en
            else:
                k += 1
    return out


def _words(text: str) -> list[str]:
    from vtts.frontend.pl.normalize_pl import normalize_pl

    out = []
    for w in normalize_pl(text).split():
        out += [p for p in w.split("-") if re.fullmatch(r"[a-ząćęłńóśźż]+", p)]
    return out


def sentences(src: Path, out: Path, n: int) -> None:
    from vtts.data.wiki_corpus import accept, split_sentences

    rows = []
    for i, line in enumerate(src.read_text(encoding="utf-8").splitlines()):
        if i % 2 == 0:
            continue
        taken = 0
        for para in json.loads(line)["text"].split("\n"):
            for s in split_sentences(para, "pl"):
                if taken < 2 and accept(s, "pl"):
                    rows.append({"id": f"pl_g2p_{len(rows):05d}", "text": s})
                    taken += 1
        if len(rows) >= n:
            break
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows[:n]), encoding="utf-8")


def reference(src: Path, out: Path, espeak: str) -> None:
    rows = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x]
    vocab = sorted({w for r in rows for w in _words(r["text"])})
    res = subprocess.run([espeak, "-q", "-x", "-v", "pl"], input="\n".join(w + "." for w in vocab),
                         capture_output=True, text=True, check=True)
    lines = [x.strip() for x in res.stdout.splitlines() if x.strip()]
    if len(lines) != len(vocab):
        raise SystemExit(f"eSpeak returned {len(lines)} lines for {len(vocab)} words")
    table = dict(zip(vocab, lines))
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            words = _words(r["text"])
            f.write(json.dumps({"id": r["id"], "text": r["text"], "words": words,
                                "ref": [table[w] for w in words]}, ensure_ascii=False) + "\n")


def _edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def _vowels(seq: list[str]) -> list[str]:
    return [p for p in seq if p.rstrip("1") in ("a", "e", "i", "o", "u", "y", "on", "en")]


def compare(ref_path: Path, n_errors: int) -> None:
    from vtts.frontend.pl.g2p_pl import UNSTRESSED, phonemes

    words = same = ph_err = ph_tot = st_ok = st_tot = 0
    stress_errs: Counter[tuple[str, str, str]] = Counter()
    word_errs: Counter[tuple[str, str, str]] = Counter()
    for line in ref_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        for w, e in zip(r["words"], r["ref"]):
            if w in UNSTRESSED or not any(ch in "aeiouyąęó" for ch in w):
                continue
            ref, hyp = espeak_coarse(e), list(phonemes(w))
            words += 1
            same += ref == hyp
            ph_err += _edits(ref, hyp)
            ph_tot += len(ref)
            if ref != hyp:
                word_errs[(w, " ".join(ref), " ".join(hyp))] += 1
            rv, hv = _vowels(ref), _vowels(hyp)
            if len(rv) >= 2:
                st_tot += 1
                ok = [v.endswith("1") for v in rv] == [v.endswith("1") for v in hv]
                st_ok += ok
                if not ok:
                    stress_errs[(w, e, " ".join(hyp))] += 1
    print(json.dumps({"words": words, "stress_agreement": round(st_ok / max(st_tot, 1), 4),
                      "word_agreement": round(same / max(words, 1), 4),
                      "phoneme_error_rate": round(ph_err / max(ph_tot, 1), 4)}))
    print("stress differences (word, eSpeak, vtts):")
    for (w, e, h), c in stress_errs.most_common(n_errors):
        print(f"  {c:4d} {w}\t{e}\t{h}")
    print("word differences (word, eSpeak coarse, vtts):")
    for (w, e, h), c in word_errs.most_common(n_errors):
        print(f"  {c:4d} {w}\t{e}\t{h}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sentences")
    s.add_argument("src", type=Path)
    s.add_argument("out", type=Path)
    s.add_argument("--n", type=int, default=2000)
    r = sub.add_parser("reference")
    r.add_argument("src", type=Path)
    r.add_argument("out", type=Path)
    r.add_argument("--espeak", default="espeak-ng")
    c = sub.add_parser("compare")
    c.add_argument("ref", type=Path)
    c.add_argument("--errors", type=int, default=30)
    a = ap.parse_args()
    if a.cmd == "sentences":
        sentences(a.src, a.out, a.n)
    elif a.cmd == "reference":
        reference(a.src, a.out, a.espeak)
    else:
        compare(a.ref, a.errors)


if __name__ == "__main__":
    main()
