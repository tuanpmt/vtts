"""Agreement of a Latin-script front-end (it, tr) with eSpeak NG, word by word.

eSpeak NG (GPL) is only a measuring stick: it is called as an external program at evaluation
time and nothing derived from it is part of vtts. Install it separately (brew install espeak-ng,
apt install espeak-ng).

  uv run python scripts/frontend/eval_latin_g2p.py --lang it SENTENCES.jsonl [--half test]
      [--rows 2400] [--errors 40]

SENTENCES.jsonl has id and text (e.g. data/it/sentences.jsonl from build_wiki_corpus.py). Rows
are split by the parity of their position among the first --rows: "dev" (even) was used to find
words for lexicons/<lang>/overrides.tsv, "test" (odd) was not. The words of each sentence that
the tagger gives to the main language are normalized, read by the front-end and by eSpeak NG
(one word per line), and both readings are mapped to a common phoneme notation (IPA-like, stress
kept apart; a glide j/w counts as the vowel i/u, since the references differ in hiatus).
Metrics over word tokens: phonemes (1 - edit distance / reference length), words read exactly
(phonemes, and stress where both readings have one: vtts leaves function words unstressed),
words with the same phonemes, stress position on words of two or more vowels whose vowel count
agrees (both stressed), and (it) the open/closed quality of a stressed e/o read at the same place.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

# front-end phoneme (without the language prefix and stress digit) -> common symbol
OURS = {
    "it": {"E": "ɛ", "O": "ɔ", "ch": "tʃ", "dj": "dʒ", "sh": "ʃ", "ny": "ɲ", "ly": "ʎ", "ts": "ts",
           "dz": "dz"},
    "tr": {"I": "ɯ", "oe": "ø", "ue": "y", "ch": "tʃ", "c": "dʒ", "sh": "ʃ", "zh": "ʒ", "y": "j",
           "long": "ː"},
}
# eSpeak IPA -> common symbol (longest first); "" drops the symbol
ESPEAK = {
    "it": {"tʃ": "tʃ", "dʒ": "dʒ", "ts": "ts", "dz": "dz", "ɡ": "g", "ɪ": "i", "ʊ": "u", "ɾ": "r", "ŋ": "n",
           "ɱ": "m", "ɐ": "a", "ə": "e", "æ": "e", "ɑ": "a"},
    "tr": {"tʃ": "tʃ", "dʒ": "dʒ", "ɡ": "g", "ɪ": "i", "ʊ": "u", "ɾ": "r", "ɛ": "e", "æ": "e", "ɔ": "o",
           "œ": "ø", "ø": "y", "ʏ": "y", "ɟ": "g", "c": "k", "ɫ": "l", "ʎ": "l", "ŋ": "n", "ɣ": "", "ɑ": "a",
           "ɱ": "m", "ɒ": "o", "ʋ": "v", "ɦ": "h", "ɨ": "ɯ", "ʔ": ""},
}
VOWELS = {"it": "aeiouɛɔ", "tr": "aeiouɯøy"}


GLIDES = {"j": "i", "w": "u"}  # glide or vowel i/u: the references differ in hiatus, not compared


def ours(lang: str, tokens: list[str]) -> tuple[list[str], int | None]:
    """(symbols, index of the stressed vowel among the vowels or None)."""
    syms, stress, nv = [], None, 0
    for t in tokens:
        p = t.split(":", 1)[1]
        stressed = p.endswith("1") and p != "1"
        p = p[:-1] if stressed else p
        s = OURS[lang].get(p, p) if lang != "it" else GLIDES.get(p, OURS[lang].get(p, p))
        if lang == "tr" and s == "ː":  # Turkish: a long vowel is the vowel symbol + ː
            if syms:
                syms[-1] += "ː"
            continue
        if s[0] in VOWELS[lang]:
            if stressed:
                stress = nv
            nv += 1
        syms.append(s)
    return syms, stress


def espeak(lang: str, ipa: str) -> tuple[list[str], int | None]:
    table = ESPEAK[lang]
    keys = sorted(table, key=len, reverse=True)
    syms: list[str] = []
    stress, nv, pending = None, 0, False
    i = 0
    ipa = ipa.replace("ˌ", "").replace("-", "").replace(" ", "")
    while i < len(ipa):
        if ipa[i] == "ˈ":
            pending = True
            i += 1
            continue
        if ipa[i] == "ː":
            if syms and syms[-1][0] not in VOWELS[lang]:
                syms.append(syms[-1])  # geminate consonant
            elif syms and lang == "tr":
                syms[-1] += "ː"
            i += 1
            continue
        k = next((k for k in keys if ipa.startswith(k, i)), None)
        s = table[k] if k else ipa[i]
        s = GLIDES.get(s, s) if lang == "it" else s
        i += len(k) if k else 1
        if not s:
            continue
        if s[0] in VOWELS[lang]:
            if pending:
                stress = nv
                pending = False
            nv += 1
        syms.append(s)
    return syms, stress


def edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def run_espeak(lang: str, words: list[str]) -> list[str]:
    text = "".join(f"{w}.\n" for w in words)
    out = subprocess.run(["espeak-ng", "-q", "--ipa", "-v", lang], input=text, capture_output=True,
                         text=True, check=True).stdout
    lines = [x.strip() for x in out.splitlines() if x.strip()]
    if len(lines) != len(words):
        raise RuntimeError(f"eSpeak returned {len(lines)} lines for {len(words)} words")
    return lines


def main() -> None:
    from vtts.frontend.lang import runs, split_sentences_raw
    from vtts.frontend.languages import LANGUAGES
    from vtts.frontend.phoneme_set import PUNCTUATION

    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=sorted(OURS))
    ap.add_argument("sentences", type=Path)
    ap.add_argument("--half", choices=("dev", "test", "all"), default="test")
    ap.add_argument("--rows", type=int, default=2400)
    ap.add_argument("--errors", type=int, default=40)
    a = ap.parse_args()
    lang, module = a.lang, LANGUAGES[a.lang]
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines()[:a.rows]]
    rows = [r for k, r in enumerate(rows) if a.half == "all" or (k % 2 == 0) == (a.half == "dev")]
    words: list[str] = []
    for r in rows:
        for s in split_sentences_raw(r["text"], lang):
            for run, code in runs(s, lang):
                if code == lang:
                    words += [w for w in module.normalize(run).split() if w not in PUNCTUATION]
    uniq = sorted(set(words))
    ref = dict(zip(uniq, run_espeak(lang, uniq)))
    n_words = exact = same_ph = ph_err = ph_len = 0
    st_n = st_ok = q_n = q_ok = 0
    errors: Counter = Counter()
    for w in words:
        hs, hst = ours(lang, module.word_tokens(w))
        rs, rst = espeak(lang, ref[w])
        n_words += 1
        e = edits(rs, hs)
        ph_err += e
        ph_len += len(rs)
        nvh = sum(s[0] in VOWELS[lang] for s in hs)
        nvr = sum(s[0] in VOWELS[lang] for s in rs)
        same_ph += e == 0
        stress_ok = hst == rst or nvr < 2 or hst is None or rst is None
        exact += e == 0 and stress_ok
        if nvr >= 2 and nvh == nvr and rst is not None and hst is not None:
            st_n += 1
            st_ok += hst == rst
        if lang == "it" and hst is not None and hst == rst:
            hv = [s for s in hs if s[0] in VOWELS[lang]][hst]
            rv = [s for s in rs if s[0] in VOWELS[lang]][rst]
            if {hv, rv} <= set("eɛoɔ") and (hv in "eɛ") == (rv in "eɛ"):
                q_n += 1
                q_ok += hv == rv
        if not (e == 0 and stress_ok):
            errors[(w, " ".join(hs) + f" /{hst}", " ".join(rs) + f" /{rst}")] += 1
    print(f"{lang} {a.half}: {len(rows)} sentences, {n_words} words ({len(uniq)} distinct)")
    print(f"phonemes {100 * (1 - ph_err / ph_len):.1f}%  words exact {100 * exact / n_words:.1f}%  "
          f"same phonemes {100 * same_ph / n_words:.1f}%  stress {100 * st_ok / max(st_n, 1):.1f}% "
          f"of {st_n}" + (f"  e/o quality {100 * q_ok / max(q_n, 1):.1f}% of {q_n}" if q_n else ""))
    for (w, h, r), c in errors.most_common(a.errors):
        print(f"{c:4d}  {w:20s} ours {h:32s} espeak {r}")


if __name__ == "__main__":
    main()
