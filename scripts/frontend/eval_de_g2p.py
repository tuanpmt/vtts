"""Agreement of the German front-end with eSpeak NG (voice "de"), used only as a measuring stick.

eSpeak NG (GPL) is not a dependency of vtts and nothing derived from it is shipped; install it
(brew install espeak-ng / apt install espeak-ng), then:

  uv run python scripts/frontend/eval_de_g2p.py reference SENTENCES.jsonl REF.jsonl [--exclude data/de/sentences.jsonl]
  uv run python scripts/frontend/eval_de_g2p.py compare REF.jsonl [--half test] [--errors 40]

SENTENCES.jsonl has id and text (plain Wikipedia sentences, e.g. from
scripts/data/build_wiki_corpus.py --lang de with another seed; rows also in --exclude are skipped).
Each word is read in isolation by eSpeak (with its case: Weg / weg) and by g2p_de.phonemes. Both
are mapped to one notation: eSpeak A: -> a:, y -> Y, Y: -> 2:, W -> 9, 3 -> 6, r R -> R and an
R that does not precede a vowel -> 6, pF -> p f, ts -> t s, tS -> t S, _! _| -> ?, "I ;" -> j,
secondary stress dropped. Rows are split by the parity of their position: "dev" (even) was used to
find stems and exceptions, "test" (odd) was not. Metrics over word tokens: words read exactly
(with stress), without stress, without stress and glottal stops; phoneme error rate (Levenshtein,
without stress and glottal stops); stress agreement on words whose sounds agree.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)*")
ESPEAK_MAP = {"A:": "a:", "y": "Y", "Y:": "2:", "W": "9", "3": "6", "r": "R", "_!": "?", "_|": "?",
              "pF": "p f", "ts": "t s", "tS": "t S", "dZ": "d Z", "a#": "a", "E2": "E", "@2": "@",
              "e": "e:", "o": "o:", "i": "i:", "u": "u:", "I2": "I", "aI@": "aI 6", "Q": "O", "UR": "U R", "A": "a", "O~": "O N", "E~": "E N", "A~": "a N", "o~": "O N"}
VOWELS = {"a", "a:", "E", "e:", "E:", "I", "i:", "O", "o:", "U", "u:", "Y", "y:", "9", "2:", "aI",
          "aU", "OY", "@", "6"}


def espeak_words(words: list[str]) -> list[str]:
    exe = shutil.which("espeak-ng") or "/opt/homebrew/bin/espeak-ng"
    out = subprocess.run([exe, "-v", "de", "-q", "-x", "--sep= "], input="\n".join(words) + "\n",
                         capture_output=True, text=True, check=True).stdout.splitlines()
    out = [x.strip() for x in out if x.strip()]
    if len(out) != len(words):
        raise RuntimeError(f"eSpeak returned {len(out)} lines for {len(words)} words")
    return out


def norm_espeak(s: str) -> list[str]:
    """eSpeak -x phonemes -> de-en notation with '1' on the primary-stressed vowel."""
    toks = s.replace(" ;", ";").split()
    out: list[str] = []
    stress = False
    for t in toks:
        if t.lstrip("',") == "I;":
            t = t[:-2] + "j"
        t = t.replace(";", "")
        if t.startswith("'"):
            stress, t = True, t[1:]
        elif t.startswith(","):
            t = t[1:]
        if not t:
            continue
        for p in ESPEAK_MAP.get(t, t).split():
            if p in VOWELS and stress:
                p += "1"
                stress = False
            out.append(p)
    return _coda_r(out)


def _coda_r(ph: list[str]) -> list[str]:
    out = []
    for k, p in enumerate(ph):
        nxt = ph[k + 1].rstrip("1") if k + 1 < len(ph) else None
        if p == "R" and (nxt is None or nxt not in VOWELS) and out and out[-1].rstrip("1") in VOWELS:
            out.append("6")
        else:
            out.append(p)
    res = []
    for p in out:  # @ 6 -> 6
        if p == "6" and res and res[-1] == "@":
            res[-1] = "6"
            continue
        res.append(p)
    return res


def hyp(word: str) -> list[str]:
    from vtts.frontend.de.g2p_de import phonemes

    return _coda_r(list(phonemes(word)))


def reference(src: Path, out: Path, exclude: Path | None) -> None:
    skip = set()
    if exclude and exclude.exists():
        skip = {json.loads(x)["text"] for x in exclude.read_text(encoding="utf-8").splitlines() if x}
    rows = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x]
    rows = [r for r in rows if r["text"] not in skip]
    words = sorted({w for r in rows for w in WORD.findall(r["text"])})
    ref = dict(zip(words, espeak_words(words), strict=True))
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            ws = WORD.findall(r["text"])
            f.write(json.dumps({"id": r["id"], "text": r["text"], "words": ws,
                                "ref": [ref[w] for w in ws]}, ensure_ascii=False) + "\n")


def lev(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def plain(ph: list[str]) -> list[str]:
    return [p.rstrip("1") for p in ph if p != "?"]


def compare(ref: Path, half: str, n_errors: int) -> None:
    rows = [json.loads(x) for x in ref.read_text(encoding="utf-8").splitlines() if x]
    rows = [r for k, r in enumerate(rows) if half == "all" or (k % 2 == 0) == (half == "dev")]
    from vtts.frontend.latin import latin_word_lang

    n = exact = nogl = withgl = stress_ok = poly = edits = phones = english = 0
    errors: Counter = Counter()
    for r in rows:
        for w, e in zip(r["words"], r["ref"], strict=True):
            if "-" in w:
                continue
            if latin_word_lang(w, "de") == "en":  # read by the English module in the pair
                english += 1
                continue
            h = hyp(w.lower())
            g = norm_espeak(e)
            n += 1
            ok = plain(h) == plain(g)
            nogl += ok
            withgl += [p.rstrip("1") for p in h] == [p.rstrip("1") for p in g]
            n_vowels = sum(p.rstrip("1") in VOWELS and p not in ("@", "6") for p in plain(g))
            same_stress = [k for k, p in enumerate(q for q in h if q != "?") if p.endswith("1")] == \
                [k for k, p in enumerate(q for q in g if q != "?") if p.endswith("1")]
            if ok and n_vowels >= 2:
                poly += 1
                stress_ok += same_stress
            exact += ok and (n_vowels < 2 or same_stress)
            if not (ok and (n_vowels < 2 or same_stress)):
                errors[(w.lower(), " ".join(h), " ".join(g))] += 1
            edits += lev(plain(h), plain(g))
            phones += len(plain(g))
    print(f"{half}: {len(rows)} sentences, {n} German words ({english} tagged English skipped)")
    print(f"  words exact (sounds, and stress of polysyllables): {100 * exact / n:.1f}%")
    print(f"  words, sounds only (no glottal stops):            {100 * nogl / n:.1f}%")
    print(f"  words, sounds with glottal stops:                 {100 * withgl / n:.1f}%")
    print(f"  phoneme error rate (no glottal stops):            {100 * edits / phones:.2f}%")
    print(f"  stress agreement, polysyllables with same sounds: {100 * stress_ok / max(poly, 1):.1f}%")
    for (w, h, g), c in errors.most_common(n_errors):
        print(f"  {c:4d} {w:24s} vtts: {h:32s} espeak: {g}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("reference")
    a.add_argument("src", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--exclude", type=Path)
    b = sub.add_parser("compare")
    b.add_argument("ref", type=Path)
    b.add_argument("--half", choices=("dev", "test", "all"), default="test")
    b.add_argument("--errors", type=int, default=30)
    args = ap.parse_args()
    if args.cmd == "reference":
        reference(args.src, args.out, args.exclude)
    else:
        compare(args.ref, args.half, args.errors)


if __name__ == "__main__":
    main()
