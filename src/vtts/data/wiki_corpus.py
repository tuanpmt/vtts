"""Sentence selection for speech synthesis from Wikipedia: Spanish, Indonesian, Brazilian
Portuguese, Thai, Hindi, French, German, Italian, Turkish, Russian,
Polish, Arabic, Dutch, Swedish and Norwegian (Bokmål).

Only plain text that needs no normalization before synthesis is kept (no digits, brackets,
symbols, acronyms or foreign scripts); nothing else is filtered.

- es, pt, id, de, ru, pl: letters of the language, spaces, intra-word hyphens and , . ? ! (es also ¿ ¡),
  6-30 words, starting with a capital letter (after ¿ ¡ in es) and ending with . ? !. Words with
  two or more capitals (acronyms, Roman numerals), single capital letters after the first word
  (initials) and common abbreviations are rejected. de also rejects any one-letter word with a
  final dot (z. B., d. h., u. a.).
- nl, sv, no: as es/pt/id with the letters of the language (nl é ë ï ö ü è á ó ú í à ê ç, sv å ä ö é,
  no æ ø å é è ò ô ó); a one-letter word with a final dot (initials, o. a.) is also rejected. no is the
  Bokmål Wikipedia. sv rejects the generated stubs of the Swedish Wikipedia (Lsjbot: species,
  municipalities, bays, climate and land-use sentences; SV_BOT).
- hi: Devanagari letters and signs (no Devanagari digits), spaces, intra-word hyphens and , . ? !,
  5-30 words, ending with . ? !. The danda । is converted to "." before splitting, so every Hindi
  row ends with . ? ! like the other languages; double danda ॥ is rejected.
- ar: Arabic letters (hamza forms, ة ى; no Arabic or Persian digits, no tatweel), optional
  vowel marks, spaces and the marks ، . ؟ ! (also , ?), 5-30 words, ending with . ؟ ! (or ?).
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
- fr: as es/pt, plus the apostrophe of elision inside words (l'école, aujourd'hui; the typographic
  apostrophe ’ becomes '), and the space or no-break space French puts before ? ! is removed
  first ("Qui est-ce ?" -> "Qui est-ce?"); capitals are counted per part of a word split at '
  and - (L'Europe, Saint-Étienne are accepted; ONU, XIVe are not).
- it, tr: as es/pt, and an apostrophe may join two parts of a word (Italian elision l'anno,
  dell'arte; Turkish suffixes after a proper noun İstanbul'da); the capital and abbreviation
  checks are on the longest part.
- fi: Finnish letters (a-z, å ä ö, š ž of loanwords), as es/pt/id; abbreviations (esim., jne., ns.,
  mm., ym., n., v., eKr., jKr. ...) end no accepted sentence.
- el: Greek letters (with tonos and dialytika), spaces, intra-word hyphens and , . ; !, as es/pt/id;
  the Greek question mark is ";" (U+037E is folded to ";" by NFC). Sentences end with . ; ! and
  are split there; the ano teleia · and Greek numerals with the keraia ʹ are rejected (not
  letters); abbreviations (κλπ., δηλ., αι., σελ. ...) end no accepted sentence.
- All languages: a double space (content removed by the dump) rejects the sentence.

Duration estimates (read speech):
- es 6.0, pt 5.5, id 5.5, ms 5.5, tl 5.5, sw 5.5, it 6.0, tr 6.0, de 5.0 syllables/s, syllables
  counted as vowel groups (ms as id; German ei, ie, au, eu, äu are one group; German syllables are
  heavier, hence the lower rate).
- tl words may hold an apostrophe between letters (contractions: dalawampu't, ako'y).
- sw words may hold an apostrophe only in ng' before a vowel (ng'ombe).
- nl 5.5, sv 5.0, no 5.0 syllables/s, syllables counted as vowel groups (Dutch aa ee oe ie ui eu ou
  ij are one group).
- hi 6.0 aksharas/s (independent vowels plus consonants not followed by virama).
- fr 6.2 vowel groups/s: French is read at about 5.5 syllables/s and the vowel groups of the
  spelling also count silent final e (école: 3 groups, 2 syllables): 1.13 groups per eSpeak-NG
  syllable on 500 French Wikipedia sentences.
- ru 5.5 syllables/s (every vowel letter); pl 6.0 syllables/s (vowel groups, the i of ci si zi
  ni dzi before a vowel not counted).
- ar 9.5 letters/s (vowel marks not counted): about 5.1 syllables/s at 1.86 letters per syllable
  (the ratio of the ar front-end's syllables on Arabic Wikipedia text).
- fi 5.5 syllables/s, el 6.0 syllables/s (vowel groups; Greek vowel digraphs count as one).
- th 13 spacing characters/s (Thai characters without the combining vowel and tone marks,
  about 2.5 per syllable at about 5.2 syllables/s).
"""

from __future__ import annotations

import re

LANGS = ("es", "id", "pt", "th", "hi", "fr", "de", "it", "tr", "ru", "pl", "ar", "fi", "el", "nl", "sv", "no")
LATIN_LETTERS = {
    "es": "a-zA-ZáéíóúüñÁÉÍÓÚÜÑ",
    "pt": "a-zA-ZáâãàçéêíóôõúÁÂÃÀÇÉÊÍÓÔÕÚ",
    "id": "a-zA-Z",
    "nl": "a-zA-ZéëïöüèáóúíàêçÉËÏÖÜÈÁÓÚÍ",
    "sv": "a-zA-ZåäöéÅÄÖÉ",
    "no": "a-zA-ZæøåéèòôóÆØÅÉ",
    "fr": "a-zA-ZàâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ",
    "de": "a-zA-ZäöüßÄÖÜ",
    "it": "a-zA-ZàèéìíòóùÀÈÉÌÍÒÓÙ",
    "tr": "a-zA-ZçğıöşüâîûÇĞİÖŞÜÂÎÛ",
    "pl": "a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "fi": "a-zA-ZåäöšžÅÄÖŠŽ",
    "el": "ΆΈ-ΊΌΎ-ΡΣ-ώ",
}
CYRILLIC_LETTERS = {"ru": "а-яА-ЯёЁ"}
VOWELS = {
    "es": "aeiouáéíóúüAEIOUÁÉÍÓÚÜ",
    "pt": "aeiouáâãàéêíóôõúAEIOUÁÂÃÀÉÊÍÓÔÕÚ",
    "id": "aeiouAEIOU",
    "nl": "aeiouyéëïöüèáóúíàêAEIOUYÉËÏÖÜÈÁÓÚÍ",
    "sv": "aeiouyåäöéAEIOUYÅÄÖÉ",
    "no": "aeiouyæøåéèòôóAEIOUYÆØÅÉ",
    "fr": "aeiouyàâæéèêëîïôœùûüÿAEIOUYÀÂÆÉÈÊËÎÏÔŒÙÛÜŸ",
    "de": "aeiouyäöüAEIOUYÄÖÜ",
    "it": "aeiouàèéìíòóùAEIOUÀÈÉÌÍÒÓÙ",
    "tr": "aeıioöuüâîûAEIİOÖUÜÂÎÛ",
    "ru": "аеёиоуыэюяАЕЁИОУЫЭЮЯ",
    "pl": "aeiouyąęóAEIOUYĄĘÓ",
    "fi": "aeiouyåäöAEIOUYÅÄÖ",
    "el": "αεηιουωάέήίόύώϊϋΐΰΑΕΗΙΟΥΩΆΈΉΊΌΎΏΪΫ",
}
RATE = {"es": 6.0, "pt": 5.5, "id": 5.5, "hi": 6.0, "th": 13.0, "fr": 6.2, "de": 5.0, "it": 6.0, "tr": 6.0, "ru": 5.5,
        "pl": 6.0, "ar": 9.5, "fi": 5.5, "el": 6.0, "nl": 5.5, "sv": 5.0,
        "no": 5.0}
ABBREV = {
    "es": {"etc", "sr", "sra", "srta", "dr", "dra", "ud", "uds", "pág", "aprox", "núm", "art", "av", "vol",
           "cap", "ed", "fig", "gral", "lic", "ing", "prof", "st", "sto", "sta", "vs"},
    "pt": {"etc", "sr", "sra", "srta", "dr", "dra", "pág", "aprox", "núm", "art", "av", "vol", "cap", "ed",
           "fig", "gen", "prof", "st", "sto", "sta", "vs", "séc", "km", "kg", "cm"},
    "id": {"dll", "dsb", "dkk", "dst", "yg", "tsb", "dr", "kab", "kec", "jl", "no", "st", "hlm", "sdr",
           "ir", "prof", "drs", "kol", "jend", "letjen", "mayjen", "brigjen", "km", "kg", "cm", "vs"},
    "nl": {"bijv", "bv", "enz", "nr", "dr", "mr", "ir", "drs", "ing", "prof", "st", "ca", "jr", "sr", "km", "kg",
           "cm", "vs", "resp", "evt", "incl", "excl", "zgn", "zg", "blz", "afb", "vgl", "ong", "max", "min", "mln",
           "mld", "jh", "chr", "lat", "gr", "eng", "fr", "ned", "dhr", "mevr", "mw", "pag", "nl", "etc"},
    "sv": {"osv", "ca", "dvs", "nr", "st", "km", "kg", "cm", "dr", "prof", "kap", "jfr", "resp", "tel", "vs",
           "inkl", "exkl", "sk", "milj", "mdr", "kl", "bl", "ex", "max", "min", "sid", "nb", "fr", "etc",
           "mm", "ff", "eng", "lat", "jan", "feb", "aug", "sept", "okt", "nov", "dec", "tex", "ung"},
    "no": {"osv", "mv", "ca", "dvs", "nr", "st", "km", "kg", "cm", "dr", "prof", "kap", "jf", "resp", "tlf", "vs",
           "inkl", "ekskl", "mill", "mrd", "kl", "pga", "ifm", "iht", "mht", "evt", "ev", "etc", "bl", "eks",
           "max", "min", "sk", "ff", "eng", "lat", "jan", "feb", "aug", "sept", "okt", "nov", "des", "ang"},
    "fr": {"etc", "mme", "mlle", "mm", "dr", "pr", "st", "ste", "av", "bd", "apr", "env", "vol", "chap",
           "éd", "fig", "cf", "art", "p", "km", "kg", "cm", "vs", "hab", "max", "min", "réf"},
    "de": {"etc", "usw", "bzw", "ca", "dr", "nr", "str", "vgl", "evtl", "ggf", "inkl", "sog", "bspw", "prof",
           "st", "hl", "jh", "jhd", "geb", "gest", "mio", "mrd", "ev", "kath", "chr", "bzgl", "max", "min",
           "km", "kg", "cm", "ff", "abb", "bd", "hrsg", "jr", "sen", "jun", "vs", "allg", "insb", "zt",
           "ehem", "urspr", "lat", "griech", "engl", "franz", "ital", "span", "russ", "dt", "mhd", "ahd"},
    "it": {"ecc", "sig", "sigg", "dott", "prof", "pag", "pagg", "ca", "cfr", "es", "art", "vol", "cap",
           "ed", "fig", "st", "vs", "ss", "km", "kg", "cm", "avv", "ing", "arch", "on", "gen", "sec"},
    "tr": {"vb", "vs", "dr", "prof", "doç", "sf", "no", "yy", "km", "kg", "cm", "st", "av", "bkz", "örn",
           "yrd", "alb", "org", "gen", "sok", "cad", "mah", "s"},
    "ru": {"т", "е", "д", "п", "к", "н", "г", "гг", "в", "вв", "др", "пр", "см", "ул", "им", "проф",
           "акад", "стр", "рис", "ок", "англ", "лат", "обл", "пос", "дер", "руб", "коп", "тыс",
           "млн", "млрд", "км", "кг", "св", "ст", "род", "нем", "франц", "греч", "араб", "м", "с"},
    "pl": {"np", "tj", "itd", "itp", "ok", "tzw", "ul", "al", "pl", "dr", "prof", "mgr", "inż", "św",
           "r", "w", "zm", "ur", "km", "kg", "cm", "godz", "min", "zł", "gr", "tys", "mln", "mld",
           "ang", "łac", "niem", "franc", "m", "in", "wg", "por", "zob", "ks", "gen", "płk", "nr"},
    "fi": {"esim", "jne", "ns", "nk", "mm", "ym", "yms", "ks", "n", "v", "s", "ts", "vrt", "eaa", "jaa",
           "ekr", "jkr", "tri", "prof", "klo", "kpl", "milj", "mrd", "km", "kg", "cm", "os", "puh",
           "p", "t", "k", "l", "srk", "vt", "ry", "oy", "ab", "lk", "vk", "kk", "ma", "ti", "ke",
           "to", "pe", "la", "su", "huom", "mrs", "mr", "dr", "st", "vs"},
    "el": {"κλπ", "κτλ", "δηλ", "αι", "π", "μ", "χ", "σελ", "βλ", "κ", "στ", "εκ", "χλμ", "τηλ",
           "εκατ", "δισ", "χιλ", "περ", "αρ", "ν", "τ", "λ", "ο", "η", "αγ", "γεν", "οδ", "λεωφ",
           "υπ", "αν", "δρ", "καθ", "τμ", "πρβλ", "ελλ", "λατ", "αγγλ", "γαλλ", "γερμ", "ιταλ"},
}
# Polish i before a vowel after c s z n dz is a softness mark, not a syllable (ciasto: 2).
PL_SOFT_I = re.compile(r"(?<=[csznCSZN])i(?=[aeouyąęóAEOUYĄĘÓ])")
APOSTROPHE = ("it", "tr")  # an apostrophe inside a word: Italian elision, Turkish suffixes
# Malay: as Indonesian (letters a-z), 5.5 syllables/s.
LANGS = (*LANGS, "ms")
LATIN_LETTERS["ms"] = "a-zA-Z"
VOWELS["ms"] = "aeiouAEIOU"
RATE["ms"] = 5.5
ABBREV["ms"] = {"dll", "dsb", "dst", "yg", "dr", "jln", "jl", "no", "hlm", "sdn", "bhd", "en", "pn", "tn",
                "prof", "kg", "km", "cm", "sg", "bkt", "tg", "kpg", "bil", "vs", "spt", "drpd"}
# Where an apostrophe may stand inside a word (other languages: nowhere).
APOSTROPHE_RE: dict[str, re.Pattern] = {}
# Tagalog: letters a-z and ñ, contractions with an apostrophe (dalawampu't, ako'y), 5.5 syllables/s.
LANGS = (*LANGS, "tl")
LATIN_LETTERS["tl"] = "a-zA-ZñÑ'"
VOWELS["tl"] = "aeiouAEIOU"
RATE["tl"] = 5.5
ABBREV["tl"] = {"atbp", "gng", "bb", "dr", "sto", "sta", "st", "brgy", "bgy", "hen", "kgg", "blg", "pres",
                "sen", "gob", "kap", "engr", "atty", "sr", "jr", "km", "kg", "cm", "vs", "pp"}
APOSTROPHE_RE["tl"] = re.compile(r"^[^']+(?:'[^']+)*$")
# Swahili: letters a-z, the apostrophe only in ng' before a vowel (ng'ombe), 5.5 syllables/s.
LANGS = (*LANGS, "sw")
LATIN_LETTERS["sw"] = "a-zA-Z'"
VOWELS["sw"] = "aeiouAEIOU"
RATE["sw"] = 5.5
ABBREV["sw"] = {"nk", "km", "bw", "bi", "dkt", "prof", "mh", "slp", "kg", "cm", "vs", "sh"}
APOSTROPHE_RE["sw"] = re.compile(r"^(?:[^']|(?<=[Nn][Gg])'(?=[aeiouAEIOU]))+$")
# Phrases of the bot-generated Swedish stubs (Lsjbot), which make up about a quarter of the plain
# Swedish sentences.
SV_BOT = re.compile(
    r"\bingår i (?:släktet|familjen|ordningen|klassen|underordningen|divisionen|riket|stammen)\b"
    r"|\boch familjen\b|\briket (?:svampar|växter|djur)\b|\bär (?:ett|en) (?:släkte|art|familj) (?:av|inom|i)\b"
    r"|\bär en kommun i\b|\bnaturlig växtlighet\b|\blövskog\b|\bsavann\b|\bär en vik i\b"
    r"|\bsvenska databasen\b|\bomgivningarna runt\b|\btrakten runt\b|\bglesbefolkat\b|\btätbefolkat\b"
    r"|\bmedeltemperatur|\bnederbörd|\bjordbruksmark\b|\bår är det\b|\binvånare per kvadratkilometer\b"
    r"|\bmeter över havet\b|\bkvadratkilometer\b|\bär en (?:tätort|småort|ort|by|sjö|ö|udde|halvö|bergstopp"
    r"|kulle|ås|dal|slätt|flygplats|vattendrag|glaciär|ögrupp|fjärd|klippa|sund) i\b", re.IGNORECASE)
MIN_WORDS, MAX_WORDS = 6, 30
HI_MIN_WORDS = 5
TH_MIN_CHARS, TH_MAX_CHARS = 25, 150
SPLIT = re.compile(r"(?<=[.?!؟])\s+")
EL_SPLIT = re.compile(r"(?<=[.;!])\s+")
BAD_MARKS = re.compile(r"[,.?!;¿¡]{2,}|\s[,.?!;]|[¿¡]\s|-[,.?!;]|[,.?!;¿¡]-")

# Devanagari block without digits ०-९ (0966-096F), danda/double danda (0964/0965) and ॰ (0970).
HI_CHARS = "ऀ-ॣॱ-ॿ"
HI_ALLOWED = re.compile(rf"^[{HI_CHARS} ,.?!\-]+$")
HI_WORD = re.compile(rf"^[{HI_CHARS}]+(-[{HI_CHARS}]+)*$")
HI_VOWEL = re.compile(r"[ऄ-औॠॡॲ-ॷ]")
HI_CONS = re.compile(r"[क-हक़-य़ॸ-ॿ](?!़?्)")
# Arabic letters (0621-063A, 0641-064A) and vowel marks (064B-0652, 0670); no tatweel, no numerals.
AR_LETTERS = "\u0621-\u063a\u0641-\u064a"
AR_MARKS = "\u064b-\u0652\u0670"
AR_ALLOWED = re.compile(rf"^[{AR_LETTERS}{AR_MARKS} ،,.؟?!]+$")
AR_WORD = re.compile(rf"^[{AR_LETTERS}][{AR_LETTERS}{AR_MARKS}]*$")
AR_BAD_MARKS = re.compile(r"[،,.؟?!]{2,}|\s[،,.؟?!]")
# Thai letters and signs without ฯ (0E2F), ฿ (0E3F) and digits (0E50-0E59); ๆ (0E46) stays.
TH_ALLOWED = re.compile(r"^[ก-ฮะ-ฺเ-๎]+$")
TH_COMBINING = re.compile(r"[ัิ-ฺ็-๎]")
TH_BAD_START = re.compile(r"^[ัิ-ฺๅ-๎]")
TH_JOIN_MAIYAMOK = re.compile(r"\s+ๆ")
TH_TARGET = 60
FR_SPACE_BEFORE_MARK = re.compile(r"[ \u00a0\u202f]+(?=[?!])")

# European Portuguese markers (pt is used as Brazilian Portuguese).
_EU_AUX = (r"est(?:ar|ou|ás|á|amos|ão|ava|avas|ávamos|avam|ive|eve|ivemos|iveram|ivesse|ivessem"
           r"|aria|ariam|ará|arão|eja|ejam|ivera|ando|ado)"
           r"|and(?:ar|o|as|a|amos|am|ava|avam|ou|aram|ando)"
           r"|continu(?:ar|o|as|a|amos|am|ava|avam|ou|aram|ará|ariam|asse|ando)"
           r"|fic(?:ar|o|as|a|amos|am|ava|avam|ou|aram|ará|ariam|asse|ando)")
_NOT_INF = r"(?!(?:par|mar|lugar|favor|bordo|cargo)\b)"
EU_PROGRESSIVE = re.compile(rf"\b(?:{_EU_AUX}) a {_NOT_INF}[a-zà-ú]+(?:ar|er|ir|ôr|or)\b", re.IGNORECASE)
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
EU_WORD_RE = re.compile(rf"(?<![\w-])(?:{EU_WORDS}|{EU_SPELLING})(?![\w-])", re.IGNORECASE)
# Acute é/ó before m/n + vowel where Brazil writes ê/ô (económico, género, ténis, António).
EU_ACCENT = re.compile(r"[éóÉÓ](?=[mn][aeiouáéíóúâêôãõ])")


class _Latin:
    def __init__(self, lang: str) -> None:
        self.lang = lang
        letters = {**LATIN_LETTERS, **CYRILLIC_LETTERS}[lang]
        marks = {"es": ",.?!¿¡", "el": ",.;!"}.get(lang, ",.?!")
        self.ends = ".;!" if lang == "el" else ".?!"
        joins = "'\\-" if lang in APOSTROPHE or lang == "fr" else "\\-"
        self.allowed = re.compile(rf"^[{letters} {marks}{joins}]+$")
        self.word = re.compile(rf"^[{letters}]+([{joins}][{letters}]+)*$")
        self.vowel_group = re.compile(rf"[{VOWELS[lang]}]+")


_LATIN = {lang: _Latin(lang) for lang in (*LATIN_LETTERS, *CYRILLIC_LETTERS)}


def prepare(paragraph: str, lang: str) -> str:
    if lang == "hi":
        return paragraph.replace("।", ".")
    if lang == "th":
        return TH_JOIN_MAIYAMOK.sub("ๆ", paragraph)
    if lang == "fr":
        return FR_SPACE_BEFORE_MARK.sub("", paragraph.replace("’", "'"))
    if lang == "el":  # Greek question mark U+037E -> ";" (as NFC does)
        return paragraph.replace("\u037e", ";")
    if lang in APOSTROPHE_RE:  # dalawampu’t
        return paragraph.replace("’", "'")
    return paragraph


def split_sentences(paragraph: str, lang: str) -> list[str]:
    paragraph = prepare(paragraph, lang).strip()
    if lang == "th":
        return _thai_utterances(paragraph)
    split = EL_SPLIT if lang == "el" else SPLIT
    return [s.strip() for s in split.split(paragraph) if s.strip()]


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
    if lang == "ar":
        return len(re.findall(f"[{AR_LETTERS}]", text))
    if lang == "hi":
        return len(HI_VOWEL.findall(text)) + len(HI_CONS.findall(text))
    if lang == "ru":  # every vowel letter is a syllable (Россия: 3)
        return sum(ch in VOWELS["ru"] for ch in text)
    if lang == "pl":
        text = PL_SOFT_I.sub("", text)
    return len(_LATIN[lang].vowel_group.findall(text))


def seconds(text: str, lang: str) -> float:
    return unit_count(text, lang) / RATE[lang]


def _accept_latin(s: str, lang: str) -> bool:
    spec = _LATIN[lang]
    if not spec.allowed.match(s) or s[-1] not in spec.ends or BAD_MARKS.search(s):
        return False
    if lang == "es" and (("¿" in s) != ("?" in s) or ("¡" in s and "!" not in s)):
        return False
    words = s.split()
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        return False
    for i, w in enumerate(words):
        core = w.strip(",.?!;¿¡")
        if not spec.word.match(core):
            return False
        if lang == "fr":  # capitals per part of a word split at ' and - (L'Europe, Saint-Étienne)
            parts = re.split(r"['-]", core)
        elif lang in APOSTROPHE:  # l'Italia, İstanbul'da: the checks below are on the longest part
            parts = core.split("'")
            if any(sum(c.isupper() for c in p) >= 2 for p in parts):
                return False
            core = max(parts, key=len)
            parts = [core]
        else:
            parts = [core]
        if any(sum(c.isupper() for c in p) >= 2 for p in parts) or (i > 0 and len(core) == 1 and core.isupper()):
            return False
        if core.lower() in ABBREV[lang] and w.endswith("."):
            return False
        if lang == "de" and len(core) == 1 and w.endswith("."):
            return False
        if lang in APOSTROPHE_RE and "'" in core and not APOSTROPHE_RE[lang].match(core):
            return False
        if lang in ("nl", "sv", "no") and len(core) == 1 and w.endswith("."):
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


def _accept_ar(s: str) -> bool:
    if not AR_ALLOWED.match(s) or s[-1] not in ".؟?!" or AR_BAD_MARKS.search(s):
        return False
    words = s.split()
    if not HI_MIN_WORDS <= len(words) <= MAX_WORDS:
        return False
    return all(AR_WORD.match(w.rstrip("،,.؟?!")) for w in words)


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
    if lang == "ar":
        return _accept_ar(sentence)
    return _accept_latin(sentence, lang)


def accept(sentence: str, lang: str) -> bool:
    return (accept_plain(sentence, lang) and not (lang == "pt" and eu_portuguese(sentence))
            and not (lang == "sv" and SV_BOT.search(sentence)))
