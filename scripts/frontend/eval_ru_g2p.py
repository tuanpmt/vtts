"""Agreement of the Russian front-end with eSpeak NG (a measuring stick only; nothing from eSpeak
is used by vtts).

  uv run python scripts/frontend/eval_ru_g2p.py sentences WIKI.jsonl SENTENCES.jsonl [--n 2000]
  uv run python scripts/frontend/eval_ru_g2p.py reference SENTENCES.jsonl REF.jsonl [--espeak espeak-ng]
  uv run python scripts/frontend/eval_ru_g2p.py compare REF.jsonl [--errors 30]

WIKI.jsonl has Wikipedia articles ({"text": ...}, one per line, e.g. a dump of the
wikimedia/wikipedia 20231101.ru stream shuffled with seed 1); "sentences" keeps sentences of the
odd-numbered articles (the even ones chose the entries of lexicons/ru/stress.tsv, see
scripts/frontend/build_ru_stress.py) that vtts.data.wiki_corpus accepts. "reference" reads every
word of the normalized sentences (normalize_ru; clitics joined with a hyphen are split again)
with `espeak-ng -v ru -x`, one word per clause.

Both sides are compared on a coarse alphabet: consonants with their softness (p p' ... sh zh ts
ch shch j); stressed vowels a e i o u y; unstressed vowels as classes A (a, @; eSpeak V @ a#), I
(i; eSpeak I e i), U and Y. Metrics: stress (same stressed vowel, words with two or more vowels),
words read the same, phoneme error rate (Levenshtein / reference phonemes), all weighted by
running words, without the clitics of g2p_ru.UNSTRESSED and words without a vowel (eSpeak reads
a lone clitic stressed and в as a letter name). eSpeak NG makes its own errors (unknown names, some stresses), so 100% is not the
goal; the error lists show where the two differ.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

STRESSED = {"a": "a", "A": "a", "e": "e", "E": "e", "i": "i", "I": "i", "o": "o", "8": "o",
            "u": "u", "U": "u", "y": "y", "I#": "y", "V": "a", "@": "a", "a#": "a"}
UNSTRESSED = {"a": "A", "A": "A", "V": "A", "@": "A", "a#": "A", "o": "A", "8": "A", "e": "I",
              "E": "I", "i": "I", "I": "I", "I#": "Y", "y": "Y", "u": "U", "U": "U"}
CONS = ("tS;", "tS", "S;", "ts", "dZ", "S", "Z", "p", "b", "t", "d", "k", "g", "f", "v", "s", "z",
        "m", "n", "l", "r", "x", "j", "N", "h", "w")
CONS_NAME = {"tS;": "ch", "tS": "ch", "S;": "shch", "S": "sh", "Z": "zh", "ts": "ts", "dZ": "zh",
             "N": "n", "h": "x", "w": "v"}
VOWEL_SYMS = sorted(STRESSED, key=len, reverse=True)


def espeak_coarse(s: str) -> list[str]:
    s = s.replace("@-", "").replace("-", "").replace(",", "").replace(":", "").replace("_", "")
    out: list[str] = []
    k, stress = 0, False
    while k < len(s):
        if s[k] == "'":
            stress = True
            k += 1
            continue
        for c in CONS:
            if s.startswith(c, k):
                k += len(c)
                soft = k < len(s) and s[k] == ";"
                k += soft
                name = CONS_NAME.get(c, c)
                if name in ("ch", "shch", "j", "sh", "zh", "ts"):
                    out.append(name)
                else:
                    out.append(name + ("'" if soft else ""))
                break
        else:
            for v in VOWEL_SYMS:
                if s.startswith(v, k):
                    k += len(v)
                    out.append(STRESSED[v] if stress else UNSTRESSED[v])
                    stress = False
                    break
            else:
                k += 1  # other marks
    return out


def ours_coarse(phonemes: tuple[str, ...]) -> list[str]:
    out = []
    for p in phonemes:
        if p.endswith("1"):
            out.append(p[0])
        elif p in ("a", "@"):
            out.append("A")
        elif p in ("i", "u", "y"):
            out.append(p.upper())
        else:
            out.append(p)
    return out


def _words(text: str) -> list[str]:
    from vtts.frontend.ru.normalize_ru import normalize_ru

    out = []
    for w in normalize_ru(text).split():
        out += [p for p in w.split("-") if re.fullmatch(r"[а-яё]+", p)]
    return out


def sentences(src: Path, out: Path, n: int) -> None:
    from vtts.data.wiki_corpus import accept, split_sentences

    rows = []
    for i, line in enumerate(src.read_text(encoding="utf-8").splitlines()):
        if i % 2 == 0:
            continue
        taken = 0
        for para in json.loads(line)["text"].split("\n"):
            for s in split_sentences(para, "ru"):
                if taken < 2 and accept(s, "ru"):
                    rows.append({"id": f"ru_g2p_{len(rows):05d}", "text": s})
                    taken += 1
        if len(rows) >= n:
            break
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows[:n]), encoding="utf-8")


def reference(src: Path, out: Path, espeak: str) -> None:
    rows = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x]
    vocab = sorted({w for r in rows for w in _words(r["text"])})
    res = subprocess.run([espeak, "-q", "-x", "-v", "ru"], input="\n".join(w + "." for w in vocab),
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


def _stress_index(seq: list[str]) -> int | None:
    vowels = [p for p in seq if p in "aeiouyAIUY"]
    return next((k for k, p in enumerate(vowels) if p.islower()), None)


def compare(ref_path: Path, n_errors: int) -> None:
    from vtts.frontend.ru.g2p_ru import UNSTRESSED, phonemes, stress_source

    words = same = ph_err = ph_tot = st_ok = st_tot = 0
    stress_errs: Counter[tuple[str, str, str]] = Counter()
    word_errs: Counter[tuple[str, str, str]] = Counter()
    sources: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    for line in ref_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        for w, e in zip(r["words"], r["ref"]):
            if w in UNSTRESSED or not any(ch in "аеёиоуыэюя" for ch in w):
                continue  # clitics: eSpeak reads a lone word stressed (and в as a letter name)
            ref, hyp = espeak_coarse(e), ours_coarse(phonemes(w))
            words += 1
            same += ref == hyp
            ph_err += _edits(ref, hyp)
            ph_tot += len(ref)
            if ref != hyp:
                word_errs[(w, " ".join(ref), " ".join(hyp))] += 1
            if sum(p in "aeiouyAIUY" for p in ref) >= 2:
                st_tot += 1
                ok = _stress_index(ref) == _stress_index(hyp)
                st_ok += ok
                src = stress_source(w)
                sources[src] += 1
                by_source[src] += ok
                if not ok:
                    stress_errs[(w, e, " ".join(phonemes(w)))] += 1
    print(json.dumps({"words": words, "stress_agreement": round(st_ok / max(st_tot, 1), 4),
                      "word_agreement": round(same / max(words, 1), 4),
                      "phoneme_error_rate": round(ph_err / max(ph_tot, 1), 4)}))
    print("stress source of words with two or more vowels (share, stress agreement):",
          json.dumps({k: [round(n / max(st_tot, 1), 4), round(by_source[k] / n, 4)]
                      for k, n in sources.most_common()}))
    print("stress differences (word, eSpeak, vtts):")
    for (w, e, h), c in stress_errs.most_common(n_errors):
        print(f"  {c:4d} {w}\t{e}\t{h}")
    print("word differences (word, eSpeak coarse, vtts coarse):")
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
