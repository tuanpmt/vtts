"""Russian word -> ru-en tokens (stress, spelling rules, vowel reduction, voicing).

A word (lower case, after normalize_ru) is read in five steps:

1. Stress. A word written with ё is stressed on the ё. Otherwise lexicons/ru/overrides.tsv
   (hand-written), then lexicons/ru/stress.tsv (forms the suffix rule gets wrong and words whose ё
   is usually written е, from a CC0 stress dictionary, see scripts/frontend/build_ru_stress.py)
   give the word with "+" before the stressed vowel; else a one-vowel word is stressed (except
   the clitics of UNSTRESSED: one-syllable prepositions, conjunctions and particles) and a longer
   word takes the position of the longest matching ending in lexicons/ru/stress_suffixes.tsv.
   A hyphenated word is read part by part (кто-то: the particle то is unstressed).
2. Spelling: unpronounced consonants (чувство, честный, поздно, солнце, сердце), сч/зч -> щ,
   тч/дч -> ч, тс/дс in -тся/-ться and -тск-/-дск- -> ц, тц/дц -> ц, сш/зш -> ш, сж/зж -> ж,
   гк/гч -> хк/хч (легко), г -> в in the endings -ого/-его (его, нового, сегодня), что -> што,
   чн -> шн in a few words (конечно, скучно), doubled consonants written once.
3. Letters: a consonant is soft (') before ь е ё и ю я; ж ш ц are always hard and ч щ й always
   soft. е ё ю я are j + vowel at the start of a word, after a vowel and after ь ъ; и after ж ш ц
   is ы; э keeps the consonant before it hard.
4. Vowel reduction: the stressed vowel keeps its quality (a1 e1 i1 o1 u1 y1). Unstressed а/о
   after a hard consonant (or at the start) are "a" in the syllable right before the stress and
   at the absolute start of the word, "@" elsewhere; unstressed е/я/а after a soft consonant or
   j are "i", except a final unstressed я/а (время, поля) which is "@"; unstressed е after ж ш ц
   is "y" (жена). A word without stress (a clitic) is read as if its last syllable came right
   before a stress (на -> n a, не -> n' i).
5. Assimilative softness: с з before т' д' н' and н before т' д' when a vowel follows (кости,
   жизни, бантик; not есть). Voicing: in a run of obstruents the last one sets the voicing of those before it (сделать
   -> z d', вокзал -> g z, сказка -> s k); в/в' is devoiced like the others but does not voice
   what comes before it (свет); obstruents at the end of a word are devoiced (дуб -> p).
   x, ts, ch, shch have no voiced partner and stay.

valid_word() says whether a word is Cyrillic (lang.py); unreadable_ru lists letters the
front-end cannot read.
"""

from __future__ import annotations

import functools
import re
import unicodedata

from ..lexicons import load_table

VOWEL_LETTERS = frozenset("аеёиоуыэюя")
SOFT_VOWELS = frozenset("еёиюя")
LETTERS = frozenset("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
# Letters of other Cyrillic alphabets read with the nearest Russian letters.
FOLD = {"і": "и", "ї": "йи", "є": "е", "ґ": "г", "ў": "у", "ј": "й", "ѣ": "е", "ѳ": "ф",
        "ѵ": "и", "ђ": "дь", "ћ": "ч", "љ": "ль", "њ": "нь", "џ": "дж", "ѕ": "з", "ќ": "к",
        "ѓ": "г", "ә": "а", "ө": "о", "ү": "у", "ұ": "у", "қ": "к", "ғ": "г", "ң": "н", "һ": "х"}
CONSONANT = {"б": "b", "в": "v", "г": "g", "д": "d", "ж": "zh", "з": "z", "к": "k", "л": "l",
             "м": "m", "н": "n", "п": "p", "р": "r", "с": "s", "т": "t", "ф": "f", "х": "x",
             "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "й": "j"}
PAIRED = frozenset(("p", "b", "t", "d", "k", "g", "f", "v", "s", "z", "m", "n", "l", "r", "x"))
ALWAYS_HARD = frozenset(("zh", "sh", "ts"))
VOWEL_OF = {"а": "a", "я": "a", "о": "o", "ё": "o", "у": "u", "ю": "u", "э": "e", "е": "e",
            "ы": "y", "и": "i"}
VOICED = {"b": "p", "d": "t", "g": "k", "v": "f", "z": "s", "zh": "sh"}
VOICELESS = {v: k for k, v in VOICED.items()}
OBSTRUENTS = frozenset(VOICED) | frozenset(VOICELESS) | {"x", "ts", "ch", "shch"}

# One-syllable function words without stress (prepositions, conjunctions, particles).
UNSTRESSED = frozenset((
    "без", "безо", "в", "во", "до", "за", "из", "изо", "к", "ко", "на", "над", "о", "об",
    "обо", "от", "ото", "по", "под", "подо", "пред", "при", "про", "с", "со", "у", "и", "а", "но",
    "да", "же", "ж", "ли", "ль", "бы", "б", "не", "ни", "то", "нибудь", "ка", "таки",
))
# чн read шн (whole words or word starts).
CHN_SH = ("конечн", "скучн", "нарочн", "яичниц", "скворечн", "прачечн", "горчичник", "двоечник",
          "троечник", "подсвечник", "переносиц")
GO_KEEP = frozenset(("много", "немного", "строго", "нестрого", "дорого", "недорого", "убого",
                     "полого", "отлого", "разлого", "пологого", "благого", "нагого", "строгого",
                     "дорогого", "убогого", "отлогого", "немногого", "многого"))
# Ordered spelling rules (regex, replacement) on the word with "+" before the stressed vowel.
RULES = (
    (r"вств", "ств"), (r"стн", "сн"), (r"здн", "зн"), (r"стл", "сл"), (r"лнц", "нц"),
    (r"рдц", "рц"), (r"рдч", "рч"), (r"нтск", "нск"), (r"ндск", "нск"), (r"нтг", "нг"),
    (r"[сз]ч", "щ"), (r"жч", "щ"), (r"[тд]ч", "ч"), (r"[тд]ь?с(?=\+?я$)", "ц"),
    (r"[тд]ск", "цк"), (r"[тд]ц", "ц"), (r"[сз]ш", "ш"),
    (r"[сз]ж", "ж"), (r"г(?=[кч])", "х"),
)


COMPOSE = {"е\u0308": "ё", "Е\u0308": "Ё", "и\u0306": "й", "И\u0306": "Й"}


def compose(text: str) -> str:
    """ё and й written with a combining mark (е + U+0308, и + U+0306) as one letter, and the
    combining acute (a stress mark in dictionaries) dropped."""
    for k, v in COMPOSE.items():
        text = text.replace(k, v)
    return text.replace("\u0301", "")


def fold(word: str) -> str:
    """Lower case Cyrillic; other Cyrillic letters to the nearest Russian ones; letters with a
    diacritic to their base letter when it is Russian (ѐ -> е); anything else dropped."""
    out = []
    for ch in compose(word.lower()):
        if ch in LETTERS or ch in "-+":
            out.append(ch)
        elif ch in FOLD:
            out.append(FOLD[ch])
        else:
            base = unicodedata.normalize("NFD", ch)[0]
            if base in LETTERS:
                out.append(base)
    return "".join(out)


def is_cyrillic(ch: str) -> bool:
    return "\u0400" <= ch <= "\u04ff"


def is_ru_word(word: str) -> bool:
    return any(is_cyrillic(ch) for ch in word)


@functools.cache
def _overrides() -> dict[str, str]:
    return load_table("ru", "overrides")


@functools.cache
def _stress_words() -> dict[str, str]:
    return load_table("ru", "stress")


@functools.cache
def _suffixes() -> tuple[dict[str, int], int]:
    table = {k[1:]: int(v) for k, v in load_table("ru", "stress_suffixes").items()}
    return table, max(map(len, table))


def _vowel_positions(w: str) -> list[int]:
    return [i for i, ch in enumerate(w) if ch in VOWEL_LETTERS]


def stress_source(word: str) -> str:
    """Where the stress of a (folded, lower-case) word comes from: "marked" (+ or ё), "overrides",
    "stress" (the word table), "none" (clitic or no vowel), "one" (one vowel) or "suffix"."""
    if "+" in word or "ё" in word:
        return "marked"
    key = word.replace("ё", "е")
    for name, table in (("overrides", _overrides()), ("stress", _stress_words())):
        if key in table:
            return name
    vow = _vowel_positions(word)
    if not vow or word in UNSTRESSED:
        return "none"
    return "one" if len(vow) == 1 else "suffix"


def stressed(word: str) -> str:
    """The word with "+" before its stressed vowel (none for a clitic or a word without vowels);
    ё from the stress table is restored (еще -> ещ+ё)."""
    w = word
    source = stress_source(w)
    if "+" in w:
        return w
    if "ё" in w:
        k = w.rindex("ё")
        return w[:k] + "+" + w[k:]
    key = w.replace("ё", "е")
    if source == "overrides":
        return _overrides()[key]
    if source == "stress":
        return _stress_words()[key]
    vow = _vowel_positions(w)
    if source == "none":
        return w
    if source == "one":
        k = vow[0]
    else:
        table, longest = _suffixes()
        back = table[""]
        for n in range(min(longest, len(key)), 0, -1):
            if key[len(key) - n:] in table:
                back = table[key[len(key) - n:]]
                break
        k = vow[max(0, len(vow) - 1 - back)]
    return w[:k] + "+" + w[k:]


def _spelling(w: str) -> str:
    plain = w.replace("+", "")
    if plain in ("что", "чтобы", "ничто", "кое-что") or plain.startswith("что"):
        w = w.replace("чт", "шт", 1)
    if plain.startswith(CHN_SH):
        w = w.replace("чн", "шн", 1)
    if plain == "сегодня" or plain.startswith("сегодняш"):
        w = w.replace("г", "в", 1)
    if (plain.endswith(("ого", "его")) and plain not in GO_KEEP
            and len(_vowel_positions(plain)) >= 2):
        w = re.sub(r"г(\+?о)$", r"в\1", w)
    for pat, rep in RULES:
        w = re.sub(pat, rep, w)
    # doubled consonant letters are written once
    return re.sub(r"([бвгджзклмнпрстфхцчшщ])\1", r"\1", w)


def _segments(w: str) -> list[list]:
    """["C", phoneme, soft] and ["V", quality, stressed, soft_before, hard_hush_before, final]."""
    segs: list[list] = []
    stress_next = False
    prev = ""  # previous letter ("" at the start)
    for i, ch in enumerate(w):
        if ch == "+":
            stress_next = True
            continue
        if ch in ("ь", "ъ"):
            if ch == "ь" and segs and segs[-1][0] == "C" and segs[-1][1] in PAIRED:
                segs[-1][2] = True
            prev = ch
            continue
        if ch in VOWEL_LETTERS:
            q = VOWEL_OF[ch]
            last_c = segs[-1] if segs and segs[-1][0] == "C" and prev not in ("ь", "ъ", "") \
                and prev not in VOWEL_LETTERS else None
            if ch in "еёюя" and last_c is None or ch == "и" and prev == "ь":
                segs.append(["C", "j", True])
                last_c = segs[-1]
            if last_c is not None:
                if ch in SOFT_VOWELS and last_c[1] in PAIRED:
                    last_c[2] = True
                if last_c[1] in ALWAYS_HARD and q == "i":
                    q = "y"
            soft = last_c is not None and (last_c[2] or last_c[1] in ("ch", "shch", "j"))
            hush = last_c is not None and last_c[1] in ALWAYS_HARD
            segs.append(["V", q, stress_next, soft, hush, False, ch])
            stress_next = False
        elif ch in CONSONANT:
            segs.append(["C", CONSONANT[ch], CONSONANT[ch] in ("ch", "shch", "j")])
        prev = ch
    for s in reversed(segs):
        if s[0] == "V":
            s[5] = True
            break
    return segs


def _reduce(segs: list[list]) -> list[str]:
    vowels = [k for k, s in enumerate(segs) if s[0] == "V"]
    stress_at = next((n for n, k in enumerate(vowels) if segs[k][2]), len(vowels))
    out = []
    for k, s in enumerate(segs):
        if s[0] == "C":
            out.append(s[1] + ("'" if s[2] and s[1] in PAIRED else ""))
            continue
        n = vowels.index(k)
        q, is_stressed, soft, hush, final, letter = s[1], s[2], s[3], s[4], s[5], s[6]
        if is_stressed:
            out.append(q + "1")
            continue
        if q in ("u", "y") or (q == "i" and not soft):
            out.append(q if q != "i" or not hush else "y")
            continue
        pretonic1 = n == stress_at - 1
        initial = k == 0
        if soft:
            out.append("@" if final and n > stress_at and letter in "яа" else "i")
        elif hush and q == "e":
            out.append("y")
        elif q == "e" or q == "i":
            out.append("i")
        else:  # a / o after a hard consonant or at the start
            out.append("a" if pretonic1 or initial else "@")
    return out


SOFTENS_SZ = frozenset(("t'", "d'", "n'"))
SOFTENS_N = frozenset(("t'", "d'"))


def _soften(ph: list[str]) -> list[str]:
    """Assimilative softness before a soft dental that a vowel follows: с з before т' д' н'
    (кости, жизни), н before т' д' (бантик); not at the end of a word (есть, часть)."""
    out = list(ph)
    for k in range(len(out) - 3, -1, -1):
        nxt = out[k + 1]
        if out[k + 2][0] not in "aeiouy@":
            continue
        if out[k] in ("s", "z") and nxt in SOFTENS_SZ or out[k] == "n" and nxt in SOFTENS_N:
            out[k] += "'"
    return out


def _voicing(ph: list[str]) -> list[str]:
    out = list(ph)

    def base(p: str) -> tuple[str, str]:
        return (p[:-1], "'") if p.endswith("'") else (p, "")

    def set_voice(p: str, voiced: bool) -> str:
        b, soft = base(p)
        if voiced and b in VOICELESS:
            return VOICELESS[b] + soft
        if not voiced and b in VOICED:
            return VOICED[b] + soft
        return p

    target: bool | None = False  # voicing set by the right context; None: a vowel or sonorant
    for k in range(len(out) - 1, -1, -1):
        b, _ = base(out[k])
        if b not in OBSTRUENTS:
            target = None
            continue
        if target is not None:
            out[k] = set_voice(out[k], target)
        if b == "v":  # в takes the voicing of what follows but does not pass on its own
            continue
        target = base(out[k])[0] in VOICED
    return out


@functools.lru_cache(maxsize=32768)
def phonemes(word: str) -> tuple[str, ...]:
    """Phonemes of one word ('молоко' -> m @ l a k o1), without the RU: prefix. The parts of a
    hyphenated word (кто-то, в-доме) are read one by one and share the softness and voicing
    rules."""
    w = fold(word).strip("-")
    out: list[str] = []
    for part in w.split("-"):
        if part:
            out += _part_phonemes(part)
    return tuple(_voicing(_soften(out)))


def _part_phonemes(w: str) -> list[str]:
    segs = _segments(_spelling(stressed(w)))
    if not any(s[0] == "V" for s in segs):
        return [s[1] + ("'" if s[2] and s[1] in PAIRED else "") for s in segs]
    return _reduce(segs)


def word_tokens_ru(word: str) -> list[str]:
    """ru-en tokens of one Cyrillic word; a word without a vowel is spelled (ж -> жэ) unless it
    is a one-letter preposition (в, к, с are joined to the next word by normalize_ru)."""
    w = fold(word)
    if w and not any(ch in VOWEL_LETTERS for ch in w) and w not in ("в", "к", "с", "б", "ж"):
        from .normalize_ru import LETTER_NAMES

        return [t for ch in w if ch in LETTER_NAMES for n in LETTER_NAMES[ch].split()
                for t in word_tokens_ru(n)]
    return [f"RU:{p}" for p in phonemes(word)]


def unreadable_ru(text: str) -> list[str]:
    """Letters the Russian front-end cannot read (scripts other than Cyrillic and Latin); Latin
    words are read by the English module."""
    out = []
    for ch in text:
        if not ch.isalpha() or is_cyrillic(ch) and fold(ch) or ch.isascii():
            continue
        if unicodedata.normalize("NFKD", ch)[0].isascii():
            continue
        out.append(ch)
    return out
