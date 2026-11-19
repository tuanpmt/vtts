"""Polish word -> pl-en tokens (spelling rules, nasal vowels, voicing, penultimate stress).

A word (lower case, after normalize_pl) is first replaced by its entry in lexicons/pl/overrides.tsv
(respellings in Polish orthography with "+" before the stressed vowel where the stress is not
the default: matem+atyka), then read letter by letter:

- Digraphs: ch h -> x, cz -> ch, sz -> sh, rz ż -> zh, dż -> dzh, dz -> dz, dź -> dz', szcz ->
  sh ch; ć ś ź ń -> c' s' z' n'; ł -> w, w -> v, ó u -> u, y -> y; foreign q -> k, v -> v,
  x -> k s.
- i: after c s z n dz it marks softness (ci si zi ni dzi = ć ś ź ń dź) and is silent before a
  vowel (ciasto, siedem, nie, linii); after another consonant before a vowel it is j (piasek ->
  p j a, miasto -> m j a, kiedy -> k j e, historii -> r j i); else the vowel i.
- Nasal vowels ą ę: before p b -> o/e + m (dąb, zęby), before t d c dz cz dż -> + n (kąt,
  będę), before ć dź -> + n' (będzie), before k g -> + n (ręka), before l ł -> oral (wziął,
  zaczęli); a final ę is e (idę); elsewhere the nasal vowel on / en (wąs, mąż, są).
- Voicing: in a run of obstruents the last one sets the voicing of the others (wódka -> t k,
  prośba -> z' b, także -> g zh); w and rz (not ż) after a voiceless obstruent are devoiced
  (twój -> t f, przy -> p sh, krzesło -> k sh); obstruents at the end of a word are devoiced (chleb -> p, róg -> k).
- au eu are a w / e w (auto, Europa) except after na- za- prze- przy- do- po- (nauka), in a
  final -um (muzeum) and before sz (Tadeusz).
- Stress on the second-to-last syllable (vowel letters; the softening i is not a syllable);
  the third-to-last in the Greek and Latin -yka/-ika nouns of lexicons/pl/antepenult.txt
  (matematyka, muzyka, muzyce; not języka, silnika) and the past forms -liśmy -łyśmy
  -liście -łyście (byliśmy), the fourth-to-last in -byśmy -byście (zrobilibyśmy); one-syllable
  function words (UNSTRESSED: w z na do o i a że się nie ...) have none; lexicons/pl/overrides.tsv
  respells the exceptions (+ before the stressed vowel).

valid_spelling() says whether a plain ASCII word could be Polish (latin.py uses it to tell Polish
from English words).
"""

from __future__ import annotations

import functools
import unicodedata
from itertools import pairwise

from ..lexicons import load_table, load_words

VOWELS = "aeiouyąęó"
LETTERS = frozenset("aąbcćdeęfghijklłmnńoóprsśtuwyzźżqvx")
FOLD = {"ø": "o", "æ": "e", "œ": "e", "ß": "s", "đ": "d", "þ": "t"}
SOFTENABLE = {"c": "c'", "s": "s'", "z": "z'", "n": "n'", "dz": "dz'"}
SIMPLE = {"b": "b", "d": "d", "f": "f", "g": "g", "j": "j", "k": "k", "l": "l", "ł": "w", "m": "m",
          "n": "n", "p": "p", "r": "r", "s": "s", "t": "t", "w": "v", "z": "z", "c": "ts",
          "ć": "c'", "ś": "s'", "ź": "z'", "ń": "n'", "ż": "zh", "h": "x", "q": "k", "v": "v"}
VOWEL_OF = {"a": "a", "e": "e", "i": "i", "o": "o", "u": "u", "ó": "u", "y": "y", "ą": "on",
            "ę": "en"}
VOICED = {"b": "p", "d": "t", "g": "k", "v": "f", "z": "s", "zh": "sh", "z'": "s'", "dz": "ts",
          "dzh": "ch", "dz'": "c'"}
VOICELESS = {v: k for k, v in VOICED.items()}
VOICELESS_SET = frozenset(VOICELESS) | {"x"}
OBSTRUENTS = frozenset(VOICED) | VOICELESS_SET
NASAL_BEFORE = {**dict.fromkeys(("p", "b"), "m"),
                **dict.fromkeys(("t", "d", "ts", "dz", "ch", "dzh", "k", "g"), "n"),
                **dict.fromkeys(("c'", "dz'"), "n'")}

# au eu are one syllable (a w, e w) except after these word starts (na-uka, za-ufanie).
NO_DIPHTHONG = ("nau", "zau", "przeu", "przyu", "dou", "pou")
UNSTRESSED = frozenset((
    "w", "we", "z", "ze", "na", "do", "od", "ode", "po", "za", "o", "u", "i", "a", "że", "się",
    "nie", "by", "bo", "czy", "ku", "przy", "przez", "pod", "nad", "bez", "dla", "spod", "znad",
    "sprzed", "zza", "lub", "ni", "ach", "no", "to", "go", "mu", "mi", "ci", "cię", "mię", "jej",
))


@functools.cache
def override_table() -> dict[str, str]:
    return load_table("pl", "overrides")


@functools.cache
def antepenult_words() -> frozenset[str]:
    """Forms of the Greek and Latin -yka / -ika nouns of lexicons/pl/antepenult.txt (stems such
    as muzyk, matematyk): stem + a i ę ą and the stem with c for k + e (muzyce) are stressed on
    the third-to-last syllable."""
    out = set()
    for stem in load_words("pl", "antepenult"):
        out |= {stem + e for e in ("a", "i", "ę", "ą")} | {stem[:-1] + "ce"}
    return frozenset(out)


def fold(word: str) -> str:
    """Lower case, Polish letters kept, other accented letters reduced to their base letter
    (é -> e, ü -> u, č -> c), "+" (stress mark) and "-" (w-domu) kept, anything else dropped."""
    out = []
    for ch in word.lower():
        if ch in LETTERS or ch in "+-":
            out.append(ch)
            continue
        base = FOLD.get(ch) or (unicodedata.normalize("NFKD", ch) or " ")[0]
        if base in LETTERS:
            out.append(base)
    return "".join(out)


def _segments(w: str) -> list[list]:
    """["C", phoneme] and ["V", vowel, marked_stress] in order."""
    out: list[list] = []
    i, n = 0, len(w)
    mark = False
    while i < n:
        c = w[i]
        if c == "+":
            mark = True
            i += 1
            continue
        if c in VOWEL_OF:
            if c == "i" and out and out[-1][0] == "C" and i + 1 < n and w[i + 1] in VOWELS:
                prev = out[-1][1]
                if prev in SOFTENABLE.values():
                    i += 1  # ci si zi ni dzi + vowel: only softness
                    continue
                out.append(["C", "j"])
                i += 1
                continue
            if c == "u" and out and out[-1][0] == "V" and out[-1][1] in ("a", "e") and not out[-1][2] \
                    and (len(out) == 1 or out[-2][0] == "C") and not w.startswith(NO_DIPHTHONG) \
                    and w[i + 1:] != "m" and not w.startswith("sz", i + 1):
                out.append(["C", "w"])  # au eu: auto, Europa (not nauka, muzeum, Tadeusz)
                i += 1
                continue
            out.append(["V", VOWEL_OF[c], mark])
            mark = False
            i += 1
            continue
        step, ph = 1, None
        if w.startswith("szcz", i):
            out += [["C", "sh"], ["C", "ch"]]
            i += 4
            continue
        two = w[i:i + 2]
        if two == "ch":
            ph, step = "x", 2
        elif two == "cz":
            ph, step = "ch", 2
        elif two == "sz":
            ph, step = "sh", 2
        elif two == "rz":
            ph, step = "rz", 2  # zh, devoiced after a voiceless consonant (_voicing)
        elif two == "dż":
            ph, step = "dzh", 2
        elif two == "dź":
            ph, step = "dz'", 2
        elif two == "dz":
            ph, step = "dz", 2
        elif c == "x":
            out += [["C", "k"], ["C", "s"]]
            i += 1
            continue
        else:
            ph = SIMPLE.get(c)
        if ph is None:
            i += step
            continue
        after = w[i + step] if i + step < n else ""
        if after == "i":
            base = {"ts": "c", "s": "s", "z": "z", "n": "n", "dz": "dz"}.get(ph)
            if base is not None:
                ph = SOFTENABLE[base]
        out.append(["C", ph])
        i += step
    return out


def _nasals(segs: list[list]) -> list[list]:
    out: list[list] = []
    for k, s in enumerate(segs):
        if s[0] == "V" and s[1] in ("on", "en"):
            nxt = segs[k + 1] if k + 1 < len(segs) else None
            oral = "o" if s[1] == "on" else "e"
            if nxt is None:
                if s[1] == "en":
                    out.append(["V", "e", s[2]])
                    continue
            elif nxt[0] == "C" and nxt[1] in NASAL_BEFORE:
                out += [["V", oral, s[2]], ["C", NASAL_BEFORE[nxt[1]]]]
                continue
            elif nxt[0] == "C" and nxt[1] in ("l", "w"):
                out.append(["V", oral, s[2]])
                continue
        out.append(s)
    return out


def _voicing(ph: list[str]) -> list[str]:
    out = list(ph)
    # progressive devoicing of w and rz/ż after a voiceless obstruent (twój, przy, krzesło)
    for k in range(len(out)):
        if out[k] in ("v", "rz") and k and out[k - 1] in VOICELESS_SET:
            out[k] = "f" if out[k] == "v" else "sh"
        elif out[k] == "rz":
            out[k] = "zh"
    target: bool | None = False
    for k in range(len(out) - 1, -1, -1):
        p = out[k]
        if p not in OBSTRUENTS:
            target = None
            continue
        if target is not None:
            if target and p in VOICELESS:
                out[k] = VOICELESS[p]
            elif not target and p in VOICED:
                out[k] = VOICED[p]
        target = out[k] in VOICED
    return out


def stressed_vowel(word: str, segs: list[list]) -> int | None:
    vowels = [k for k, s in enumerate(segs) if s[0] == "V"]
    marked = [k for k in vowels if segs[k][2]]
    if marked:
        return marked[0]
    if not vowels or word in UNSTRESSED:
        return None
    back = 2
    if word.endswith(("byśmy", "byście")):
        back = 4
    elif word.endswith(("liśmy", "łyśmy", "liście", "łyście")) or word in antepenult_words():
        back = 3
    return vowels[max(0, len(vowels) - back)] if len(vowels) >= 2 else vowels[0]


def _part(w: str) -> list[str]:
    w = override_table().get(w, w)
    segs = _nasals(_segments(w))
    stress = stressed_vowel(w.replace("+", ""), segs)
    return [s[1] + ("1" if k == stress else "") for k, s in enumerate(segs)]


@functools.lru_cache(maxsize=32768)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('chrząszcz' -> x sh o1 n sh ch), without the PL: prefix. The parts
    of a hyphenated word (w-domu, joined by the normalizer) share the voicing rules."""
    w = fold(word).strip("-")
    out: list[str] = []
    for part in w.split("-"):
        if part:
            out += _part(part)
    return tuple(_voicing(out))


def word_tokens_pl(word: str) -> list[str]:
    """pl-en tokens of one word; a word without a vowel (other than the prepositions w z, which
    the normalizer joins to the next word) is spelled letter by letter."""
    w = fold(word).replace("+", "")
    if w and not any(ch in VOWELS for ch in w) and w not in ("w", "z"):  # (fold keeps "-")
        from .normalize_pl import LETTERS as NAMES

        return [t for ch in w if ch in NAMES for n in NAMES[ch].split() for t in word_tokens_pl(n)]
    return [f"PL:{p}" for p in phonemes(word)]


# ---------------- spelling check (Polish or English?) ----------------

FOREIGN = ("q", "v", "x", "th", "ph", "sh", "gh", "wh", "ee", "oo", "ou", "ay", "ey", "oy")


def valid_spelling(w: str) -> bool:
    """True when a lower-case ASCII word fits Polish spelling: a vowel, none of q v x or the
    English letter groups th ph sh gh wh ee oo ou ay ey oy (not ea: teatr, idea), no doubled letters
    other than nn zz jj ii, and no English ending -ing, -ly, -gy (Polish onsets and codas are too
    free to test clusters)."""
    if not w or not w.isascii() or not w.isalpha() or not any(ch in "aeiouy" for ch in w):
        return False
    if any(f in w for f in FOREIGN):
        return False
    if any(a == b and a not in "nzji" for a, b in pairwise(w)):
        return False
    return not (len(w) > 3 and w.endswith(("ing", "ly", "gy")))


def unreadable_pl(text: str) -> list[str]:
    """Letters the Polish front-end cannot read (other scripts), to filter training sentences;
    Latin letters with any accent are folded to a base letter and are readable."""
    return [ch for ch in text if ch.isalpha() and not fold(ch)]
