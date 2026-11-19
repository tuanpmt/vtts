"""Burmese text -> syllables -> my-en tokens (spelling rules after Google's Burmese grammar).

Burmese is written without spaces between words, but its syllables are delimited by the
spelling, so a run of Burmese letters is read syllable by syllable (no word list); every step is
table-driven (the C port follows the same steps):

1. Spelling (prepare). The text is in Unicode canonical order (my/zawgyi.to_unicode; Zawgyi is
   converted). Respellings (RESPELL: ယောက်ျား, ကျွန်ုပ်, ၎င်း), independent vowels as အ + vowel
   sign (ဣ ဤ ဥ ဦ ဧ ဩ ဪ), ါ as ာ, ဿ as သ်သ, kinzi င်္ as င် and the virama ္ as ် (the upper
   consonant of a stack closes the syllable before it: ကမ္ဘာ = ကမ်ဘာ).
2. Syllables (syllables). A syllable starts at a consonant that does not carry ် and takes its
   medials (ျ ြ ွ ှ), vowel signs, tone marks (့ း) and a final consonant with ် (one more final
   consonant of a loanword is not read). ၌ ၍ ၏ ၎င်း are words of their own (SPECIAL).
3. Readings. The onset is the base consonant (ONSET), changed by ှ (voiceless nasals and laterals,
   ယှ ရှ = ʃ, HA_ONSET) and ြ after င (ɲ); ျ and ြ are the glide y, ွ the glide w (unless the rhyme
   takes it: ွန် ွတ် ွံ). The rhyme comes from the vowel signs and the final (rhyme(), after the
   nucleus rules of the grammar): stop finals give a checked syllable (T4: ɛʔ ɪʔ aʔ eiʔ ouʔ aiʔ
   auʔ ʊʔ), nasal finals and ံ give ɪN aN eiN ouN aiN auN ʊN, ယ် is ɛ, ည် is i (SYLLABLES has the
   onsets for which it is ɛ or e), open vowels a i u e ɛ ɔ o. Tones: ့ creaky (T3), း high (T2),
   else the vowel's own tone (ိ ု creaky; ဲ ော high; the rest low, T1). A syllable without a vowel
   sign or final is the reduced ə (no tone) inside a run and a̰ (creaky) at its end; the particles
   က and မှ after a full syllable are a̰ too.

Voicing in compounds (ကောင်းကင် = kaʊ́ɴ gɪ̀ɴ) and the reduction of other syllables are not
written and are left to the voice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .zawgyi import ASAT, VIRAMA

CONSONANTS = "ကခဂဃငစဆဇဈဉညဋဌဍဎဏတထဒဓနပဖဗဘမယရလဝသဟဠအ"
ONSET = dict(zip(CONSONANTS, (
    "k", "kh", "g", "g", "ng", "s", "sh", "z", "z", "ny", "ny", "t", "th", "d", "d", "n", "t", "th",
    "d", "d", "n", "p", "ph", "b", "b", "m", "y", "y", "l", "w", "T", "h", "l", "?"), strict=True))
HA_ONSET = {"င": "hng", "ဉ": "hny", "ည": "hny", "ဏ": "hn", "န": "hn", "မ": "hm", "ယ": "S", "ရ": "S",
            "လ": "hl", "ဠ": "hl", "ဝ": "hw"}
MEDIALS = "ျြွှ"
VOWEL_SIGNS = "ေိီုူဲာံ"
DOT, VISARGA = "့", "း"
# Special words: their phonemes, syllables separated by " . " (tone as T1-T4).
SPECIAL = {"၌": "hn ai ? T4", "၍": "y w e T3", "၏": "? i T3", "၎င်း": "l @ . g au N T2",
           "၎": "l @ . g au N T2"}
# Particles read with the full a̰ after a full syllable, not the reduced ə (သူက, ဒီမှာမှ).
PARTICLES = frozenset(("က", "မှ"))
RESPELL = (("က်ျာ", "က်ကျာ"), ("န်ု", "န်နု"), ("င်္၎", "၎င်း"))
INDEPENDENT = {"ဣ": "အိ", "ဤ": "အီ", "ဥ": "အု", "ဦ": "အူ", "ဧ": "အေ", "ဩ": "အော", "ဪ": "အော်"}
K_FINALS = "ကဂ"
STOP_I = "ကဂစဋတဒပသ"       # after ိ ု: eiʔ ouʔ
T_FINALS = "ဋဌတထဒပဗဘဝသ"  # aʔ
N_FINALS = "ဏနမ"          # aN
NG_FINALS = "ငဉ"          # ɪN
# Syllables the rules read differently (from the exceptions of Google's grammar): spelling ->
# phonemes (onset, glides, rhyme, tone).
SYLLABLES = {
    "လည်း": "l E T2", "ဆည်": "sh E T1", "ထည်": "th E T1", "ထည့်": "th E T3", "ထည်း": "th E T2",
    "ပည်": "p E T1", "ပည့်": "p y i T3", "ပည်း": "p y i T2", "ပြည့်": "p y e T3",
    "ဖည်": "ph E T1", "ဖည့်": "ph E T3", "ဖည်း": "ph E T2", "ဖြည်": "ph y e T1",
    "ဖြည့်": "ph y e T3", "ဖြည်း": "ph y e T2", "ဗည်း": "b y i T2", "မည်": "m y i T1",
    "မည့်": "m y i T3", "မည်း": "m E T2", "မှည့်": "hm E T3", "ရှည်": "S e T1", "ရှည့်": "S e T3",
    "လည်": "l E T1", "လည့်": "l E T3", "လှည်": "hl E T1", "လှည့်": "hl E T3", "လှည်း": "hl E T2",
    "ကွမ်း": "k U N T2", "ဆွမ်း": "sh U N T2",
}


@dataclass
class Syllable:
    base: str = ""
    medials: str = ""
    vowel: str = ""          # vowel signs in canonical order (ေ ိ ီ ု ူ ဲ ာ ံ)
    final: str = ""          # final consonant
    dot: bool = False
    visarga: bool = False
    asat: bool = False       # ် on the vowel (ော်) or the final
    text: str = ""           # the spelling of the syllable
    special: str = ""        # phonemes of a special word
    extra: list[str] = field(default_factory=list)


def prepare(word: str) -> str:
    """Respellings, independent vowels, ါ, ဿ, kinzi and stacks (module docstring, step 1)."""
    w = word
    for a, b in RESPELL:
        w = w.replace(a, b)
    w = "".join(INDEPENDENT.get(ch, ch) for ch in w)
    w = w.replace("ါ", "ာ").replace("ဿ", "သ်သ")
    w = w.replace("င်္", "င်").replace(VIRAMA, ASAT)
    return w.replace(ASAT + ASAT, ASAT)


def _is_final(w: str, j: int) -> bool:
    """w[j] is a consonant closed by ် (with ့ between in canonical order)."""
    n = len(w)
    if j >= n or w[j] not in ONSET:
        return False
    k = j + 1
    if k < n and w[k] == DOT:
        k += 1
    return k < n and w[k] == ASAT


def syllables(word: str) -> list[Syllable]:
    """Syllables of a run of Burmese letters (prepared spelling)."""
    w = prepare(word)
    n = len(w)
    out: list[Syllable] = []
    i = 0
    while i < n:
        sp = next((k for k in SPECIAL if w.startswith(k, i)), None)
        if sp is not None:
            out.append(Syllable(special=SPECIAL[sp], text=sp))
            i += len(sp)
            continue
        ch = w[i]
        if ch not in ONSET:
            i += 1
            continue
        if _is_final(w, i) and out and not out[-1].special and not out[-1].final:
            s = out[-1]  # a final after a syllable that has none: ကမ်ဘာ
            j = i + 1
            s.final, s.asat = ch, True
            while j < n and w[j] in (DOT, ASAT, VISARGA):
                s.dot |= w[j] == DOT
                s.visarga |= w[j] == VISARGA
                j += 1
            s.text += w[i:j]
            i = j
            continue
        s = Syllable(base=ch)
        j = i + 1
        while j < n:
            x = w[j]
            if x in MEDIALS:
                s.medials += x
            elif x in VOWEL_SIGNS:
                s.vowel += x
            elif x == DOT:
                s.dot = True
            elif x == VISARGA:
                s.visarga = True
            elif x == ASAT:
                s.asat = True
            elif _is_final(w, j) and not s.final:
                s.final = x
                j += 1
                continue
            elif s.final and _is_final(w, j):
                s.extra.append(x)  # a second final of a loanword: not read
                j += 1
                continue
            else:
                break
            j += 1
        s.text = w[i:j]
        out.append(s)
        i = j
    return out


def _tone(default: str, s: Syllable) -> str:
    if s.dot:
        return "T3"
    if s.visarga:
        return "T2"
    return default


def rhyme(s: Syllable) -> tuple[list[str], bool]:
    """(vowel [final] tone, whether the rhyme takes the medial ွ)."""
    v, f = s.vowel.replace("ံ", ""), s.final
    nasal = "ံ" in s.vowel
    w = "ွ" in s.medials
    if f:
        if v == "" or v == "ာ":
            if f in K_FINALS and v == "":
                return ["E", "?", "T4"], False
            if f in NG_FINALS:
                return ["I", "N", _tone("T1", s)], False
            if f == "စ":
                return ["I", "?", "T4"], False
            if f == "ယ":
                return ["E", _tone("T1", s)], False
            if f == "ည":
                return ["i", _tone("T1", s)], False
            if f in N_FINALS:
                if w and v == "" and f != "မ":
                    return ["U", "N", _tone("T1", s)], True
                return ["a", "N", _tone("T1", s)], False
            if f in T_FINALS:
                if w and v == "" and f in "ဋတ":
                    return ["U", "?", "T4"], True
                return ["a", "?", "T4"], False
            return ["a", _tone("T1", s)], False
        if v == "ိ":
            if f in STOP_I:
                return ["ei", "?", "T4"], False
            if f in "ငဏနမ":
                return ["ei", "N", _tone("T1", s)], False
            return ["i", _tone("T3", s)], False
        if v == "ု":
            if f in STOP_I:
                return ["ou", "?", "T4"], False
            if f in "ဉဏနမ":
                return ["ou", "N", _tone("T1", s)], False
            return ["u", _tone("T3", s)], False
        if v == "ို":
            if f in "ကဋတ":
                return ["ai", "?", "T4"], False
            if f in "ငဏ":
                return ["ai", "N", _tone("T1", s)], False
            return ["o", _tone("T1", s)], False
        if v == "ေ":
            if f in "တသ":
                return ["I", "?", "T4"], False
            if f == "ည":
                return ["i", _tone("T1", s)], False
        if v == "ော":
            if f == "က":
                return ["au", "?", "T4"], False
            if f in "ငဏ":
                return ["au", "N", _tone("T1", s)], False
    if nasal:
        if v == "ိ":
            return ["ei", "N", _tone("T1", s)], False
        if v == "ု":
            return ["ou", "N", _tone("T1", s)], False
        if w and v == "":
            return ["U", "N", _tone("T1", s)], True
        return ["a", "N", _tone("T1", s)], False
    open_vowel = {"ာ": ("a", "T1"), "ိ": ("i", "T3"), "ီ": ("i", "T1"), "ု": ("u", "T3"),
                  "ူ": ("u", "T1"), "ေ": ("e", "T1"), "ဲ": ("E", "T2"), "ော": ("O", "T2"),
                  "ို": ("o", "T1"), "ိူ": ("o", "T1"), "ီု": ("o", "T1")}.get(v)
    if open_vowel is not None:
        vowel, tone = open_vowel
        if v == "ော" and s.asat:
            tone = "T1"  # ော်
        return [vowel, _tone(tone, s)], False
    return [], False  # no vowel sign: the reduced or the inherent vowel (syllable_phones)


def onset(s: Syllable, takes_w: bool) -> list[str]:
    m = s.medials
    if "ှ" in m:
        if s.base == "င" and "ြ" in m:
            ini, m = "hny", m.replace("ြ", "")
        elif s.base in ("လ", "သ") and "ျ" in m:
            ini, m = "S", m.replace("ျ", "")
        else:
            ini = HA_ONSET.get(s.base, ONSET[s.base])
    elif s.base == "င" and "ြ" in m:
        ini, m = "ny", m.replace("ြ", "")
    else:
        ini = ONSET[s.base]
    out = [ini]
    if "ျ" in m or "ြ" in m:
        out.append("G:y")
    if "ွ" in m and not takes_w:
        out.append("G:w")
    return out


def syllable_phones(s: Syllable, last: bool, after_full: bool = False) -> list[str]:
    """Phonemes of one syllable: onset ("G:" glides), vowel, final N or ?, tone T1-T4 (none for
    the reduced vowel)."""
    if s.special:
        return s.special.split()
    if s.text in SYLLABLES:
        return SYLLABLES[s.text].split()
    if s.base == "ဝ" and (s.vowel == "ံ" or (not s.vowel and s.final and s.final in "ဋတနဏ")):
        rh = ["U", "?", "T4"] if s.final and s.final in "ဋတ" else ["U", "N", _tone("T1", s)]
        return ["w", *rh]  # initial ဝ: ဝတ် ဝန် ဝံ
    rh, takes_w = rhyme(s)
    if not rh:
        if s.dot or s.visarga or last or (s.text in PARTICLES and after_full):
            rh = ["a", _tone("T3", s)]
        else:
            rh = ["@"]
    return onset(s, takes_w) + rh


def run_phones(run: str) -> list[list[str]]:
    """Phonemes per syllable of a run of Burmese letters; special words give several syllables."""
    syls = syllables(run)
    out: list[list[str]] = []
    for k, s in enumerate(syls):
        after_full = k > 0 and bool(syls[k - 1].vowel or syls[k - 1].final or syls[k - 1].special)
        ph = syllable_phones(s, k == len(syls) - 1, after_full)
        part: list[str] = []
        for p in ph:
            if p == ".":
                out.append(part)
                part = []
            else:
                part.append(p)
        out.append(part)
    return out


# ---------------- tokens ----------------

VOWELS = ("i", "u", "e", "o", "E", "O", "a", "@", "I", "U", "ei", "ou", "ai", "au")


def syllable_tokens(phones: list[str]) -> list[str]:
    """my-en tokens of one syllable: MY:I:initial [MY:M:glide...] MY:V:vowel [MY:F:N|?] [MY:Ttone]."""
    out: list[str] = []
    seen_vowel = False
    for p in phones:
        if p in VOWELS:
            out.append("MY:V:" + p)
            seen_vowel = True
        elif p.startswith("T") and p[1:].isdigit():
            out.append("MY:" + p)
        elif seen_vowel:
            out.append("MY:F:" + p)
        elif p.startswith("G:"):
            out.append("MY:M:" + p[2:])
        else:
            out.append("MY:I:" + p)
    return out


def burmese_syllable_tokens(run: str) -> list[list[str]]:
    """Tokens per syllable of a run of Burmese letters (Unicode, canonical order)."""
    return [syllable_tokens(p) for p in run_phones(run)]


def is_burmese(ch: str) -> bool:
    """Burmese letters and signs (U+1000..U+103F) and ၌ ၍ ၎ ၏ (not the digits, ၊ ။)."""
    return "က" <= ch <= "ဿ" or "၌" <= ch <= "၏"


def unreadable_my(text: str) -> list[str]:
    """Letters the Burmese front-end cannot read (other scripts than Burmese and Latin, and the
    Myanmar letters of other languages), to filter training sentences."""
    import unicodedata

    out = []
    for ch in text:
        if not ch.isalpha() or is_burmese(ch) or ch.isascii():
            continue
        base = unicodedata.normalize("NFKD", ch)[:1]
        if not (base.isascii() and base.isalpha()):
            out.append(ch)
    return out
