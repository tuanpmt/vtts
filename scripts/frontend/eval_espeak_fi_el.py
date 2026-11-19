"""Agreement of the Finnish and Greek front-ends with eSpeak NG (a measuring stick only).

eSpeak NG (GPL) is not a dependency and nothing derived from it is included; it must be installed
on the host (`brew install espeak-ng`, `apt install espeak-ng`).

  uv run python scripts/frontend/eval_espeak_fi_el.py --lang fi SENTENCES.jsonl [--n 1000] \
      [--errors 40]

SENTENCES.jsonl has a "text" field (e.g. the held-out tail of data/<lang>/sentences.jsonl from
scripts/data/build_wiki_corpus.py). Words the tagger reads in the main language are compared one by
one: each word is phonemized by eSpeak on its own (as its own clause, so no sandhi between words)
and by the front-end. eSpeak's IPA is mapped to the token names (Finnish: ɪ i, æ ae, ø oe, ŋ ng,
ʃ sh, ʒ zh, ː and a doubled sound = the length mark ":"; Greek: θ th, ð dh, ɣ gh, ç x, c k, ɟ g,
ɲ n j, ʎ l j, ŋ ng, ts dz). eSpeak writes ʝ (γ before e i) and the glide alike as j and the
palatal k x g without a glide, so for Greek both sides are reduced: gh before e i j -> j, a j
after k g x or j is dropped. Stress marks are compared separately.

One-letter words are skipped (eSpeak reads a lone letter by its name).

Metrics: phoneme error rate (Levenshtein over phonemes / reference phonemes), words read exactly
(phonemes), and words whose stressed vowel is the same (among words of two or more syllables with
the same phonemes; eSpeak stresses every word read alone, the front-ends leave short function words
unstressed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

FI_IPA = {"ɪ": "i", "æ": "ae", "ø": "oe", "ŋ": "ng", "ʃ": "sh", "ʒ": "zh", "ɡ": "g", "q": "k"}
EL_IPA = {"θ": "th", "ð": "dh", "ɣ": "gh", "ʝ": "j", "ç": "x", "c": "k", "ɟ": "g", "ɲ": "n j",
          "ʎ": "l j", "ŋ": "ng", "ɱ": "m", "ɾ": "r", "ɡ": "g", "dz": "dz", "ts": "ts", "ɪ": "i",
          "ɐ": "a", "ɛ": "e", "ɔ": "o"}
VOWELS = {"fi": {"a", "e", "i", "o", "u", "y", "ae", "oe"}, "el": {"a", "e", "i", "o", "u"}}


def espeak_words(words: list[str], lang: str) -> list[str]:
    """IPA of each word, one clause per word."""
    out = subprocess.run(["espeak-ng", "-v", lang, "-q", "--ipa", "--stdin"],
                         input="\n".join(w + " ." for w in words), capture_output=True, text=True,
                         check=True).stdout
    lines = [x.strip() for x in out.splitlines() if x.strip()]
    return lines if len(lines) == len(words) else []


def ipa_to_tokens(ipa: str, lang: str) -> tuple[list[str], int | None]:
    """(phonemes without stress, ordinal of the first primary-stressed vowel or None)."""
    table = FI_IPA if lang == "fi" else EL_IPA
    ipa = unicodedata.normalize("NFC", ipa).replace("\u0361", "").replace(" ", "")
    out: list[str] = []
    stress_next, stressed, vowels = False, None, 0
    i = 0
    while i < len(ipa):
        ch = ipa[i]
        if ch == "ˈ":
            stress_next = True
            i += 1
            continue
        if ch == "ˌ":
            i += 1
            continue
        if ch == "ː":
            out.append(":")
            i += 1
            continue
        two = ipa[i:i + 2]
        if two in table:
            toks, i = table[two].split(), i + 2
        elif lang == "el" and ch == "ç":  # ç before a back vowel after a consonant: the glide
            nxt = ipa[i + 1:].lstrip("ˈˌ")[:1]
            glide = nxt not in ("e", "i", "ɪ") and out and out[-1] not in VOWELS[lang]
            toks, i = ["j" if glide else "x"], i + 1
        else:
            toks, i = table.get(ch, ch).split(), i + 1
        for t in toks:
            if out and out[-1] == t and t not in VOWELS[lang]:
                if lang == "fi":
                    out.append(":")  # doubled consonant = long
                continue  # el: eSpeak keeps doubled letters (γλώσσα); Greek has no long consonants
            if lang == "fi" and out and out[-1] == t:
                out.append(":")
                continue
            if t in VOWELS[lang]:
                if stress_next and stressed is None:
                    stressed = vowels
                stress_next = False
                vowels += 1
            out.append(t)
    return out, stressed


def reduce_el(ph: list[str]) -> list[str]:
    out: list[str] = []
    for k, p in enumerate(ph):
        nxt = ph[k + 1] if k + 1 < len(ph) else ""
        if p == "gh" and nxt in ("e", "i", "j"):
            p = "j"
        if p == "j" and out and out[-1] in ("k", "g", "x", "j"):
            continue
        out.append(p)
    return out


def ours(word: str, lang: str) -> tuple[list[str], set[int]]:
    """(phonemes without stress, ordinals of the stressed vowels)."""
    from vtts.frontend.languages import LANGUAGES

    toks = [t.split(":", 1)[1] for t in LANGUAGES[lang].word_tokens(word)]
    phones, stressed, v = [], set(), 0
    for t in toks:
        base = t.removesuffix("1")
        if base in VOWELS[lang]:
            if t.endswith("1"):
                stressed.add(v)
            v += 1
        phones.append(base)
    return phones, stressed


def _edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def main() -> None:
    from vtts.frontend.lang import split_sentences_raw, tag_words
    from vtts.frontend.languages import LANGUAGES

    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=("fi", "el"))
    ap.add_argument("sentences", type=Path)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--errors", type=int, default=40)
    a = ap.parse_args()
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines() if x]
    words: list[str] = []
    for r in rows[-a.n:]:
        for s in split_sentences_raw(r["text"], a.lang):
            for chunk, tag in tag_words(s, a.lang):
                if tag != a.lang:
                    continue
                words += [w for w in LANGUAGES[a.lang].normalize(chunk).split()
                          if w.isalpha() and len(w) > 1]  # eSpeak spells a lone letter
    errs = total = exact = n = stress_same = stress_n = 0
    wrong: Counter = Counter()
    bad_stress: Counter = Counter()
    for k in range(0, len(words), 200):
        batch = words[k:k + 200]
        ipas = espeak_words(batch, a.lang)
        for w, ipa in zip(batch, ipas, strict=False):
            ref, ref_stress = ipa_to_tokens(ipa, a.lang)
            hyp, hyp_stress = ours(w, a.lang)
            if a.lang == "el":  # the reduction keeps the vowels (stress ordinals stay valid)
                ref, hyp = reduce_el(ref), reduce_el(hyp)
            e = _edits(ref, hyp)
            errs, total, n = errs + e, total + len(ref), n + 1
            exact += e == 0
            if e:
                wrong[(w, " ".join(ref), " ".join(hyp))] += 1
            elif ref_stress is not None and sum(t in VOWELS[a.lang] for t in ref) >= 2:
                stress_n += 1
                stress_same += ref_stress in hyp_stress
                if ref_stress not in hyp_stress:
                    bad_stress[(w, ipa)] += 1
    print(f"{a.lang}: {n} words ({len(set(words))} distinct) from {min(a.n, len(rows))} sentences")
    print(f"phoneme error rate {100 * errs / max(total, 1):.2f}% "
          f"(agreement {100 - 100 * errs / max(total, 1):.2f}%), words exact {100 * exact / max(n, 1):.2f}%, "
          f"stress agreement {100 * stress_same / max(stress_n, 1):.2f}% of {stress_n} words of 2+ syllables")
    for (w, ref, hyp), c in wrong.most_common(a.errors):
        print(f"{c:4d}  {w:24s} espeak: {ref:32s} ours: {hyp}")
    for (w, ipa), c in bad_stress.most_common(a.errors // 2):
        print(f"{c:4d}  stress {w:24s} espeak: {ipa}")


if __name__ == "__main__":
    main()
