"""Sentence selection for speech synthesis from Wikipedia: Spanish, Indonesian, Brazilian
Portuguese, Thai and Hindi.

Only plain text that needs no normalization before synthesis is kept (no digits, brackets,
symbols, acronyms or foreign scripts); nothing else is filtered.

- es, pt, id: letters of the language, spaces, intra-word hyphens and , . ? ! (es also ¿ ¡),
  6-30 words, starting with a capital letter (after ¿ ¡ in es) and ending with . ? !. Words with
  two or more capitals (acronyms, Roman numerals), single capital letters after the first word
  (initials) and common abbreviations are rejected.
- hi: Devanagari letters and signs (no Devanagari digits), spaces, intra-word hyphens and , . ? !,
  5-30 words, ending with . ? !. The danda । is converted to "." before splitting, so every Hindi
  row ends with . ? ! like the other languages; double danda ॥ is rejected.
- th: Thai has no sentence punctuation and no spaces between words; spaces separate clauses and
  sentences. Paragraphs are split on single spaces (after joining the repetition mark ๆ to the
  word before it) and a chunk is kept when it has only Thai letters and signs (no Thai digits,
  no ฯ), 25-150 characters, and both neighbouring chunks (if any) are plain Thai too, so clauses
  cut off by a number, a foreign word or content the dump removed are left out. No final mark is
  required.
- All languages: a double space (content removed by the dump) rejects the sentence.

Duration estimates (read speech):
- es 6.0, pt 5.5, id 5.5 syllables/s, syllables counted as vowel groups.
- hi 6.0 aksharas/s (independent vowels plus consonants not followed by virama).
- th 13 spacing characters/s (Thai characters without the combining vowel and tone marks,
  about 2.5 per syllable at about 5.2 syllables/s).
"""

from __future__ import annotations

import re

LANGS = ("es", "id", "pt", "th", "hi")
LATIN_LETTERS = {
    "es": "a-zA-ZáéíóúüñÁÉÍÓÚÜÑ",
    "pt": "a-zA-ZáâãàçéêíóôõúÁÂÃÀÇÉÊÍÓÔÕÚ",
    "id": "a-zA-Z",
}
VOWELS = {
    "es": "aeiouáéíóúüAEIOUÁÉÍÓÚÜ",
    "pt": "aeiouáâãàéêíóôõúAEIOUÁÂÃÀÉÊÍÓÔÕÚ",
    "id": "aeiouAEIOU",
}
RATE = {"es": 6.0, "pt": 5.5, "id": 5.5, "hi": 6.0, "th": 13.0}
ABBREV = {
    "es": {"etc", "sr", "sra", "srta", "dr", "dra", "ud", "uds", "pág", "aprox", "núm", "art", "av", "vol",
           "cap", "ed", "fig", "gral", "lic", "ing", "prof", "st", "sto", "sta", "vs"},
    "pt": {"etc", "sr", "sra", "srta", "dr", "dra", "pág", "aprox", "núm", "art", "av", "vol", "cap", "ed",
           "fig", "gen", "prof", "st", "sto", "sta", "vs", "séc", "km", "kg", "cm"},
    "id": {"dll", "dsb", "dkk", "dst", "yg", "tsb", "dr", "kab", "kec", "jl", "no", "st", "hlm", "sdr",
           "ir", "prof", "drs", "kol", "jend", "letjen", "mayjen", "brigjen", "km", "kg", "cm", "vs"},
}
MIN_WORDS, MAX_WORDS = 6, 30
HI_MIN_WORDS = 5
TH_MIN_CHARS, TH_MAX_CHARS = 25, 150
SPLIT = re.compile(r"(?<=[.?!])\s+")
BAD_MARKS = re.compile(r"[,.?!¿¡]{2,}|\s[,.?!]|[¿¡]\s|-[,.?!]|[,.?!¿¡]-")

# Devanagari block without digits ०-९ (0966-096F), danda/double danda (0964/0965) and ॰ (0970).
HI_CHARS = "ऀ-ॣॱ-ॿ"
HI_ALLOWED = re.compile(rf"^[{HI_CHARS} ,.?!\-]+$")
HI_WORD = re.compile(rf"^[{HI_CHARS}]+(-[{HI_CHARS}]+)*$")
HI_VOWEL = re.compile(r"[ऄ-औॠॡॲ-ॷ]")
HI_CONS = re.compile(r"[क-हक़-य़ॸ-ॿ](?!़?्)")
# Thai letters and signs without ฯ (0E2F), ฿ (0E3F) and digits (0E50-0E59); ๆ (0E46) stays.
TH_ALLOWED = re.compile(r"^[ก-ฮะ-ฺเ-๎]+$")
TH_COMBINING = re.compile(r"[ัิ-ฺ็-๎]")
TH_BAD_START = re.compile(r"^[ัิ-ฺๅ-๎]")
TH_JOIN_MAIYAMOK = re.compile(r"\s+ๆ")


class _Latin:
    def __init__(self, lang: str) -> None:
        self.lang = lang
        letters = LATIN_LETTERS[lang]
        marks = ",.?!¿¡" if lang == "es" else ",.?!"
        self.allowed = re.compile(rf"^[{letters} {marks}\-]+$")
        self.word = re.compile(rf"^[{letters}]+(-[{letters}]+)*$")
        self.vowel_group = re.compile(rf"[{VOWELS[lang]}]+")


_LATIN = {lang: _Latin(lang) for lang in LATIN_LETTERS}


def prepare(paragraph: str, lang: str) -> str:
    if lang == "hi":
        return paragraph.replace("।", ".")
    if lang == "th":
        return TH_JOIN_MAIYAMOK.sub("ๆ", paragraph)
    return paragraph


def split_sentences(paragraph: str, lang: str) -> list[str]:
    paragraph = prepare(paragraph, lang).strip()
    if lang == "th":
        chunks = paragraph.split(" ")
        plain = [bool(TH_ALLOWED.match(c)) for c in chunks]
        return [c for i, c in enumerate(chunks)
                if plain[i] and (i == 0 or plain[i - 1]) and (i + 1 == len(chunks) or plain[i + 1])]
    return [s.strip() for s in SPLIT.split(paragraph) if s.strip()]


def unit_count(text: str, lang: str) -> int:
    """Syllables (es/pt/id), aksharas (hi) or spacing characters (th)."""
    if lang == "th":
        return len(TH_ALLOWED.sub("", "")) + sum(1 for c in text if "ก" <= c <= "๛"
                                                   and not TH_COMBINING.match(c))
    if lang == "hi":
        return len(HI_VOWEL.findall(text)) + len(HI_CONS.findall(text))
    return len(_LATIN[lang].vowel_group.findall(text))


def seconds(text: str, lang: str) -> float:
    return unit_count(text, lang) / RATE[lang]


def _accept_latin(s: str, lang: str) -> bool:
    spec = _LATIN[lang]
    if not spec.allowed.match(s) or s[-1] not in ".?!" or BAD_MARKS.search(s):
        return False
    if lang == "es" and (("¿" in s) != ("?" in s) or ("¡" in s and "!" not in s)):
        return False
    words = s.split()
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        return False
    for i, w in enumerate(words):
        core = w.strip(",.?!¿¡")
        if not spec.word.match(core):
            return False
        if sum(c.isupper() for c in core) >= 2 or (i > 0 and len(core) == 1 and core.isupper()):
            return False
        if core.lower() in ABBREV[lang] and w.endswith("."):
            return False
    first = words[0].lstrip("¿¡")
    return first[:1].isupper()


def _accept_hi(s: str) -> bool:
    if not HI_ALLOWED.match(s) or s[-1] not in ".?!" or BAD_MARKS.search(s):
        return False
    words = s.split()
    if not HI_MIN_WORDS <= len(words) <= MAX_WORDS:
        return False
    return all(HI_WORD.match(w.strip(",.?!")) for w in words)


def _accept_th(s: str) -> bool:
    return (bool(TH_ALLOWED.match(s)) and not TH_BAD_START.match(s)
            and TH_MIN_CHARS <= len(s) <= TH_MAX_CHARS)


def accept(sentence: str, lang: str) -> bool:
    if not sentence or "  " in sentence:
        return False
    if lang == "th":
        return _accept_th(sentence)
    if lang == "hi":
        return _accept_hi(sentence)
    return _accept_latin(sentence, lang)
