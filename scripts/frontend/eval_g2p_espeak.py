"""Agreement of the Dutch, Swedish and Norwegian front-ends with eSpeak NG, used only as a
measuring stick (eSpeak NG is GPL: it is not a dependency of vtts and nothing derived from it is
shipped; install it with brew install espeak-ng / apt install espeak-ng).

  uv run python scripts/frontend/eval_g2p_espeak.py --lang nl SENTENCES.jsonl [--rows 2000]
      [--half test] [--errors 40] [--content]

SENTENCES.jsonl has id and text (plain Wikipedia sentences, data/<lang>/sentences.jsonl from
scripts/data/build_wiki_corpus.py). The first --rows rows are used and split by the parity of
their position: "dev" (even) was used to find rules and exceptions, "test" (odd) was not. Every
word the front-end tags as the main language is read in isolation by eSpeak (voice nl, sv or nb)
and by the front-end's g2p; both are mapped to one notation (MAPS below: eSpeak's symbols to the
token names, retroflex consonants and tones are not compared since eSpeak's Swedish and
Norwegian voices do not mark them consistently). Metrics over word tokens: words read the same
(sounds, and the stressed vowel of words of two or more syllables), the same sounds, phoneme error
rate (Levenshtein over phonemes), stress agreement on polysyllables whose sounds agree.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

VOICE = {"nl": "nl", "sv": "sv", "no": "nb"}
# eSpeak -x symbols -> token names (after splitting on --sep=' ').
MAPS = {
    "nl": {"I:": "e:", "Wy": "9y", "EI": "Ei", "VU": "Au", "Y:": "2:", "8": "Y", "v#": "w", "Q": "x", "G": "x",
           "_!": "", "_|": "", "_": "", "o:": "o:", "e:": "e:", "a:": "a:", "i:": "i", "u:": "u",
           "y:": "y", "E:": "E", "O:": "o:", "9y": "9y", "EU": "Ei", "@-": "@", "I2": "I", "&": "E",
           "A:": "a:", "Y": "Y", "u": "u", "y": "y", "J": "n j", "c": "t j", "g": "x", "W": "2:",
           "R": "r", "r": "r", "l": "l", "dZ": "d j", "tS": "t j", "ts": "t s"},
    "sv": {"u-": "}", "u-:": "}:", "8": "8", "}": "8", "y": "Y", "Y:": "2:", "W": "9", "W:": "2:", "E-": "@", "sx": "S",
           "S;": "C", "R": "r", "k:": "k", "s.": "s", "t.": "t", "d.": "d", "n.": "n", "l.": "l",
           "_!": "", "_|": "", "_": "", "A:": "A:", "U": "U", "u:": "u:", "E2": "E", "e": "e",
           "@": "@", "I": "I", "i:": "i:", "a": "a", "E": "E", "E:": "E:", "o:": "o:", "O": "O",
           "y:": "y:", "Y": "Y", "e:": "e:", "&": "{", "&:": "{:", "a:": "A:"},
    "no": {"a#": "@", "x": "C", "U:": "u:", "u-": "}", "u-:": "}:", "Y:": "2:", "W": "9", "W:": "2:", "@": "@", "S;": "C", "C": "C",
           "R": "r", "s.": "s", "t.": "t", "d.": "d", "n.": "n", "l.": "l", "r.": "r", "_!": "",
           "_|": "", "_": "", "A:": "A:", "A": "A", "&": "{", "&:": "{:", "&I": "{I", "{I": "{I",
           "9Y": "9Y", "WY": "9Y", "&U": "{}", "VU": "{}", "Au": "{}", "a": "A", "a:": "A:", "aI": "Ai",
           "E": "E", "e:": "e:", "I": "I", "i:": "i:", "O": "O", "o:": "o:", "U": "U", "u:": "u:",
           "y:": "y:", "Y": "Y", "EI": "{I", "OY": "9Y", "e": "E"},
}
# Retroflex tokens compared as the plain consonant; an r before t d n s l is dropped on both sides.
RETRO = {"t`": "t", "d`": "d", "n`": "n", "s`": "s", "l`": "l"}
TONES = ("'1", "'2", ",")
LANG = ["nl"]
# Words eSpeak reads in isolation as another word (the numeral één for the article een).
SKIP = {"nl": ("een",)}
WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def espeak_words(words: list[str], lang: str) -> list[str]:
    exe = shutil.which("espeak-ng") or "/opt/homebrew/bin/espeak-ng"
    out: list[str] = []
    for k in range(0, len(words), 2000):
        chunk = words[k:k + 2000]
        res = subprocess.run([exe, "-v", VOICE[lang], "-q", "-x", "--sep= "], input="\n".join(chunk) + "\n",
                             capture_output=True, text=True, check=True).stdout.splitlines()
        res = [x.strip() for x in res if x.strip()]
        if len(res) != len(chunk):
            raise RuntimeError(f"eSpeak returned {len(res)} lines for {len(chunk)} words")
        out += res
    return out


def _vowels(lang: str) -> set[str]:
    from vtts.frontend import phoneme_set

    up = lang.upper() + ":"
    toks = phoneme_set.TOKEN_SETS[phoneme_set.PAIR_MODES[lang]]
    return {t[len(up):] for t in toks if t.startswith(up) and t[len(up):][:1] in "AEIOUY@9}{2aeiouy8"
            and t[len(up):] not in TONES}


def norm_espeak(s: str, lang: str, vowels: set[str]) -> tuple[list[str], int | None]:
    """eSpeak phonemes -> (phonemes, index of the primary-stressed vowel or None)."""
    out: list[str] = []
    stress = None
    pending = False
    for t in s.split():
        if t.startswith("'"):
            pending, t = True, t[1:]
        elif t.startswith(","):
            t = t[1:]
        t = t.replace("'", "").replace(",", "")
        if len(t) == 2 and t[1] == ":" and t[0] in "bdfghjklmnprstv":  # a long consonant
            t = t[0]
        if not t:
            continue
        for p in MAPS[lang].get(t, t).split():
            if pending and p in vowels:
                stress, pending = len(out), False
            out.append(p)
    if lang == "no":  # eSpeak writes rs as r S
        k = 0
        while k + 1 < len(out):
            if out[k] == "r" and out[k + 1] == "S":
                out[k:k + 2] = ["s`"]
                if stress is not None and stress > k:
                    stress -= 1
            k += 1
    return _plain(out), stress if stress is None else _plain_index(out, stress)


def norm_ours(ph: tuple[str, ...]) -> tuple[list[str], int | None]:
    out: list[str] = []
    stress = None
    for p in ph:
        if p in TONES:
            if out and stress is None:
                stress = len(out) - 1
            continue
        if p.endswith("1") and len(p) > 1:
            stress = len(out)
            p = p[:-1]
        out.append(p)
    return _plain(out), stress if stress is None else _plain_index(out, stress)


def _keep(ph: list[str], k: int) -> bool:
    return not (ph[k] == "r" and k + 1 < len(ph) and RETRO.get(ph[k + 1], ph[k + 1]) in ("t", "d", "n", "s", "l")
                and (ph[k + 1] in RETRO or True))


# sv, no: the short e and ä are one vowel in eSpeak (and the schwa of a final -e is E there).
MERGE = {"sv": {"e": "E", "@": "E", "{:": "E:", "{": "E", "9:": "2:"}, "no": {"@": "E"}}


def _plain(ph: list[str]) -> list[str]:
    out = [RETRO.get(p, p) for k, p in enumerate(ph) if LANG[0] == "nl" or _keep(ph, k)]
    out = [MERGE.get(LANG[0], {}).get(p, p) for p in out]
    merged: list[str] = []
    for p in out:  # geminates and s j -> S (nl)
        if merged and p == merged[-1]:
            continue
        merged.append(p)
    return merged


def _plain_index(ph: list[str], k: int) -> int:
    return len(_plain(ph[:k]))


def lev(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def main() -> None:
    from vtts.frontend.lang import word_lang

    ap = argparse.ArgumentParser()
    ap.add_argument("sentences", type=Path)
    ap.add_argument("--lang", required=True, choices=sorted(VOICE))
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--half", choices=("dev", "test", "all"), default="test")
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--content", action="store_true",
                    help="leave out function words and words of the override table (spoken forms that eSpeak "
                         "reads as written)")
    a = ap.parse_args()
    LANG[0] = a.lang
    g2p = importlib.import_module(f"vtts.frontend.{a.lang}.g2p_{a.lang}")
    skip = set(SKIP.get(a.lang, ()))
    if a.content:
        skip |= set(g2p.override_table())
        skip |= set(g2p.RULES.function_words if hasattr(g2p, "RULES") else g2p.FUNCTION_WORDS)
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines()[:a.rows]]
    words: list[str] = []
    for k, r in enumerate(rows):
        if a.half != "all" and (k % 2 == 0) != (a.half == "dev"):
            continue
        for m in WORD.finditer(r["text"]):
            for w in m.group(0).split("-"):
                if word_lang(w, a.lang) == a.lang and w.lower() not in skip:
                    words.append(w.lower())
    uniq = sorted(set(words))
    ref = dict(zip(uniq, espeak_words(uniq, a.lang)))
    vowels = _vowels(a.lang)
    n = same = sounds = stress_n = stress_ok = 0
    edits = total = 0
    errs: Counter = Counter()
    for w in words:
        ours, s1 = norm_ours(g2p.phonemes(w))
        theirs, s2 = norm_espeak(ref[w], a.lang, vowels)
        n += 1
        d = lev(ours, theirs)
        edits += d
        total += len(theirs)
        poly = sum(p in vowels for p in theirs) >= 2
        if d == 0:
            sounds += 1
            if poly:
                stress_n += 1
                stress_ok += s1 == s2
            if not poly or s1 == s2:
                same += 1
                continue
        errs[(w, " ".join(ours), " ".join(theirs))] += 1
    print(f"{a.lang} {a.half}: {n} word tokens ({len(uniq)} types) from {len(rows)} rows")
    print(f"  same reading (sounds + stress of polysyllables): {100 * same / n:.1f}%")
    print(f"  same sounds: {100 * sounds / n:.1f}%")
    print(f"  phoneme error rate: {100 * edits / max(total, 1):.1f}%")
    print(f"  stress agreement (polysyllables, same sounds): {100 * stress_ok / max(stress_n, 1):.1f}%")
    for (w, o, t), c in errs.most_common(a.errors):
        print(f"{c:4d} {w:20s} ours: {o:30s} espeak: {t}")


if __name__ == "__main__":
    main()
