"""Agreement of a Latin-script front-end's G2P with a reference, on held-out Wikipedia sentences.

References (measuring sticks only; nothing derived from them is shipped):
- ms: eSpeak NG (`espeak-ng -v ms --ipa`, GPL; run as an external program). eSpeak reduces final
  a to the schwa (colloquial Peninsular Malay); the front-end reads the standard a, so a word-final
  schwa of the reference is counted as a.
- sw: eSpeak NG (`espeak-ng -v sw --ipa`), as for ms.
- tl: the pronunciations of Wiktionary (CC BY-SA; read at evaluation time only, from a kaikki.org
  JSONL extract turned into a TSV of word and IPA variants with --kaikki). Only words with an
  IPA entry are scored; a word agrees when it matches any of the entry's variants; the
  word-initial glottal onset of the reference is ignored (the front-end does not write it).

  uv run python scripts/frontend/eval_g2p_reference.py --lang ms --sentences data/ms/sentences.jsonl
  uv run python scripts/frontend/eval_g2p_reference.py --kaikki kaikki-Tagalog.jsonl tl_ipa.tsv
  uv run python scripts/frontend/eval_g2p_reference.py --lang tl --sentences data/tl/sentences.jsonl \
      --ref tl_ipa.tsv

Words are the main-language words of the sentences after the front-end's tagging and
normalization (English words are left out). Rows are split by the parity of their position:
"dev" (even) was used to find words for the exception tables, "test" (odd) was not. Metrics, over
word tokens: words read exactly (without stress), phoneme error rate (Levenshtein over phonemes /
reference phonemes) and, where the reference marks stress, the stressed syllable agreement on
words whose phonemes agree. A final glide (pantai -> a y) is compared as the vowel (a i).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

DROP = "ˈˌːˑ‍̩͜͡.-"  # stress, length, tie bars, syllabic mark, dots
IPA = {  # IPA -> front-end phoneme, longest match first
    "ms": {"tʃ": "c", "dʒ": "j", "ʃ": "sy", "x": "kh", "ɣ": "gh", "ŋ": "ng", "ɲ": "ny", "ʔ": "?",
           "ə": "@", "ɛ": "e", "e": "e", "ɔ": "o", "o": "o", "a": "a", "i": "i", "ɪ": "i", "u": "u",
           "ʊ": "u", "j": "y", "w": "w", "ɡ": "g", "g": "g", "ɾr": "r", "r": "r", "ɾ": "r", "ɹ": "r",
           "θ": "th", "ð": "dh", **{c: c for c in "pbtdkfvszhmnl"}},
    "tl": {"tʃ": "ch", "ts": "ch", "dʒ": "j", "ʃ": "sh", "ŋ": "ng", "ɲ": "n y", "ʔ": "?", "ɛ": "e",
           "e": "e", "ɔ": "o", "o": "o", "a": "a", "ɐ": "a", "i": "i", "ɪ": "i", "u": "u", "ʊ": "u",
           "j": "y", "w": "w", "ɡ": "g", "g": "g", "ɾ": "r", "r": "r", "ɹ": "r",
           **{c: c for c in "pbtdkfvszhmnl"}},
    "sw": {"mb": "mb", "nd": "nd", "ŋɡ": "ngg", "ŋg": "ngg", "ɲɟ": "nj", "ndʒ": "nj", "tʃ": "ch",
           "dʒ": "j", "ɟ": "j", "ʃ": "sh", "θ": "th", "ð": "dh", "ɣ": "gh", "x": "kh", "ŋ": "ng",
           "ɲ": "ny", "ɛ": "e", "e": "e", "ɔ": "o", "o": "o", "a": "a", "ɑ": "a", "i": "i", "ɪ": "i",
           "u": "u", "ʊ": "u", "j": "y", "w": "w", "ɡ": "g", "g": "g", "r": "r", "ɾ": "r", "ɹ": "r",
           "ʔ": "", **{c: c for c in "pbtdkfvszhmnl"}},
}
# Allophones the front-end leaves to the voice: i/u lowered to e/o in a closed final syllable
# (untuk [untoʔ], masih [maseh]); reference vowels there are compared as the front-end's.
CLOSED_FINAL = {"ms": {"o": "u", "e": "i"}, "tl": {"o": "u", "e": "i"}}
VOWELS = frozenset("aiueo@")


def espeak(words: list[str], voice: str) -> list[str]:
    out = subprocess.run(["espeak-ng", "-v", voice, "-q", "--ipa=3"], input="\n".join(words) + "\n",
                         capture_output=True, text=True, check=True).stdout.splitlines()
    out = [o.strip() for o in out if o.strip()]
    if len(out) != len(words):
        raise RuntimeError(f"eSpeak returned {len(out)} lines for {len(words)} words")
    return out


def ipa_to_phonemes(ipa: str, lang: str, word: str = "") -> tuple[list[str], int | None]:
    """(phonemes, index of the stressed vowel among the vowels or None)."""
    table = IPA[lang]
    keys = sorted(table, key=len, reverse=True)
    out: list[str] = []
    stress_at = None
    ipa = "".join(ch for ch in ipa if ch == "ˈ" or not (ch in DROP or ch.isspace()))
    i = 0
    while i < len(ipa):
        if ipa[i] == "ˈ":
            stress_at = sum(p in VOWELS for p in out)  # the next vowel (approximately)
            i += 1
            continue
        k = next((k for k in keys if ipa.startswith(k, i)), None)
        if k is None:
            out.append("<" + ipa[i] + ">")
            i += 1
            continue
        out += table[k].split()
        i += len(k)
    if lang == "tl" and out[:1] == ["?"]:
        out = out[1:]
    if lang == "ms" and out and out[-1] == "@" and word.endswith("a"):
        out[-1] = "a"
    return out, stress_at


def closed_final(ref: list[str], hyp: list[str], lang: str) -> list[str]:
    """The reference with a lowered vowel of a closed final syllable read as the front-end's."""
    lower = CLOSED_FINAL.get(lang, {})
    rv = [k for k, p in enumerate(ref) if p in VOWELS]
    hv = [p for p in hyp if p in VOWELS]
    if rv and hv and rv[-1] + 1 < len(ref) and ref[rv[-1]] in lower and lower[ref[rv[-1]]] == hv[-1]:
        ref = ref[:rv[-1]] + [hv[-1]] + ref[rv[-1] + 1:]
    return ref


def hyp_phonemes(word: str, lang: str) -> tuple[list[str], int | None]:
    from importlib import import_module

    g2p = import_module(f"vtts.frontend.{lang}.g2p_{lang}")
    ph = list(g2p.phonemes(word))
    stress = next((sum(p.rstrip("1") in VOWELS for p in ph[:k]) for k, p in enumerate(ph) if p.endswith("1")), None)
    ph = [p.rstrip("1") for p in ph]
    if lang == "ms" and len(ph) >= 2 and ph[-2] in VOWELS and ph[-1] in ("y", "w"):
        ph[-1] = "i" if ph[-1] == "y" else "u"
    return ph, stress


def kaikki_tsv(src: Path, out: Path) -> None:
    """word<TAB>ipa|ipa... of the Standard Tagalog (or untagged) IPA of a kaikki.org extract."""
    best: dict[str, set[str]] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        w = e.get("word", "")
        if not w or " " in w:
            continue
        for snd in e.get("sounds", []):
            tags = snd.get("tags", [])
            ipa = snd.get("ipa", "")
            if ipa.startswith("/") and (not tags or "Standard-Tagalog" in tags):
                best.setdefault(w.lower(), set()).add(ipa.strip("/"))
    out.write_text("".join(f"{w}\t{'|'.join(sorted(v))}\n" for w, v in sorted(best.items())),
                   encoding="utf-8")


def words_of(text: str, lang: str) -> list[str]:
    from vtts.frontend.lang import runs, split_sentences_raw
    from vtts.frontend.languages import LANGUAGES

    out = []
    for s in split_sentences_raw(text):
        for run, code in runs(s, lang):
            if code == lang:
                out += [w for w in LANGUAGES[lang].normalize(run).split() if w[0].isalpha()]
    return out


def lev(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(IPA))
    ap.add_argument("--sentences", type=Path)
    ap.add_argument("--ref", type=Path, help="tl: word<TAB>ipa|ipa... (from --kaikki)")
    ap.add_argument("--kaikki", type=Path, nargs=2, metavar=("JSONL", "TSV"))
    ap.add_argument("--rows", type=int, default=2000, help="first N rows of the corpus")
    ap.add_argument("--half", choices=("dev", "test", "all"), default="test")
    ap.add_argument("--errors", type=int, default=30)
    a = ap.parse_args()
    if a.kaikki:
        kaikki_tsv(*a.kaikki)
        return
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines()[:a.rows]]
    rows = [r for k, r in enumerate(rows) if a.half == "all" or (k % 2 == 0) == (a.half == "dev")]
    tokens = Counter(w for r in rows for w in words_of(r["text"], a.lang))
    vocab = sorted(tokens)
    if a.ref:
        table = dict(x.split("\t") for x in a.ref.read_text(encoding="utf-8").splitlines())
        refs = {w: table[w].split("|") for w in vocab if w in table}
    else:
        refs = {w: [r] for w, r in zip(vocab, espeak(vocab, a.lang), strict=True)}
    covered = sum(c for w, c in tokens.items() if w in refs)
    n_words = exact = errs = ref_len = st_n = st_ok = 0
    bad: Counter = Counter()
    for w, c in tokens.items():
        if w not in refs:
            continue
        h, hs = hyp_phonemes(w, a.lang)
        cands = []
        for variant in refs[w]:
            r, rs = ipa_to_phonemes(variant, a.lang, w)
            r = closed_final(r, h, a.lang)
            cands.append((lev(h, r), rs != hs, r, rs))
        d, _, r, rs = min(cands, key=lambda x: x[:2])
        n_words += c
        exact += c * (d == 0)
        errs += c * d
        ref_len += c * len(r)
        multi = rs is not None and sum(p in VOWELS for p in r) > 1
        if d == 0 and multi:
            st_n += c
            st_ok += c * (rs == hs)
        if d or (multi and rs != hs):
            bad[(w, f"{' '.join(h)} [{hs}]", f"{' '.join(r)} [{rs}]")] += c
    print(f"{a.lang} {a.half}: {len(rows)} sentences, {sum(tokens.values())} words ({len(vocab)} distinct),"
          f" {100 * covered / sum(tokens.values()):.1f}% with a reference")
    print(f"words read exactly: {100 * exact / n_words:.1f}%  phoneme error rate: {100 * errs / ref_len:.1f}%"
          f"  stress agreement (same phonemes, 2+ syllables): {100 * st_ok / max(st_n, 1):.1f}%")
    for (w, h, r), c in bad.most_common(a.errors):
        print(f"{c:5d}  {w:20s} hyp {h:30s} ref {r}")


if __name__ == "__main__":
    main()
