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
- pt is used as Brazilian Portuguese: sentences with clear European-Portuguese markers are
  rejected (eu_portuguese): the progressive estar/andar/continuar/ficar + a + infinitive,
  EU-only vocabulary (concelho, comboio, ecrã, equipa, facto, registo, ficheiro ...), pre-1990
  or EU spellings with silent consonants (acção, actual, director, óptimo, sector ...) and EU
  acute accents before m/n where Brazil writes a circumflex (económico, género, ténis, António).
- th: Thai has no sentence punctuation and no spaces between words; spaces separate clauses and
  sentences. Paragraphs are split on single spaces (after joining the repetition mark ๆ to the
  word before it). A chunk is plain when it has only Thai letters and signs (no Thai digits,
  no ฯ). Runs of consecutive plain chunks of at most 150 characters are joined with a space into
  utterances of about 60-150 characters, never across another chunk or a paragraph break; a
  chunk next to a non-plain chunk (cut off by a number, a foreign word or content the dump
  removed) is dropped from its run. Utterances of 25-150 characters are kept. No final mark is
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
TH_TARGET = 60

# European Portuguese markers (pt is used as Brazilian Portuguese).
_EU_AUX = (r"est(?:ar|ou|ás|á|amos|ão|ava|avas|ávamos|avam|ive|eve|ivemos|iveram|ivesse|ivessem"
           r"|aria|ariam|ará|arão|eja|ejam|ivera|ando|ado)"
           r"|and(?:ar|o|as|a|amos|am|ava|avam|ou|aram|ando)"
           r"|continu(?:ar|o|as|a|amos|am|ava|avam|ou|aram|ará|ariam|asse|ando)"
           r"|fic(?:ar|o|as|a|amos|am|ava|avam|ou|aram|ará|ariam|asse|ando)")
_NOT_INF = r"(?!(?:par|mar|lugar|favor|bordo|cargo)\b)"
EU_PROGRESSIVE = re.compile(rf"\b(?:{_EU_AUX}) a {_NOT_INF}[a-zà-ú]+(?:ar|er|ir|ôr|or)\b", re.I)
EU_WORDS = (
    "banda desenhada|bandas desenhadas|concelhos?|freguesias?|autocarros?|comboios?|ecrãs?|écrans?"
    "|telemóve(?:l|is)|equipas?|casas? de banho|pequenos?-almoços?|raparigas?|frigoríficos?"
    "|sumos?(?! (?:sacerdote|pontífice))|talhos?|montras?|guarda-redes|golos?|relvados?"
    "|factos?|contactos?|contactar|contactou|registos?|ficheiros?|utilizador(?:es|a|as)?"
    "|planeamentos?|desportos?|desportiv[oa]s?|cancro|camião|camiões|autarquias?|bebés?"
    "|receção|receções|conceção|conceções|perceção|perceções|deteção|deteções"
    "|nomeadamente|aquando|connosco|dezasseis|dezassete|dezanove"
    "|regist(?:ar|ou|aram|ado|ada|ados|adas|ando)"
)
EU_SPELLING = (
    "acç(?:ão|ões)|accionistas?|actua(?:l|is|lmente|lidade|lizar|lizado|lizada|lização|lizações"
    "|ção|ções|r|ram|m|va|vam|ou)?|act[oa]s?|activ[oa]s?|activ(?:idade|idades|ista|istas|ar|ado|ada)"
    "|colectiv[oa]s?|colecç(?:ão|ões)|direcç(?:ão|ões)|direct(?:or|ores|ora|oras|o|a|os|as|amente)"
    "|eléctric[oa]s?|electricidade|electrónic[oa]s?|electr(?:ão|ões)|efectiv[oa]s?|efectivamente"
    "|efectu(?:ar|ou|aram|ado|ada|ados|adas)|exact[oa]s?|exactamente|object[oa]s?|objectiv[oa]s?"
    "|project[oa]s?|project(?:ar|ou|ado|ada)|selecç(?:ão|ões)|seleccion(?:ar|ou|aram|ado|ada|ados|adas)"
    "|protecç(?:ão|ões)|protector(?:es|a|as)?|correcç(?:ão|ões)|correct[oa]s?|correctamente"
    "|reacç(?:ão|ões)|redacç(?:ão|ões)|sector(?:es)?|arquitect[oa]s?|arquitectura|arquitectónic[oa]s?"
    "|óptim[oa]s?|adopç(?:ão|ões)|adopt(?:ar|ou|aram|ado|ada|ados|adas|ivo|iva)|baptismos?"
    "|baptiz(?:ar|ou|ado|ada)|baptista|egipto|excepto|excepç(?:ão|ões)|excepcional|excepcionalmente"
    "|tect[oa]s?|factor(?:es)?"
)
EU_WORD_RE = re.compile(rf"(?<![\w-])(?:{EU_WORDS}|{EU_SPELLING})(?![\w-])", re.I)
# Acute é/ó before m/n + vowel where Brazil writes ê/ô (económico, género, ténis, António).
EU_ACCENT = re.compile(r"[éóÉÓ](?=[mn][aeiouáéíóúâêôãõ])")


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
        return _thai_utterances(paragraph)
    return [s.strip() for s in SPLIT.split(paragraph) if s.strip()]


def _pack(run: list[str]) -> list[str]:
    """Join a run of plain Thai chunks (each <= TH_MAX_CHARS) into the fewest utterances of at
    most TH_MAX_CHARS characters, then as few characters short of TH_TARGET as possible."""
    n = len(run)
    best: list[tuple[int, int, int]] = [(0, 0, 0)] + [(n + 1, 0, 0)] * n  # (groups, shortfall², start)
    for i in range(1, n + 1):
        length = -1
        for j in range(i - 1, -1, -1):
            length += len(run[j]) + 1
            if length > TH_MAX_CHARS:
                break
            cand = (best[j][0] + 1, best[j][1] + max(0, TH_TARGET - length) ** 2, j)
            if cand[:2] < best[i][:2]:
                best[i] = cand
    out, i = [], n
    while i > 0:
        j = best[i][2]
        out.append(" ".join(run[j:i]))
        i = j
    return out[::-1]


def _thai_utterances(paragraph: str) -> list[str]:
    chunks = paragraph.split(" ")
    kind = ["plain" if TH_ALLOWED.match(c) and len(c) <= TH_MAX_CHARS
            else "long" if TH_ALLOWED.match(c) else "bad" for c in chunks]
    keep = [k == "plain" and (i == 0 or kind[i - 1] != "bad") and (i + 1 == len(chunks) or kind[i + 1] != "bad")
            for i, k in enumerate(kind)]
    out, run = [], []
    for c, k in zip(chunks, keep):
        if k:
            run.append(c)
            continue
        if run:
            out += _pack(run)
            run = []
    if run:
        out += _pack(run)
    return out


def eu_portuguese(sentence: str) -> bool:
    """True when the sentence has a clear European-Portuguese marker."""
    return bool(EU_PROGRESSIVE.search(sentence) or EU_WORD_RE.search(sentence) or EU_ACCENT.search(sentence))


def unit_count(text: str, lang: str) -> int:
    """Syllables (es/pt/id), aksharas (hi) or spacing characters (th)."""
    if lang == "th":
        return sum(1 for c in text if "\u0e01" <= c <= "\u0e5b" and not TH_COMBINING.match(c))
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
    return (all(TH_ALLOWED.match(c) for c in s.split(" ")) and not TH_BAD_START.match(s)
            and TH_MIN_CHARS <= len(s) <= TH_MAX_CHARS)


def accept_plain(sentence: str, lang: str) -> bool:
    """The readability rule only (no European-Portuguese check)."""
    if not sentence or "  " in sentence:
        return False
    if lang == "th":
        return _accept_th(sentence)
    if lang == "hi":
        return _accept_hi(sentence)
    return _accept_latin(sentence, lang)


def accept(sentence: str, lang: str) -> bool:
    return accept_plain(sentence, lang) and not (lang == "pt" and eu_portuguese(sentence))
