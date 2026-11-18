"""Agreement of the Thai front-end with TLTK's g2p (PyThaiNLP's "tltk_g2p" engine).

TLTK is not a dependency of vtts (it pins old numpy/pandas); make the reference in its own
environment, then compare in the project environment:

  uv venv /tmp/tltk && uv pip install --python /tmp/tltk "tltk==1.11" "numpy<2" requests
  /tmp/tltk/bin/python scripts/frontend/eval_th_g2p.py reference SENTENCES.jsonl REF.jsonl
  uv run python scripts/frontend/eval_th_g2p.py compare REF.jsonl [--half test] [--errors 30]

SENTENCES.jsonl has id and text (e.g. from scripts/data/build_wiki_corpus.py --lang th).
Syllables are compared in TLTK's notation (initial + vowel + final + tone 0-4); long diphthongs
iia UUa uua are written ia Ua ua as in th-en. Rows are split by the parity of their position:
"dev" (even) was used to find words for lexicons/th/overrides.tsv, "test" (odd) was not.
Metrics: syllable error rate (Levenshtein over syllables / reference syllables) with and without
tones and vowel length, tone agreement on syllables whose sounds agree, sentences read exactly.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

VOWEL = {"ue": "U", "uue": "UU", "ae": "x", "aae": "xx", "or": "O", "oor": "OO", "oe": "@",
         "ooe": "@@", "uea": "Ua"}
REF_FIX = (("iia", "ia"), ("UUa", "Ua"), ("uua", "ua"))


def reference(src: Path, out: Path) -> None:
    """Reference syllables, and TLTK's units (Thai spelling, reading) to look up errors."""
    import tltk

    with out.open("w", encoding="utf-8") as f:
        for line in src.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            syls: list[str] = []
            units: list[tuple[str, str]] = []
            for part in tltk.nlp.g2p(r["text"]).split("<s/>"):
                if "<tr/>" not in part:
                    continue
                th, tr = part.split("<tr/>", 1)
                syls += [s for s in re.split(r"[~'|\s]+", tr) if s]
                units += zip(re.split(r"[~|]", th), re.split(r"[~|]", tr))
            f.write(json.dumps({"id": r["id"], "text": r["text"], "ref": syls, "units": units},
                               ensure_ascii=False) + "\n")


def hyp_syllables(text: str) -> list[str]:
    from vtts.frontend.text import text_to_tokens

    out: list[str] = []
    cur = ""
    for tok in (t for chunk in text_to_tokens(text, "th") for t in chunk):
        if not tok.startswith("TH:"):
            continue
        kind, _, val = tok[3:].partition(":")
        if kind.startswith("T") and not val:
            out.append(cur + str(int(kind[1:]) - 1))
            cur = ""
        elif kind == "V":
            cur += VOWEL.get(val, val)
        else:
            cur += "N" if val == "ng" else val
    return out


def norm_ref(s: str) -> str:
    for a, b in REF_FIX:
        s = s.replace(a, b)
    return s


def no_tone(s: str) -> str:
    return s.rstrip("01234")


def no_length(s: str) -> str:
    return re.sub(r"([aiUueoxO@])\1", r"\1", no_tone(s))


def align(ref: list[str], hyp: list[str]) -> tuple[int, list[tuple[str, str]]]:
    """Levenshtein distance and the substituted / matched pairs of one alignment."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    pairs, i, j = [], n, m
    while i and j:
        if d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            pairs.append((ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j] + 1:
            i -= 1
        else:
            j -= 1
    return d[n][m], pairs


def compare(ref_path: Path, half: str, n_errors: int) -> None:
    rows = [json.loads(x) for x in ref_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for k, r in enumerate(rows) if half == "all" or (k % 2 == (half == "test"))]
    tot = err = err_nt = err_nl = exact = 0
    tone_ok = tone_n = 0
    subs: Counter[str] = Counter()
    for r in rows:
        ref = [norm_ref(s) for s in r["ref"]]
        hyp = hyp_syllables(r["text"])
        e, pairs = align(ref, hyp)
        tot += len(ref)
        err += e
        err_nt += align([no_tone(s) for s in ref], [no_tone(s) for s in hyp])[0]
        err_nl += align([no_length(s) for s in ref], [no_length(s) for s in hyp])[0]
        exact += e == 0
        for a, b in pairs:
            if no_tone(a) == no_tone(b):
                tone_n += 1
                tone_ok += a == b
        subs.update(f"{a} -> {b}" for a, b in pairs if a != b)
    print(f"{len(rows)} sentences ({half}), {tot} reference syllables")
    print(f"syllable agreement: {1 - err / tot:.4f} (tones ignored {1 - err_nt / tot:.4f}, "
          f"tones and vowel length ignored {1 - err_nl / tot:.4f})")
    print(f"tone agreement on syllables with the same sounds: {tone_ok / tone_n:.4f} ({tone_n})")
    print(f"sentences read exactly: {exact / len(rows):.4f}")
    for k, c in subs.most_common(n_errors):
        print(c, k)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reference")
    r.add_argument("src", type=Path)
    r.add_argument("out", type=Path)
    c = sub.add_parser("compare")
    c.add_argument("ref", type=Path)
    c.add_argument("--half", choices=("dev", "test", "all"), default="test")
    c.add_argument("--errors", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "reference":
        reference(a.src, a.out)
    else:
        compare(a.ref, a.half, a.errors)


if __name__ == "__main__":
    main()
