"""Agreement of the French front-end with eSpeak NG (a measuring stick only: eSpeak NG is GPL and is
neither a dependency nor a source of any table).

  espeak-ng must be on PATH (brew install espeak-ng / apt install espeak-ng).
  uv run python scripts/frontend/eval_fr_g2p.py reference SENTENCES.jsonl REF.jsonl [--limit 2000]
  uv run python scripts/frontend/eval_fr_g2p.py compare REF.jsonl [--half test] [--errors 30]

SENTENCES.jsonl has id and text (e.g. data/fr/sentences.jsonl from build_wiki_corpus.py --lang fr).
The reference keeps eSpeak's reading of each sentence (with its liaisons) and of each word on its own.
Rows are split by the parity of their position: "dev" (even) was used to find words for the
lexicons/fr tables, "test" (odd) was not. Sentences where eSpeak switches language or the front-end
tags a word as English are left out.

Metrics: phoneme error rate (Levenshtein over phonemes / reference phonemes) of whole sentences
(liaison, elision and e muet included), strict and with the mid vowels merged (e=E, o=O, eu=oe: the
open/closed choice varies between speakers and dictionaries); word accuracy on the words of the
sentences read one by one (token-weighted), strict and merged.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

IPA = (("ɑ̃", "an"), ("ɔ̃", "on"), ("ɛ̃", "in"), ("œ̃", "un"), ("ɛ", "E"), ("ɔ", "O"), ("ø", "eu"),
       ("œ", "oe"), ("ə", "@"), ("ɑ", "a"), ("ɥ", "H"), ("ʃ", "sh"), ("ʒ", "zh"), ("ɲ", "gn"),
       ("ŋ", "ng"), ("ʁ", "r"), ("ɡ", "g"), ("r", "r"))
VOWELS = {"i", "e", "E", "a", "O", "o", "u", "y", "eu", "oe", "@", "an", "on", "in", "un"}
MERGE = {"E": "e", "O": "o", "oe": "eu"}


def espeak(text: str) -> str:
    return subprocess.run(["espeak-ng", "-v", "fr", "-q", "--ipa", text], capture_output=True,
                          text=True, check=True).stdout


def ipa_phonemes(ipa: str) -> list[str] | None:
    """eSpeak IPA -> fr-en phonemes; None when eSpeak switched language."""
    if "(" in ipa:
        return None
    s = re.sub(r"[ˈˌː\-‿_\s]", "", ipa)
    table = dict(IPA)
    out: list[str] = []
    k = 0
    while k < len(s):
        if s[k:k + 2] in table:  # nasal vowels: vowel + combining tilde
            out.append(table[s[k:k + 2]])
            k += 2
            continue
        out.append(table.get(s[k], s[k]))
        k += 1
    # eSpeak writes the glide ɥ as y before a vowel (nuit -> nyi)
    return ["H" if p == "y" and k + 1 < len(out) and out[k + 1] in VOWELS else p
            for k, p in enumerate(out)]


def reference(src: Path, out: Path, limit: int) -> None:
    from vtts.frontend.fr.normalize_fr import normalize_fr

    rows = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x][:limit]
    words = Counter()
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            ref = ipa_phonemes(espeak(r["text"]))
            plain = [w for w in normalize_fr(r["text"]).split() if w not in ",.?!;:"]
            words.update(w.split("'")[-1] if "'" in w.rstrip("'") and len(w.split("'")[0]) == 1
                         else w for w in plain)
            f.write(json.dumps({"id": r["id"], "text": r["text"], "ref": ref},
                               ensure_ascii=False) + "\n")
    wref = {w: ipa_phonemes(espeak(w)) for w in words}
    out.with_suffix(".words.json").write_text(json.dumps(wref, ensure_ascii=False), encoding="utf-8")


def hyp_phonemes(text: str) -> list[str] | None:
    from vtts.frontend.text import text_to_tokens

    toks = [t for chunk in text_to_tokens(text, "fr") for t in chunk]
    if any(t.startswith("EN:") for t in toks):
        return None
    return notation([t[3:] for t in toks if t.startswith("FR:")])


def notation(ph: list[str]) -> list[str]:
    """ɲ as n j: eSpeak NG writes it either way (montagne -> m on t a n j in sentences)."""
    return [x for p in ph for x in (("n", "j") if p == "gn" else (p,))]


def edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def merged(ph: list[str]) -> list[str]:
    return [MERGE.get(p, p) for p in ph]


def compare(ref_path: Path, half: str, n_errors: int) -> None:
    from vtts.frontend.fr.g2p_fr import phonemes

    rows = [json.loads(x) for x in ref_path.read_text(encoding="utf-8").splitlines() if x]
    rows = [r for k, r in enumerate(rows) if half == "all" or (k % 2 == 0) == (half == "dev")]
    n = e_strict = e_merged = exact = used = skipped = 0
    worst = []
    words = Counter()
    for r in rows:
        hyp = hyp_phonemes(r["text"])
        if r["ref"] is None or hyp is None:
            skipped += 1
            continue
        used += 1
        ref = notation(r["ref"])
        n += len(ref)
        d = edits(hyp, ref)
        e_strict += d
        e_merged += edits(merged(hyp), merged(ref))
        exact += d == 0
        worst.append((d / max(len(ref), 1), r["text"], " ".join(hyp), " ".join(ref)))
        from vtts.frontend.fr.normalize_fr import normalize_fr

        for w in normalize_fr(r["text"]).split():
            if w not in ",.?!;:":
                words[w.split("'")[-1] if "'" in w.rstrip("'") and len(w.split("'")[0]) == 1
                      else w] += 1
    wref = json.loads(ref_path.with_suffix(".words.json").read_text(encoding="utf-8"))
    tot = ok = ok_m = 0
    bad = Counter()
    for w, c in words.items():
        ref = wref.get(w)
        if ref is None:
            continue
        hyp, ref = notation(list(phonemes(w))), notation(ref)
        tot += c
        ok += c * (hyp == ref)
        ok_m += c * (merged(hyp) == merged(ref))
        if merged(hyp) != merged(ref):
            bad[(w, " ".join(hyp), " ".join(ref))] += c
    print(f"{half}: {used} sentences ({skipped} skipped: English words or eSpeak language switch)")
    print(f"sentence PER strict {100 * e_strict / n:.2f}%  merged mid vowels "
          f"{100 * e_merged / n:.2f}%  exact sentences {100 * exact / max(used, 1):.1f}%")
    print(f"word accuracy (token-weighted, {tot} tokens) strict {100 * ok / tot:.2f}%  "
          f"merged {100 * ok_m / tot:.2f}%")
    for (w, h, r), c in bad.most_common(n_errors):
        print(f"  {c:5d} {w:18} {h:28} | {r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("reference")
    a.add_argument("src", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--limit", type=int, default=2000)
    b = sub.add_parser("compare")
    b.add_argument("ref", type=Path)
    b.add_argument("--half", choices=("dev", "test", "all"), default="test")
    b.add_argument("--errors", type=int, default=30)
    args = ap.parse_args()
    if args.cmd == "reference":
        reference(args.src, args.out, args.limit)
    else:
        compare(args.ref, args.half, args.errors)


if __name__ == "__main__":
    main()
