"""Versioned, spelling-based token inventory shared by teacher, student and C runtime.

Token ids are the index in TOKENS. Changing the order or contents requires a
new PHONEME_SET_VERSION.

Prefixes: O: onset, G: on-glide, N: nucleus, C: coda, T1..T6 tones in the order
ngang, huyền, sắc, hỏi, ngã, nặng. The set is dialect-neutral: spellings that
merge in Hanoi speech (tr/ch, s/x, r/d/gi) stay distinct tokens.
"""

PHONEME_SET_VERSION = "1"

PAD, BOS, EOS, SPACE = "<pad>", "<bos>", "<eos>", " "
PUNCTUATION = (",", ".", "?", "!", ";", ":")

ONSETS = ("b", "k", "ch", "d", "đ", "g", "gi", "h", "kh", "l", "m", "n", "ng", "nh",
          "p", "ph", "r", "s", "t", "th", "tr", "v", "x")
NUCLEI = ("a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "iê", "uô", "ươ", "oo")
CODAS = ("c", "ch", "m", "n", "ng", "nh", "p", "t", "j", "w")
TONE_COUNT = 6

TOKENS: tuple[str, ...] = (
    (PAD, BOS, EOS, SPACE)
    + PUNCTUATION
    + tuple(f"O:{o}" for o in ONSETS)
    + ("G:w",)
    + tuple(f"N:{n}" for n in NUCLEI)
    + tuple(f"C:{c}" for c in CODAS)
    + tuple(f"T{i}" for i in range(1, TONE_COUNT + 1))
)
VOCAB_SIZE = len(TOKENS)

_TOKEN_TO_ID = {tok: i for i, tok in enumerate(TOKENS)}


def token_to_id(tok: str) -> int:
    return _TOKEN_TO_ID[tok]


def id_to_token(i: int) -> str:
    return TOKENS[i]


# ---------------- version 2: Vietnamese + English (ids 0..64 unchanged) ----------------
# English uses the 39 ARPAbet phonemes (CMUdict); a stress token S0/S1/S2 follows each vowel,
# the way a tone token follows each Vietnamese syllable.

PHONEME_SET_VERSION_V2 = "2"
ARPABET = ("AA", "AE", "AH", "AO", "AW", "AY", "B", "CH", "D", "DH", "EH", "ER", "EY", "F", "G",
           "HH", "IH", "IY", "JH", "K", "L", "M", "N", "NG", "OW", "OY", "P", "R", "S", "SH", "T",
           "TH", "UH", "UW", "V", "W", "Y", "Z", "ZH")
ARPABET_VOWELS = frozenset(("AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY",
                            "OW", "OY", "UH", "UW"))
STRESS = ("S0", "S1", "S2")

TOKENS_V2: tuple[str, ...] = TOKENS + tuple(f"EN:{p}" for p in ARPABET) + STRESS
VOCAB_SIZE_V2 = len(TOKENS_V2)

_TOKEN_TO_ID_V2 = {tok: i for i, tok in enumerate(TOKENS_V2)}


def token_to_id_v2(tok: str) -> int:
    return _TOKEN_TO_ID_V2[tok]


# ---------------- token set "zh-en": Mandarin + English (ids 0..106 = v2 unchanged) ----------------
# A model uses only the ids of its pair; the Vietnamese rows (8..64) stay unused by zh-en models
# so that the English rows (65..106) can be warm-started from a vi-en teacher. Mandarin syllables
# are [ZI:initial] ZF:final ZTtone; finals are written in full (iou, uei, uen; v for u-umlaut),
# "ii" is the apical vowel after zh/ch/sh/r and "i0" after z/c/s. Tone 5 is the neutral tone.

TOKEN_SET_V2 = "vi-en"
TOKEN_SET_ZHEN = "zh-en"

ZH_INITIALS = ("b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x",
               "zh", "ch", "sh", "r", "z", "c", "s")
ZH_FINALS = ("a", "o", "e", "ai", "ei", "ao", "ou", "an", "en", "ang", "eng", "ong", "er",
             "i", "ia", "ie", "iao", "iou", "ian", "in", "iang", "ing", "iong",
             "u", "ua", "uo", "uai", "uei", "uan", "uen", "uang", "ueng",
             "v", "ve", "van", "vn", "ii", "i0")
ZH_TONE_COUNT = 5

TOKENS_ZHEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"ZI:{i}" for i in ZH_INITIALS)
    + tuple(f"ZF:{f}" for f in ZH_FINALS)
    + tuple(f"ZT{i}" for i in range(1, ZH_TONE_COUNT + 1))
)
VOCAB_SIZE_ZHEN = len(TOKENS_ZHEN)

TOKEN_SETS: dict[str, tuple[str, ...]] = {TOKEN_SET_V2: TOKENS_V2, TOKEN_SET_ZHEN: TOKENS_ZHEN}

_TOKEN_TO_ID_ZHEN = {tok: i for i, tok in enumerate(TOKENS_ZHEN)}


def token_to_id_zhen(tok: str) -> int:
    return _TOKEN_TO_ID_ZHEN[tok]


# ---------------- token set "ko-en": Korean + English (ids 0..106 = v2 unchanged) ----------------
# Phoneme-level tokens after the standard pronunciation rules (src/vtts/frontend/ko/): a syllable
# is [KO:I:onset] KO:V:vowel [KO:C:coda]. The silent onset ㅇ has no token; vowels include the
# glides (ya, wa, ui, ...); codas are the 7 coda sounds. Names are romanized (Revised Romanization
# letters; ㄹ is "r" as an onset and "l" as a coda). Korean has no lexical tone.

TOKEN_SET_KOEN = "ko-en"

KO_ONSETS = ("g", "kk", "k", "d", "tt", "t", "b", "pp", "p", "s", "ss", "j", "jj", "ch", "h",
             "n", "m", "r")
KO_VOWELS = ("a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u",
             "wo", "we", "wi", "yu", "eu", "ui", "i")
KO_CODAS = ("k", "n", "t", "l", "m", "p", "ng")

TOKENS_KOEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"KO:I:{o}" for o in KO_ONSETS)
    + tuple(f"KO:V:{v}" for v in KO_VOWELS)
    + tuple(f"KO:C:{c}" for c in KO_CODAS)
)
VOCAB_SIZE_KOEN = len(TOKENS_KOEN)

TOKEN_SETS[TOKEN_SET_KOEN] = TOKENS_KOEN

_TOKEN_TO_ID_KOEN = {tok: i for i, tok in enumerate(TOKENS_KOEN)}


def token_to_id_koen(tok: str) -> int:
    return _TOKEN_TO_ID_KOEN[tok]


# ---------------- token set "ja-en": Japanese + English (ids 0..106 = v2 unchanged) ----------------
# Phonemes in the style of Open JTalk (src/vtts/frontend/ja/): a mora is [JA:consonant] JA:vowel,
# or JA:N (moraic nasal ん) or JA:cl (geminate っ). Palatalized consonants are one token (ky, sh,
# ch, j, ...); ts f v ty dy serve loanword kana (ツァ ファ ヴァ テュ デュ). A long vowel is the vowel repeated (トー -> t o o), not a
# separate token. Devoiced vowels and pitch accent are not marked in version 1.

TOKEN_SET_JAEN = "ja-en"

JA_VOWELS = ("a", "i", "u", "e", "o")
JA_CONSONANTS = ("k", "g", "s", "z", "t", "d", "n", "h", "b", "p", "m", "y", "r", "w",
                 "ky", "gy", "sh", "j", "ch", "ny", "hy", "by", "py", "my", "ry",
                 "ts", "f", "v", "ty", "dy")
JA_SPECIAL = ("N", "cl")

TOKENS_JAEN: tuple[str, ...] = (
    TOKENS_V2 + tuple(f"JA:{p}" for p in JA_VOWELS + JA_CONSONANTS + JA_SPECIAL)
)
VOCAB_SIZE_JAEN = len(TOKENS_JAEN)

TOKEN_SETS[TOKEN_SET_JAEN] = TOKENS_JAEN

_TOKEN_TO_ID_JAEN = {tok: i for i, tok in enumerate(TOKENS_JAEN)}


def token_to_id_jaen(tok: str) -> int:
    return _TOKEN_TO_ID_JAEN[tok]


# ---------------- token set "es-en": Spanish + English (ids 0..106 = v2 unchanged) ----------------
# Phonemes from the spelling rules of src/vtts/frontend/es/: vowels, the same vowels stressed
# (a1 = stressed a), the glides of diphthongs (j as in "tiene", w as in "bueno") and consonants.
# Dialect-neutral like the Vietnamese set: spellings that merge in some dialects stay distinct
# (th = c/z as in "cielo", "zapato" vs s; ll vs y). b/v are one phoneme; allophones (b d g
# spirantized, n assimilated) are left to the model.

TOKEN_SET_ESEN = "es-en"

ES_VOWELS = ("a", "e", "i", "o", "u")
ES_GLIDES = ("j", "w")
ES_CONSONANTS = ("p", "b", "t", "d", "k", "g", "f", "th", "s", "x", "ch", "y", "ll", "m", "n",
                 "ny", "l", "r", "rr")

TOKENS_ESEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"ES:{v}" for v in ES_VOWELS)
    + tuple(f"ES:{v}1" for v in ES_VOWELS)
    + tuple(f"ES:{c}" for c in ES_GLIDES + ES_CONSONANTS)
)
VOCAB_SIZE_ESEN = len(TOKENS_ESEN)

TOKEN_SETS[TOKEN_SET_ESEN] = TOKENS_ESEN


# ---------------- token set "id-en": Indonesian + English (ids 0..106 = v2 unchanged) ----------------
# Phonemes from the spelling rules of src/vtts/frontend/id/: six vowels (e = the e of "enak",
# @ = the schwa of "besar"), the stressed vowels (the schwa is never stressed) and consonants
# (? = glottal stop: final k, apostrophe; sy, kh for loanwords; v is read f).

TOKEN_SET_IDEN = "id-en"

ID_VOWELS = ("a", "i", "u", "e", "@", "o")
ID_STRESSED = ("a", "i", "u", "e", "o")
ID_CONSONANTS = ("p", "b", "t", "d", "k", "g", "?", "c", "j", "f", "s", "z", "sy", "kh", "h", "m",
                 "n", "ny", "ng", "l", "r", "w", "y")

TOKENS_IDEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"ID:{v}" for v in ID_VOWELS)
    + tuple(f"ID:{v}1" for v in ID_STRESSED)
    + tuple(f"ID:{c}" for c in ID_CONSONANTS)
)
VOCAB_SIZE_IDEN = len(TOKENS_IDEN)

TOKEN_SETS[TOKEN_SET_IDEN] = TOKENS_IDEN


# ---------------- token set "pt-en": Brazilian Portuguese + English (ids 0..106 = v2 unchanged) ----
# Phonemes from the spelling rules of src/vtts/frontend/pt/: oral vowels, nasal vowels (an en in
# on un), the stressed vowels with open E/O (é, ó), the glides j/w of diphthongs and nasal
# diphthongs (pai, mão, bem) and consonants (sh zh nh lh; r = the tap of "caro", rr = the strong r
# of "carro", "rio" and of a syllable-final r). Final unstressed e/o are written i/u (leite, carro);
# t/d before i and syllable-final l are left to the voice (palatalized, vocalized in Brazil).

TOKEN_SET_PTEN = "pt-en"

PT_VOWELS = ("a", "e", "i", "o", "u")
PT_STRESSED = ("a", "e", "E", "i", "o", "O", "u")
PT_NASALS = ("an", "en", "in", "on", "un")
PT_CONSONANTS = ("j", "w", "p", "b", "t", "d", "k", "g", "f", "v", "s", "z", "sh", "zh", "m", "n",
                 "nh", "l", "lh", "r", "rr")

TOKENS_PTEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"PT:{v}" for v in PT_VOWELS)
    + tuple(f"PT:{v}1" for v in PT_STRESSED)
    + tuple(f"PT:{v}" for v in PT_NASALS)
    + tuple(f"PT:{v}1" for v in PT_NASALS)
    + tuple(f"PT:{c}" for c in PT_CONSONANTS)
)
VOCAB_SIZE_PTEN = len(TOKENS_PTEN)

TOKEN_SETS[TOKEN_SET_PTEN] = TOKENS_PTEN


# ---------------- token set "hi-en": Hindi + English (ids 0..106 = v2 unchanged) ----------------
# Phonemes from the Devanagari rules of src/vtts/frontend/hi/ (schwa deletion applied). Vowels: a
# (the schwa of अ), aa i ii u uu e, ai (ऐ, also ॅ), o, au (औ, also ऑ); "~" nasalizes the vowel
# before it (chandrabindu, anusvara before a non-stop or after a long vowel). Consonants in ITRANS
# style: c ch = च छ, T Th D Dh N = retroflex ट ठ ड ढ ण, R Rh = the flaps ड़ ढ़, ng ny = ङ ञ, sh = श
# and ष (merged), q x G z f = the nukta consonants क़ ख़ ग़ ज़ फ़. ऋ is read r i; no stress.

TOKEN_SET_HIEN = "hi-en"

HI_VOWELS = ("a", "aa", "i", "ii", "u", "uu", "e", "ai", "o", "au")
HI_NASAL = "~"
HI_CONSONANTS = ("k", "kh", "g", "gh", "ng", "c", "ch", "j", "jh", "ny",
                 "T", "Th", "D", "Dh", "N", "t", "th", "d", "dh", "n",
                 "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "sh", "s", "h",
                 "R", "Rh", "q", "x", "G", "z", "f")

TOKENS_HIEN: tuple[str, ...] = (
    TOKENS_V2 + tuple(f"HI:{p}" for p in HI_VOWELS + (HI_NASAL,) + HI_CONSONANTS)
)
VOCAB_SIZE_HIEN = len(TOKENS_HIEN)

TOKEN_SETS[TOKEN_SET_HIEN] = TOKENS_HIEN


# ---------------- token set "th-en": Thai + English (ids 0..106 = v2 unchanged) ----------------
# Phonemes from the spelling rules of src/vtts/frontend/th/: a syllable is TH:I:initial
# [TH:I:second consonant of a cluster] TH:V:vowel [TH:F:final] TH:Ttone. Initials are the 21
# initial sounds (? = the glottal stop of อ); vowels are the nine monophthongs short and long
# (ue = ɯ, ae = ɛ, or = ɔ, oe = ɤ; doubled letters = long) and the diphthongs ia, uea, ua; finals
# are the six final sounds k p t m n ng and the glides w j. Tones T1..T5: mid, low, falling, high,
# rising (สามัญ เอก โท ตรี จัตวา).

TOKEN_SET_THEN = "th-en"

TH_INITIALS = ("p", "ph", "b", "t", "th", "d", "k", "kh", "c", "ch", "?", "m", "n", "ng", "f",
               "s", "h", "j", "r", "l", "w")
TH_VOWELS = ("a", "aa", "i", "ii", "ue", "uue", "u", "uu", "e", "ee", "ae", "aae", "o", "oo",
             "or", "oor", "oe", "ooe", "ia", "uea", "ua")
TH_FINALS = ("k", "p", "t", "m", "n", "ng", "w", "j")
TH_TONE_COUNT = 5

TOKENS_THEN: tuple[str, ...] = (
    TOKENS_V2
    + tuple(f"TH:I:{c}" for c in TH_INITIALS)
    + tuple(f"TH:V:{v}" for v in TH_VOWELS)
    + tuple(f"TH:F:{c}" for c in TH_FINALS)
    + tuple(f"TH:T{i}" for i in range(1, TH_TONE_COUNT + 1))
)
VOCAB_SIZE_THEN = len(TOKENS_THEN)

TOKEN_SETS[TOKEN_SET_THEN] = TOKENS_THEN


# ---------------- text modes of the pair token sets ----------------
# text_to_ids(text, mode) with a pair mode returns ids of that mode's token set; the modes vi, en
# and auto use vi-en. A new pair adds its token set above, one entry here, its language module
# (languages.py) and its tagging rule (lang.py).

PAIR_MODES: dict[str, str] = {"zh": TOKEN_SET_ZHEN, "ko": TOKEN_SET_KOEN, "ja": TOKEN_SET_JAEN,
                              "es": TOKEN_SET_ESEN, "id": TOKEN_SET_IDEN,
                              "pt": TOKEN_SET_PTEN, "th": TOKEN_SET_THEN, "hi": TOKEN_SET_HIEN}

_TOKEN_INDEX: dict[str, dict[str, int]] = {}


def token_index(token_set: str) -> dict[str, int]:
    """token -> id in a token set of TOKEN_SETS."""
    if token_set not in _TOKEN_INDEX:
        _TOKEN_INDEX[token_set] = {tok: i for i, tok in enumerate(TOKEN_SETS[token_set])}
    return _TOKEN_INDEX[token_set]
