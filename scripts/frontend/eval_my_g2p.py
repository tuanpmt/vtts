"""Agreement of the Burmese front-end with the IPA of English Wiktionary (measuring stick only).

Usage: uv run python scripts/frontend/eval_my_g2p.py WIKTIONARY.jsonl [--errors 30]

WIKTIONARY.jsonl is the Burmese dump of kaikki.org (https://kaikki.org/dictionary/Burmese/,
extracted from Wiktionary, CC BY-SA): it is read at evaluation time only and nothing from it is
kept in the repository. eSpeak NG's Burmese voice cannot serve as a reference (its rules read
most Burmese syllables as letter strings).

Every entry whose word is Burmese letters only and has a Wiktionary IPA is read by the front-end
(my/g2p_my.run_phones on the normalized word). Both readings are cut into the same units: onset
consonants, glides j w, the vowel, the tone (low, high, creaky; none for checked and reduced
syllables), the finals ɴ and ʔ. Reported: words read exactly, and the unit error rate
(Levenshtein over units / reference units), each also with voicing neutralized (Wiktionary writes
the voicing of compounds, ကောင်းကင် = kaʊ́ɴ gɪ̀ɴ, which the spelling rules do not predict) and
without tones. Wiktionary's /t͡ɕ t͡ɕʰ d͡ʑ/ are written k kʰ g + j by the front-end (as in Google's
analysis), /ɹ/ of loanwords is j.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

TONE = {"̀": "T1", "́": "T2", "̰": "T3"}
VOWELS = ("eɪ", "oʊ", "aɪ", "aʊ", "i", "u", "e", "o", "ɛ", "ɔ", "a", "ə", "ɪ", "ʊ")
CONS = ("t͡ɕʰ", "t͡ɕ", "d͡ʑ", "kʰ", "sʰ", "tʰ", "pʰ", "ŋ̊", "ɲ̊", "n̥", "m̥", "l̥", "k", "ɡ", "g", "ŋ",
        "s", "z", "ɲ", "t", "d", "n", "p", "b", "m", "j", "ɹ", "ʃ", "l", "w", "ʍ", "θ", "ð", "h",
        "ʔ", "f", "v")
# front-end phoneme names -> reference units
MINE = {"k": "k", "kh": "kʰ", "g": "g", "ng": "ŋ", "hng": "ŋ̊", "s": "s", "sh": "sʰ", "z": "z",
        "ny": "ɲ", "hny": "ɲ̊", "t": "t", "th": "tʰ", "d": "d", "n": "n", "hn": "n̥", "p": "p",
        "ph": "pʰ", "b": "b", "m": "m", "hm": "m̥", "y": "j", "S": "ʃ", "l": "l", "hl": "l̥",
        "w": "w", "hw": "ʍ", "T": "θ", "h": "h", "?": "ʔ", "G:y": "j", "G:w": "w",
        "I": "ɪ", "U": "ʊ", "E": "ɛ", "O": "ɔ", "@": "ə", "N": "ɴ", "ai": "aɪ", "au": "aʊ",
        "ou": "oʊ", "ei": "eɪ"}
VOICING = {"g": "k", "z": "s", "d": "t", "b": "p", "ð": "θ"}


def ref_units(ipa: str) -> list[str]:
    """Reference IPA -> units (onset consonants, vowel, tone, finals)."""
    s = unicodedata.normalize("NFD", ipa.strip("/[] ")).replace("ɡ", "g").replace(".", "")
    s = s.replace("t͡ɕʰ", "kʰj").replace("t͡ɕ", "kj").replace("d͡ʑ", "gj").replace("ɹ", "j")
    s = s.replace("ˑ", "").replace("ː", "")
    base, tones = "", []  # tone diacritics taken off the letters they sit on
    for ch in s:
        if ch in TONE:
            if tones:
                tones[-1] = TONE[ch]
        else:
            base += ch
            tones.append("")
    out: list[str] = []
    i = 0
    while i < len(base):
        v = next((x for x in VOWELS if base.startswith(x, i)), None)
        if v is not None:
            out.append(v)
            tone = next((t for t in tones[i:i + len(v)] if t), "")
            if tone:
                out.append(tone)
            i += len(v)
            continue
        if base.startswith("ɴ", i):
            out.append("ɴ")
            i += 1
            continue
        c = next((x for x in CONS if base.startswith(x, i)), None)
        if c is not None:
            out.append(c)
            i += len(c)
            continue
        i += 1  # stress marks, spaces, other diacritics
    return out


def my_units(phones: list[list[str]]) -> list[str]:
    out: list[str] = []
    for syl in phones:
        tone = next((p for p in syl if p in ("T1", "T2", "T3", "T4")), None)
        for p in syl:
            if p in ("T1", "T2", "T3", "T4"):
                continue
            u = MINE.get(p, p)
            out.append(u)
            if u in VOWELS and tone in ("T1", "T2", "T3"):
                out.append(tone)
    return out


def neutral(units: list[str], voicing: bool, tones: bool) -> list[str]:
    out = []
    for u in units:
        if tones and u in ("T1", "T2", "T3"):
            continue
        out.append(VOICING.get(u, u) if voicing else u)
    return out


def edits(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def main() -> None:
    from vtts.frontend.my.g2p_my import run_phones
    from vtts.frontend.my.normalize_my import is_burmese_word, normalize_my

    ap = argparse.ArgumentParser()
    ap.add_argument("wiktionary", type=Path)
    ap.add_argument("--errors", type=int, default=30)
    a = ap.parse_args()
    seen, rows = set(), []
    for line in a.wiktionary.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        w = d.get("word", "")
        ipas = [s["ipa"] for s in d.get("sounds", []) if "ipa" in s]
        if not ipas or w in seen or not re.fullmatch(r"[က-ဿ၌-၏]+", w):
            continue
        seen.add(w)
        norm = normalize_my(w)
        if not is_burmese_word(norm):
            continue
        rows.append((w, my_units(run_phones(norm)), [ref_units(i) for i in ipas]))
    print(f"{len(rows)} Wiktionary words with IPA")
    for name, voicing, tones in (("exact", False, False), ("voicing neutralized", True, False),
                                 ("voicing neutralized, no tones", True, True)):
        ok = err = tot = 0
        for _, mine, refs in rows:
            m = neutral(mine, voicing, tones)
            best = min((neutral(r, voicing, tones) for r in refs), key=lambda r: edits(m, r))
            ok += m == best
            err += edits(m, best)
            tot += len(best)
        print(f"  {name:31s}: words {100 * ok / len(rows):.1f}%, unit error rate {100 * err / tot:.1f}%")
    if a.errors:
        bad = [(w, m, r[0]) for w, m, r in rows
               if all(neutral(m, True, False) != neutral(x, True, False) for x in r)]
        for w, m, r in bad[:a.errors]:
            print(f"   {w}  front-end: {' '.join(m)}  wiktionary: {' '.join(r)}")


if __name__ == "__main__":
    main()
