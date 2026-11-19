"""Spelling rules shared by the Swedish and Norwegian (Bokmål, Urban East Norwegian) front-ends:
graphemes, stress, the two word tones, vowel length and retroflex consonants. Each language gives
a Rules table (sv/g2p_sv.py, no/g2p_no.py); the C port (runtime/src/vtts_text_nx.c) follows this
module step by step.

A word (lower case) is read in this order:

1. its entry in the language's override table (phonemes with the stress and tone tokens);
2. a word made only of number morphs (tjugotvå, tjueen, hundrafemtio): morph by morph from the
   NUMBER_MORPHS table, with the stress and tone of the last morph that has one;
3. an unstressed prefix (be-, för- / for-) before a stem with a vowel and a valid onset, then
   the stem (its stress is accent 1);
4. the rules: graphemes, longest first (the language's GRAPHEMES anywhere; INITIAL groups and the
   soft k g sk before a front vowel at the start of the stem; c is s before a front vowel, else
   k; a doubled consonant is one sound); stress (a stressed ending of STRESSED_ENDINGS, also
   before an inflection of INFLECTIONS; the vowel before an ending of PRESTRESS; else the first
   syllable); vowel length (a stressed vowel is long before nothing, one consonant letter, or rd
   rn rl (also before another consonant: nordväst); short before two consonants, a doubled consonant, x and a final m; unstressed vowels
   are short); an unstressed e after the stress in an ending of SCHWA_ENDINGS is a schwa; the
   silent letters of the language (SILENT: Norwegian final d after a vowel, l, n or r, the g of
   -ig, the t of an unstressed -et; Swedish the g of -ig and -igt); then r + t d n s l become one
   retroflex consonant, and t d n s l right after one are retroflex too (rst -> s` t`).

The tone token follows the stressed vowel: '1 (accent 1, acute) or '2 (accent 2, grave). A stress
on the last syllable (every stressed one-syllable word) is accent 1; so is a stress after an
unstressed prefix, and a two-syllable word ending in one of ACUTE_ENDINGS (the definite and
plural forms of one-syllable words: bilen, huset); any other word stressed before its last
syllable has accent 2. An ending of SECONDARY (-het -dom -skap ...) after an accent-2 stress gets
the secondary-stress token "," after its vowel. One-syllable function words (FUNCTION_WORDS) have
no tone token (their vowel length follows the rules). An ending after a doubled consonant is not a
stressed ending (annat).
"""

from __future__ import annotations

from dataclasses import dataclass

VOWEL_LETTERS = "aeiouyåäöæøéèòôóü"
TONES = ("'1", "'2", ",")


@dataclass(frozen=True)
class Rules:
    code: str
    vowels: str                                  # vowel letters
    front: tuple[str, ...]                       # spellings that soften k g sk before them
    front_c: str                                 # letters before which c is s
    long: dict[str, str]                         # vowel letter -> long vowel
    short: dict[str, str]                        # vowel letter -> short vowel
    before_r: dict[str, tuple[str, str]]         # vowel letter -> (long, short) before r
    before_r_coda: str                           # letters of before_r only before an r not followed by a vowel
    diphthongs: tuple[tuple[str, str], ...]      # spelling -> diphthong token (no: ei øy au ai)
    graphemes: tuple[tuple[str, tuple[str, ...]], ...]       # consonant groups anywhere ("ti|on": before on)
    initial: tuple[tuple[str, tuple[str, ...]], ...]         # consonant groups at a stem start
    soft: tuple[tuple[str, tuple[str, ...]], ...]            # k g sk before a front vowel at a stem start
    single: dict[str, str]                       # consonant letter -> phoneme
    prefixes: tuple[tuple[str, tuple[str, ...]], ...]        # unstressed prefixes
    not_prefix: tuple[str, ...]                  # words (and their inflections) that look prefixed
    onsets: frozenset[str]                       # valid onsets of two or more letters
    stressed_endings: tuple[tuple[str, int], ...]  # (ending, letter offset of its stressed vowel)
    inflections: tuple[str, ...]                 # endings after a stressed ending (stationen)
    prestress: tuple[str, ...]                   # endings stressing the vowel before them
    acute_endings: tuple[str, ...]               # two-syllable words with these endings: accent 1
    secondary: tuple[str, ...]                   # endings with a secondary stress
    function_words: frozenset[str]
    schwa_endings: tuple[str, ...]               # unstressed final syllables read with @
    number_morphs: dict[str, tuple[str, ...]]    # number morph -> phonemes (with tone tokens)
    silent: tuple[str, ...]                      # silent-letter rules: "d", "ig", "igt", "ige", "et"
    unstressed: dict[str, str]                   # vowel letter -> unstressed word-final vowel
    final_g_j: bool                              # g after l r at the end or before e i y ä ö is j (sv)


def _front_at(w: str, i: int, r: Rules) -> bool:
    return any(w.startswith(f, i) for f in r.front)


def segments(w: str, r: Rules) -> list[list]:
    """["V", vowel letter or diphthong token, spelling] or ["C", phonemes, spelling] per
    grapheme, in order."""
    out: list[list] = []
    i, n = 0, len(w)
    while i < n:
        c = w[i]
        hit = None
        for g, tok in r.diphthongs:
            if w.startswith(g, i):
                hit = ["V", tok, g]
                break
        if hit is None and c in r.vowels:
            hit = ["V", c, c]
        if hit is None and i == 0:
            for g, ph in r.soft:
                if w.startswith(g, i) and _front_at(w, i + len(g), r):
                    hit = ["C", ph, g]
                    break
            if hit is None:
                for g, ph in r.initial:
                    if w.startswith(g, i):
                        hit = ["C", ph, g]
                        break
        if hit is None:
            for g, ph in r.graphemes:
                pre, _, post = g.partition("|")  # "ti|on": ti when on follows
                if w.startswith(pre, i) and w.startswith(post, i + len(pre)):
                    hit = ["C", ph, pre]
                    break
        if hit is None and c == "c":
            ph = ("s",) if i + 1 < n and w[i + 1] in r.front_c else ("k",)
            hit = ["C", ph, "cc" if i + 1 < n and w[i + 1] == "c" else "c"]
        if hit is None and c == "g" and r.final_g_j and i > 0 and w[i - 1] in "lr" \
                and (i == n - 1 or w[i + 1] in r.front_c):
            hit = ["C", ("j",), "g"]  # sv: älg, berg, Norge, berget
        if hit is None and c in r.single:
            hit = ["C", (r.single[c],), c + c if i + 1 < n and w[i + 1] == c else c]
        if hit is None:  # a letter without a reading (an apostrophe)
            i += 1
            continue
        out.append(hit)
        i += len(hit[2])
    return out


def _start(segs: list[list], k: int) -> int:
    return sum(len(s[2]) for s in segs[:k])


def _nucleus_at(segs: list[list], nuclei: list[int], pos: int) -> int | None:
    for k in nuclei:
        if _start(segs, k) == pos:
            return k
    return None


def stress_index(w: str, segs: list[list], nuclei: list[int], r: Rules) -> int | None:
    if not nuclei:
        return None
    if len(nuclei) == 1:
        return nuclei[0]
    for e in r.prestress:
        if w.endswith(e) and len(w) > len(e):
            before = [k for k in nuclei if _start(segs, k) < len(w) - len(e)]
            if before:
                return before[-1]
    for infl in ("",) + r.inflections:
        if infl and not w.endswith(infl):
            continue
        stem = w[:len(w) - len(infl)]
        for e, off in r.stressed_endings:
            cut = len(stem) - len(e)
            if stem.endswith(e) and cut > 0 and not (cut >= 2 and stem[cut - 1] == stem[cut - 2]):
                k = _nucleus_at(segs, nuclei, len(stem) - len(e) + off)
                if k is not None:
                    return k
    return nuclei[0]


def _consonants_after(segs: list[list], k: int) -> str:
    """Spelling of the consonants after segs[k] up to the next vowel or the end."""
    out = ""
    j = k + 1
    while j < len(segs) and segs[j][0] == "C":
        out += segs[j][2]
        j += 1
    return out


def _is_long(segs: list[list], k: int) -> bool:
    cons = _consonants_after(segs, k)
    if cons[:2] in ("rd", "rn", "rl"):
        return True
    if cons == "m" and k + 2 == len(segs):
        return False
    return cons == "" or (len(cons) == 1 and cons != "x")


def _ending_vowel(w: str, segs: list[list], k: int, endings: tuple[str, ...]) -> bool:
    """The word ends with one of endings and segs[k] is the ending's first vowel."""
    for e in endings:
        if w.endswith(e) and len(w) > len(e):
            first = next((j for j, ch in enumerate(e) if ch in VOWEL_LETTERS), -1)
            if first >= 0 and _start(segs, k) == len(w) - len(e) + first:
                return True
    return False


def _silent(w: str, segs: list[list], k: int, stress: int | None, r: Rules) -> bool:
    """The consonant segs[k] is not pronounced."""
    g = segs[k][2]
    last = k == len(segs) - 1
    prev = segs[k - 1] if k > 0 else None
    if "d" in r.silent and g == "d" and prev is not None:
        if last and (prev[0] == "V" or prev[2] in ("l", "n", "r")):
            return True  # god, tid, land, kald, gård
        if prev[2] in ("l", "n") and w[_start(segs, k) + 1:] in ("e", "er", "en", "et", "es"):
            return True  # holde, kalde, landet
    if g == "g" and prev is not None and prev[2] == "i" and k - 1 != stress:
        tail = w[_start(segs, k) + 1:]
        if "ig" in r.silent and tail == "":
            return True  # rolig, viktig
        if "igt" in r.silent and tail == "t":
            return True  # roligt
        if "ige" in r.silent and tail in ("e", "es"):
            return True  # viktige
    # huset, kastet
    return ("et" in r.silent and g == "t" and last and prev is not None and prev[2] == "e"
            and k - 1 != stress and stress is not None and not _ending_vowel(w, segs, k - 1, r.secondary))


def rules_phonemes(w: str, r: Rules, after_prefix: bool = False) -> list[str]:
    """Phonemes of a stem read by the rules, with the stress and tone tokens."""
    segs = segments(w, r)
    nuclei = [k for k, s in enumerate(segs) if s[0] == "V"]
    stress = stress_index(w, segs, nuclei, r)
    tone = ""
    function = len(nuclei) == 1 and w in r.function_words  # no tone token
    if stress is not None and not function:
        if stress == nuclei[-1] or after_prefix or (
                len(nuclei) == 2 and any(w.endswith(e) and len(w) > len(e) for e in r.acute_endings)
                and not any(w.endswith(e) for e in r.secondary)):
            tone = "'1"
        else:
            tone = "'2"
    out: list[str] = []
    for k, s in enumerate(segs):
        if s[0] == "C":
            if not _silent(w, segs, k, stress, r):
                out.extend(s[1])
            continue
        v = s[1]
        if v not in r.long:  # a diphthong token
            out.append(v)
            if k == stress and tone:
                out.append(tone)
            continue
        nxt = segs[k + 1][2] if k + 1 < len(segs) else ""
        if nxt[:1] == "r" and v in r.before_r_coda and len(nxt) == 1 and k + 2 < len(segs) \
                and segs[k + 2][0] == "V":
            nxt = ""  # e before an r and a vowel keeps its quality (studere, era)
        if k == stress:
            long = _is_long(segs, k)
            if nxt[:1] == "r" and v in r.before_r:
                out.append(r.before_r[v][0 if long else 1])
            else:
                out.append(r.long[v] if long else r.short[v])
            if tone:
                out.append(tone)
            continue
        second = tone == "'2" and k > stress and _ending_vowel(w, segs, k, r.secondary) \
            if stress is not None else False
        if v == "e" and not second and stress is not None and k > stress \
                and _ending_vowel(w, segs, k, r.schwa_endings):
            out.append("@")
            continue
        if nxt[:1] == "r" and v in r.before_r:
            out.append(r.before_r[v][1])
        else:
            out.append(r.unstressed.get(v, r.short[v]) if k == len(segs) - 1 else r.short[v])
        if second:
            out.append(",")
    return out


RETRO = {"t": "t`", "d": "d`", "n": "n`", "s": "s`", "l": "l`"}


def retroflex(ph: list[str]) -> list[str]:
    """r + t d n s l -> one retroflex consonant; t d n s l right after a retroflex one are
    retroflex too (rst -> s` t`)."""
    out: list[str] = []
    for p in ph:
        if p in RETRO and out and out[-1] == "r":
            out[-1] = RETRO[p]
        elif p in RETRO and out and out[-1].endswith("`"):
            out.append(RETRO[p])
        else:
            out.append(p)
    return out


def is_vowel(p: str) -> bool:
    return p[0] in "aeiouyAEIOUY@9}{28"


def merge(ph: list[str]) -> list[str]:
    """Doubled consonants from adjacent graphemes or morphs are one."""
    out: list[str] = []
    for p in ph:
        if out and p == out[-1] and p not in TONES and not is_vowel(p):
            continue
        out.append(p)
    return out


def number_split(w: str, r: Rules) -> list[str] | None:
    """The number morphs of w (two or more, fewest pieces, the first split found in morph order
    on ties), or None."""
    n = len(w)
    best: list[list[str] | None] = [None] * (n + 1)
    best[0] = []
    for i in range(n):
        cur = best[i]
        if cur is None:
            continue
        for m in r.number_morphs:
            j = i + len(m)
            if j <= n and w.startswith(m, i):
                prev = best[j]
                if prev is None or len(cur) + 1 < len(prev):
                    best[j] = cur + [m]
    parts = best[n]
    return parts if parts is not None and len(parts) >= 2 else None


def number_phonemes(parts: list[str], r: Rules) -> list[str]:
    """Morphs read from the table; only the last morph with a tone token keeps it."""
    keep = max(k for k, m in enumerate(parts) if any(p in TONES for p in r.number_morphs[m])) \
        if any(p in TONES for m in parts for p in r.number_morphs[m]) else -1
    out: list[str] = []
    for k, m in enumerate(parts):
        out += [p for p in r.number_morphs[m] if k == keep or p not in TONES]
    return out


def prefix_split(w: str, r: Rules) -> tuple[tuple[str, ...], str] | None:
    """(prefix phonemes, stem) for an unstressed prefix, or None."""
    for p, ph in r.prefixes:
        rest = w[len(p):]
        if not w.startswith(p) or len(rest) < 3:
            continue
        if any(w.startswith(x) and w[len(x):] in ("",) + r.inflections for x in r.not_prefix):
            continue
        k = 0
        while k < len(rest) and rest[k] not in r.vowels:
            k += 1
        if k == len(rest) or k == 0 or (k > 1 and rest[:k] not in r.onsets):
            continue
        return ph, rest
    return None


def word_phonemes(w: str, r: Rules, overrides: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    if not w:
        return ()
    if w in overrides:
        return overrides[w]
    parts = number_split(w, r)
    if parts is not None:
        return tuple(retroflex(merge(number_phonemes(parts, r))))
    sp = prefix_split(w, r)
    if sp is not None:
        ph, rest = sp
        body = overrides.get(rest)
        if body is None:
            body = tuple(rules_phonemes(rest, r, after_prefix=True))
        else:
            body = tuple("'1" if p == "'2" else p for p in body)
        return tuple(retroflex(merge(list(ph) + list(body))))
    return tuple(retroflex(merge(rules_phonemes(w, r))))
