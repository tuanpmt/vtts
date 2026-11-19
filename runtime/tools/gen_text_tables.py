"""Generate runtime/src/vtts_text_tables.h from the Python front-end (single source of truth).

Run: uv run python runtime/tools/gen_text_tables.py
"""

import unicodedata
from itertools import pairwise
from pathlib import Path

from vtts.frontend import lexicon, phoneme_set
from vtts.frontend.en import g2p_en, normalize_en
from vtts.frontend.syllable import _TONE_MARKS

OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_tables.h"

# internal single-byte codes for Vietnamese letters with quality marks
CODES = {"ă": "1", "â": "2", "ê": "3", "ô": "4", "ơ": "5", "ư": "6", "đ": "7"}
BASES = "abcdeghiklmnopqrstuvxyfjwz" + "ăâêôơưđ"


def letter_code(base: str) -> str:
    return CODES.get(base, base)


def c_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def c_list(name: str, items: list[str]) -> list[str]:
    out = [f"static const char *const {name}[{len(items)}] = {{"]
    out += ["    " + ", ".join(c_str(s) for s in items[i:i + 6]) + "," for i in range(0, len(items), 6)]
    return out + ["};", ""]


def english_tables() -> list[str]:
    """Tables of the English front-end (src/vtts/frontend/en), in the order Python applies them."""
    ne = normalize_en
    v2 = phoneme_set.token_to_id_v2
    out = ["/* ---- English (token set v2) ---- */",
           f"#define VTTS_V2_EN0 {v2('EN:' + phoneme_set.ARPABET[0])}",
           f"#define VTTS_V2_S0 {v2('S0')}",
           f"#define VTTS_V2_BOS {v2(phoneme_set.BOS)}",
           f"#define VTTS_V2_EOS {v2(phoneme_set.EOS)}",
           f"#define VTTS_V2_SPACE {v2(phoneme_set.SPACE)}",
           f"#define VTTS_V2_VOCAB {phoneme_set.VOCAB_SIZE_V2}", ""]
    out += c_list("VTTS_ARPABET", list(phoneme_set.ARPABET))
    vowels = sorted(phoneme_set.ARPABET.index(v) for v in phoneme_set.ARPABET_VOWELS)
    out += [f"static const uint8_t VTTS_ARPABET_VOWEL[{len(phoneme_set.ARPABET)}] = {{"
            + ", ".join("1" if i in vowels else "0" for i in range(len(phoneme_set.ARPABET))) + "};", ""]
    letters = [[v2(x) for x in g2p_en.letter_tokens(ch)] for ch in "abcdefghijklmnopqrstuvwxyz"]
    out += ["static const uint8_t VTTS_EN_LETTERS[26][12] = {"]
    out += ["    {" + ", ".join(map(str, [len(ids)] + ids)) + "}," for ids in letters]
    out += ["};", ""]
    out += c_list("VTTS_EN_ONES", ne.ONES) + c_list("VTTS_EN_TENS", ne.TENS) + c_list("VTTS_EN_MONTHS", ne.MONTHS)
    out += ["static const char *const VTTS_EN_ORD_IRREG[][2] = {"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ne.ORD_IRREG.items()] + ["};",
            f"#define VTTS_EN_N_ORD_IRREG {len(ne.ORD_IRREG)}", ""]
    out += ["static const char *const VTTS_EN_ABBREV[][2] = {  /* applied in this order */"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ne.ABBREV.items()] + ["};",
            f"#define VTTS_EN_N_ABBREV {len(ne.ABBREV)}", ""]
    units = sorted(ne.UNITS, key=len, reverse=True)  # the alternation order of the Python regex
    out += ["static const char *const VTTS_EN_UNITS[][2] = {  /* longest first */"]
    out += [f"    {{{c_str(k)}, {c_str(ne.UNITS[k])}}}," for k in units] + ["};",
            f"#define VTTS_EN_N_UNITS {len(units)}", ""]
    out += ["static const char *const VTTS_EN_UNIT_ONE[][2] = {"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ne.UNIT_ONE.items()] + ["};",
            f"#define VTTS_EN_N_UNIT_ONE {len(ne.UNIT_ONE)}", ""]
    out += ["static const struct { uint32_t cp; const char *one, *many, *sub1, *subn; } VTTS_EN_CURRENCY[] = {"]
    out += [f"    {{0x{ord(k):04X}, {', '.join(c_str(x) for x in v)}}}," for k, v in ne.CURRENCY.items()]
    out += ["};", f"#define VTTS_EN_N_CURRENCY {len(ne.CURRENCY)}", ""]
    return out


def chinese_tables() -> list[str]:
    """Token ids of the zh-en set and the strings of the Mandarin normalizer (zh/normalize_zh.py)."""
    from vtts.frontend.zh import normalize_zh as nz

    z = phoneme_set.token_to_id_zhen
    out = ["/* ---- Mandarin (token set zh-en; ids 0..106 are the v2 ids) ---- */",
           f"#define VTTS_ZHEN_ZI0 {z('ZI:' + phoneme_set.ZH_INITIALS[0])}  /* + initial index */",
           f"#define VTTS_ZHEN_ZF0 {z('ZF:' + phoneme_set.ZH_FINALS[0])}  /* + final index */",
           f"#define VTTS_ZHEN_ZT1 {z('ZT1')}  /* + tone - 1 */",
           f"#define VTTS_ZH_N_INITIALS {len(phoneme_set.ZH_INITIALS)}",
           f"#define VTTS_ZH_N_FINALS {len(phoneme_set.ZH_FINALS)}",
           f"#define VTTS_ZH_N_TONES {phoneme_set.ZH_TONE_COUNT}",
           f"#define VTTS_ZHEN_VOCAB {phoneme_set.VOCAB_SIZE_ZHEN}", ""]
    out += c_list("VTTS_ZH_DIGITS", list(nz.DIGITS))
    out += c_list("VTTS_ZH_SECTION_UNITS", [u for _, u in nz._SECTION_UNITS])
    out += c_list("VTTS_ZH_GROUP_UNITS", list(nz._GROUP_UNITS))
    extra = {k: v for k, v in nz._FULLWIDTH.items() if not 0xFF01 <= k < 0xFF5F}
    assert all(nz._FULLWIDTH[c] == c - 0xFEE0 for c in range(0xFF01, 0xFF5F))
    out += ["/* full-width forms: U+FF01..U+FF5E -> minus 0xFEE0, plus these */",
            "static const uint32_t VTTS_ZH_FULLWIDTH[][2] = {"]
    out += [f"    {{0x{k:04X}, 0x{v:04X}}}," for k, v in extra.items()]
    out += ["};", f"#define VTTS_ZH_N_FULLWIDTH {len(extra)}", ""]
    out += ["static const char *const VTTS_ZH_SYMBOLS[][2] = {  /* replaced in this order */"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in nz._SYMBOLS.items()]
    out += ["};", f"#define VTTS_ZH_N_SYMBOLS {len(nz._SYMBOLS)}", ""]
    out += ["static const uint32_t VTTS_ZH_DROP[] = {  /* replaced by a space */"]
    drop = [f"0x{ord(c):04X}" for c in nz._DROP]
    out += ["    " + ", ".join(drop[i:i + 8]) + "," for i in range(0, len(drop), 8)]
    out += ["};", f"#define VTTS_ZH_N_DROP {len(drop)}", ""]
    out += ["static const struct { uint32_t cp; const char *name; } VTTS_ZH_CURRENCY[] = {"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nz.CURRENCY.items()]
    out += ["};", f"#define VTTS_ZH_N_CURRENCY {len(nz.CURRENCY)}", ""]
    return out


def korean_tables() -> list[str]:
    """Token ids of the ko-en set, the jamo tables of the pronunciation rules (ko/g2p_ko.py), the
    exception table (lexicons/ko/overrides.tsv) and the strings of the normalizer (ko/normalize_ko.py).

    Consonant jamo are coded as their compatibility code point - 0x3130 (ㄱ 1 .. ㅎ 30, 0 = none),
    vowels as their index in hangul.VOWELS (ㅏ 0 .. ㅣ 20, the Unicode order)."""
    from vtts.frontend.ko import g2p_ko as g
    from vtts.frontend.ko import hangul as h
    from vtts.frontend.ko import normalize_ko as nk

    k = phoneme_set.token_to_id_koen
    base = 0x3130

    def J(ch: str) -> int:
        if not ch:
            return 0
        v = ord(ch) - base
        assert 1 <= v <= 30, ch
        return v

    assert "".join(h.VOWELS) == "".join(chr(c) for c in range(0x314F, 0x3164))
    vowel = {v: i for i, v in enumerate(h.VOWELS)}
    n = 31

    def arr(name: str, ctype: str, vals: list[int], comment: str) -> list[str]:
        return [f"static const {ctype} {name}[{len(vals)}] = {{  /* {comment} */",
                "    " + ", ".join(map(str, vals)) + ",", "};", ""]

    def by_code(d: dict, f) -> list[int]:
        vals = [0] * n
        for key, v in d.items():
            vals[J(key)] = f(v)
        return vals

    out = ["/* ---- Korean (token set ko-en; ids 0..106 are the v2 ids) ---- */",
           f"#define VTTS_KOEN_VOCAB {phoneme_set.VOCAB_SIZE_KOEN}",
           f"#define VTTS_KO_JAMO0 0x{base:04X}  /* consonant code = compatibility jamo - this */", ""]
    out += arr("VTTS_KO_ONSETS", "uint8_t", [J(c) for c in h.ONSETS], "onset index (U+AC00 arithmetic) -> code")
    out += arr("VTTS_KO_CODAS", "uint8_t", [J(c) for c in h.CODAS], "coda index -> code (0 = none)")
    neutral = [255] * n
    for key, v in g.NEUTRAL.items():
        neutral[J(key)] = J(v)
    out += arr("VTTS_KO_NEUTRAL", "uint8_t", neutral, "NEUTRAL: coda code -> one of the 7 (255: not a coda)")
    liaison = [f"{{0, {c}}}" for c in range(n)]
    for key, (stay, move) in g.LIAISON.items():
        liaison[J(key)] = f"{{{J(stay)}, {J(move)}}}"
    out += [f"static const uint8_t VTTS_KO_LIAISON[{n}][2] = {{  /* LIAISON: (stays, moves); default (none, coda) */",
            "    " + ", ".join(liaison) + ",", "};", ""]
    asp = ["{0, 0, 0}"] * n
    for key, (stay, onset) in g.ASPIRATE_BEFORE_H.items():
        asp[J(key)] = f"{{1, {J(stay)}, {J(onset)}}}"
    out += [f"static const uint8_t VTTS_KO_ASP_H[{n}][3] = {{  /* ASPIRATE_BEFORE_H: (present, stays, onset) */",
            "    " + ", ".join(asp) + ",", "};", ""]
    out += arr("VTTS_KO_ASPIRATED", "uint8_t", by_code(g.ASPIRATED, J), "ASPIRATED (0: none)")
    hc = ["{0, 0}"] * n
    for key, rest in g.H_CODAS.items():
        hc[J(key)] = f"{{1, {J(rest)}}}"
    out += [f"static const uint8_t VTTS_KO_H_CODA[{n}][2] = {{  /* H_CODAS: (present, rest) */",
            "    " + ", ".join(hc) + ",", "};", ""]
    out += arr("VTTS_KO_TENSE", "uint8_t", by_code(g.TENSE, J), "TENSE (0: none)")
    out += arr("VTTS_KO_OBSTRUENT", "uint8_t", by_code({c: 1 for c in g.OBSTRUENT_CODAS}, int), "OBSTRUENT_CODAS")
    out += arr("VTTS_KO_STEM", "uint8_t", by_code({c: 1 for c in g.STEM_CODAS}, int), "STEM_CODAS")
    yp = [255] * len(h.VOWELS)
    for key, v in g.Y_TO_PLAIN.items():
        yp[vowel[key]] = vowel[v]
    out += arr("VTTS_KO_Y_PLAIN", "uint8_t", yp, "Y_TO_PLAIN: vowel -> vowel (255: none)")
    out += arr("VTTS_KO_ONSET_ID", "uint8_t", by_code(g.ONSET_NAMES, lambda s: k(f"KO:I:{s}")),
               "onset code -> token id (0: silent or none)")
    out += arr("VTTS_KO_VOWEL_ID", "uint8_t", [k(f"KO:V:{g.VOWEL_NAMES[v]}") for v in h.VOWELS], "vowel -> token id")
    out += arr("VTTS_KO_CODA_ID", "uint8_t", by_code(g.CODA_NAMES, lambda s: k(f"KO:C:{s}")),
               "coda code -> token id (0: none)")
    table = g.override_table()
    longest = max(map(len, table))
    assert all(h.is_hangul_syllable(c) for kv in table.items() for s in kv for c in s)
    out += [f"#define VTTS_KO_OVR_MAX {longest}",
            "/* lexicons/ko/overrides.tsv: syllables - U+AC00 of the written form and its reading */",
            "static const struct { uint8_t nk, nr; uint16_t k[VTTS_KO_OVR_MAX], r[VTTS_KO_OVR_MAX]; } VTTS_KO_OVERRIDES[] = {"]
    for key, v in table.items():
        ks = ", ".join(str(ord(c) - h.BASE) for c in key)
        rs = ", ".join(str(ord(c) - h.BASE) for c in v)
        out.append(f"    {{{len(key)}, {len(v)}, {{{ks}}}, {{{rs}}}}},  /* {key} {v} */")
    out += ["};", f"#define VTTS_KO_N_OVERRIDES {len(table)}", ""]
    out += c_list("VTTS_KO_SINO_DIGITS", list(nk.SINO_DIGITS))
    out += c_list("VTTS_KO_PHONE_DIGITS", list(nk.PHONE_DIGITS))
    out += c_list("VTTS_KO_SECTION_UNITS", [u for _, u in nk._SECTION_UNITS])
    out += c_list("VTTS_KO_GROUP_UNITS", list(nk._GROUP_UNITS))
    out += c_list("VTTS_KO_NATIVE_ONES", list(nk.NATIVE_ONES))
    out += c_list("VTTS_KO_NATIVE_ONES_COUNTER", list(nk.NATIVE_ONES_COUNTER))
    out += c_list("VTTS_KO_NATIVE_TENS", list(nk.NATIVE_TENS))
    out += ["static const struct { int month; const char *name; } VTTS_KO_MONTHS[] = {"]
    out += [f"    {{{m}, {c_str(v)}}}," for m, v in nk.MONTHS.items()]
    out += ["};", f"#define VTTS_KO_N_MONTHS {len(nk.MONTHS)}", ""]
    kinds = {"native": 1, "sino": 2, "joined": 3}
    out += ["/* counters, longest first (counter_kind): kind 1 native, 2 sino, 3 joined */",
            "static const struct { const char *word; uint8_t kind; } VTTS_KO_COUNTERS[] = {"]
    out += [f"    {{{c_str(c)}, {kinds[kind]}}}," for c, kind in nk._COUNTERS]
    out += ["};", f"#define VTTS_KO_N_COUNTERS {len(nk._COUNTERS)}", ""]
    extra = {kk: v for kk, v in nk._FULLWIDTH.items() if not 0xFF01 <= kk < 0xFF5F}
    assert all(nk._FULLWIDTH[c] == c - 0xFEE0 for c in range(0xFF01, 0xFF5F))
    out += ["/* full-width forms: U+FF01..U+FF5E -> minus 0xFEE0, plus these */",
            "static const uint32_t VTTS_KO_FULLWIDTH[][2] = {"]
    out += [f"    {{0x{kk:04X}, 0x{v:04X}}}," for kk, v in extra.items()]
    out += ["};", f"#define VTTS_KO_N_FULLWIDTH {len(extra)}", ""]
    out += ["static const char *const VTTS_KO_SYMBOLS[][2] = {  /* replaced in this order */"]
    out += [f"    {{{c_str(kk)}, {c_str(v)}}}," for kk, v in nk._SYMBOLS.items()]
    out += ["};", f"#define VTTS_KO_N_SYMBOLS {len(nk._SYMBOLS)}", ""]
    out += ["static const uint32_t VTTS_KO_DROP[] = {  /* replaced by a space */"]
    drop = [f"0x{ord(c):04X}" for c in nk._DROP]
    out += ["    " + ", ".join(drop[i:i + 8]) + "," for i in range(0, len(drop), 8)]
    out += ["};", f"#define VTTS_KO_N_DROP {len(drop)}", ""]
    units = sorted(nk.UNITS, key=len, reverse=True)  # the alternation order of the UNIT regex
    out += ["static const char *const VTTS_KO_UNITS[][2] = {  /* alternation order */"]
    out += [f"    {{{c_str(u)}, {c_str(nk.UNITS[u])}}}," for u in units]
    out += ["};", f"#define VTTS_KO_N_UNITS {len(units)}", ""]
    out += ["static const struct { uint32_t cp; const char *name; } VTTS_KO_CURRENCY[] = {"]
    out += [f"    {{0x{ord(kk):04X}, {c_str(v)}}}," for kk, v in nk.CURRENCY.items()]
    out += ["};", f"#define VTTS_KO_N_CURRENCY {len(nk.CURRENCY)}", ""]
    return out


# literal strings of normalize_hi.py (not in a table there); each must appear in its source
HI_LITERALS = {"MINUS": "माइनस ", "POINT": " दशमलव ", "BAJE": "बजे", "BAJKAR": "बजकर", "MINUTE": "मिनट",
               "SECOND": "सेकंड", "SE": "से", "PERCENT": "प्रतिशत", "PLUS": "प्लस ", "RUPAYA": "रुपया",
               "RUPAYE": "रुपये", "PAISE": "पैसे", "SAU": "सौ", "SAN_H": "सन्", "SAN": "सन", "ISVI": "ईस्वी"}


def _deva_nfd(s: str) -> str:
    """NFC with the nukta letters decomposed: the form the C g2p compares (canonically equivalent)."""
    from vtts.frontend.hi import g2p_hi as g

    t = unicodedata.normalize("NFC", s)
    return "".join(g.PRECOMPOSED[c] + g.NUKTA if c in g.PRECOMPOSED else c for c in t)


def hindi_tables() -> list[str]:
    """Token ids of the hi-en set, the letter tables of the Devanagari rules (hi/g2p_hi.py), the
    exception table (lexicons/hi/overrides.tsv) and the strings of the normalizer (hi/normalize_hi.py,
    lexicons/hi/numbers.tsv). Phonemes are coded as their index in g2p_hi.PHONEMES (the token order)."""
    import re

    from vtts.frontend import latin_norm
    from vtts.frontend.hi import g2p_hi as g
    from vtts.frontend.hi import normalize_hi as nh

    src = (Path(nh.__file__)).read_text(encoding="utf-8")
    assert all(v in src for v in HI_LITERALS.values())
    hi = phoneme_set.token_index(phoneme_set.TOKEN_SET_HIEN)
    ph = {p: i for i, p in enumerate(g.PHONEMES)}
    assert [hi[f"HI:{p}"] for p in g.PHONEMES] == list(range(hi["HI:a"], hi["HI:a"] + len(g.PHONEMES)))
    out = ["/* ---- Hindi (token set hi-en; ids 0..106 are the v2 ids) ---- */",
           f"#define VTTS_HIEN_VOCAB {phoneme_set.VOCAB_SIZE_HIEN}",
           f"#define VTTS_HIEN_HI0 {hi['HI:a']}  /* + phoneme index (g2p_hi.PHONEMES) */",
           f"#define VTTS_HI_N_PHONEMES {len(g.PHONEMES)}",
           f"#define VTTS_HI_PH_NASAL {ph[g.NASAL]}", ""]
    out += c_list("VTTS_HI_PHONEMES", list(g.PHONEMES))
    # per code point U+0900..U+097F: kind, a, b, c
    K_LETTER, K_VOWEL, K_MATRA, K_ANUSVARA, K_CANDRA, K_VISARGA, K_VIRAMA, K_NUKTA, K_OM, K_PRECOMP = range(1, 11)
    rows = []
    for cp in range(0x900, 0x980):
        ch = chr(cp)
        kind, a, b, c = 0, 255, 255, 255
        if ch in g.LETTERS:
            kind, a, c = K_LETTER, ph[g.LETTERS[ch]], ph[g.NUKTA_LETTERS.get(ch, g.LETTERS[ch])]
        elif ch in g.INDEPENDENT or ch in g.MATRAS:
            parts = (g.INDEPENDENT.get(ch) or g.MATRAS[ch]).split()
            assert len(parts) <= 2
            kind = K_VOWEL if ch in g.INDEPENDENT else K_MATRA
            b = ph[parts[-1]]
            a = ph[parts[0]] if len(parts) == 2 else 255
        elif ch == g.ANUSVARA:
            kind = K_ANUSVARA
        elif ch == g.CHANDRABINDU:
            kind = K_CANDRA
        elif ch == g.VISARGA:
            kind = K_VISARGA
        elif ch == g.VIRAMA:
            kind = K_VIRAMA
        elif ch == g.NUKTA:
            kind = K_NUKTA
        elif ch == "ॐ":
            kind = K_OM
        elif ch in g.PRECOMPOSED:
            kind, a = K_PRECOMP, ord(g.PRECOMPOSED[ch]) - 0x900
        rows.append(f"{{{kind}, {a}, {b}, {c}}}")
    assert all(ord(ch) in range(0x900, 0x980) for ch in g.PRECOMPOSED)
    out += ["/* U+0900 + i: {kind, a, b, c}; kind 1 consonant (a phoneme, c with nukta), 2 independent vowel and",
            " * 3 matra (a consonant or 255, b vowel), 4 anusvara, 5 chandrabindu, 6 visarga, 7 virama, 8 nukta,",
            " * 9 om, 10 precomposed nukta letter (a = base letter - U+0900), 0 ignored */",
            "static const uint8_t VTTS_HI_CHARS[128][4] = {"]
    out += ["    " + ", ".join(rows[i:i + 8]) + "," for i in range(0, 128, 8)] + ["};", ""]
    for name, vals in (("HOMORGANIC", [ph[g.HOMORGANIC[p]] if p in g.HOMORGANIC else 255 for p in g.PHONEMES]),
                       ("SHORT", [int(p in g.SHORT) for p in g.PHONEMES]),
                       ("FINAL_KEEP", [int(p in g.FINAL_KEEP) for p in g.PHONEMES])):
        out += [f"static const uint8_t VTTS_HI_{name}[{len(vals)}] = {{" + ", ".join(map(str, vals)) + "};"]
    out += [""]
    word = [0] * 160  # Python \w over U+0900..U+097F and U+A8E0..U+A8FF
    for k, cp in enumerate(list(range(0x900, 0x980)) + list(range(0xA8E0, 0xA900))):
        if re.match(r"\w", chr(cp)):
            word[k // 8] |= 1 << (k % 8)
    out += ["/* Python \\w bits: U+0900..U+097F (bits 0..127), U+A8E0..U+A8FF (128..159) */",
            "static const uint8_t VTTS_HI_WORD_BITS[20] = {" + ", ".join(map(str, word[:20])) + "};", ""]
    ccc = [(cp, unicodedata.combining(chr(cp))) for cp in list(range(0x300, 0x370)) + list(range(0x900, 0x980))
           + list(range(0xA8E0, 0xA900)) if unicodedata.combining(chr(cp))]
    out += ["/* canonical combining classes (non-zero) of U+0300..U+036F and the Devanagari blocks */",
            "static const struct { uint16_t cp; uint8_t ccc; } VTTS_HI_CCC[] = {"]
    out += ["    " + ", ".join(f"{{0x{c:04X}, {v}}}" for c, v in ccc[i:i + 6]) + "," for i in range(0, len(ccc), 6)]
    out += ["};", f"#define VTTS_HI_N_CCC {len(ccc)}", ""]
    table = g.override_table()
    assert all(unicodedata.normalize("NFC", k) == k for k in table)
    longest = max(len(v.split()) for v in table.values())
    out += [f"#define VTTS_HI_OVR_MAX {longest}",
            "/* lexicons/hi/overrides.tsv: the word (NFC, nukta letters decomposed) and its phoneme indices */",
            "static const struct { const char *word; uint8_t n; uint8_t ph[VTTS_HI_OVR_MAX]; } VTTS_HI_OVERRIDES[] = {"]
    for k, v in table.items():
        ids = [ph[p] for p in v.split()]
        out.append(f"    {{{c_str(_deva_nfd(k))}, {len(ids)}, {{{', '.join(map(str, ids))}}}}},")
    out += ["};", f"#define VTTS_HI_N_OVERRIDES {len(table)}", ""]
    nw = nh.number_words()
    assert sorted(nw) == list(range(100))
    out += c_list("VTTS_HI_NUMBERS", [nw[i] for i in range(100)])
    assert [s for s, _ in nh.SCALES] == [10 ** 7, 10 ** 5, 1000, 100]
    out += c_list("VTTS_HI_SCALES", [name for _, name in nh.SCALES])
    out += c_list("VTTS_HI_MONTHS", list(nh.MONTHS))
    out += c_list("VTTS_HI_LETTERS", [nh.LETTERS[c] for c in "abcdefghijklmnopqrstuvwxyz"])

    def pairs(name: str, items: list[tuple[str, str]], comment: str) -> list[str]:
        return ([f"static const char *const VTTS_HI_{name}[][2] = {{  /* {comment} */"]
                + [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in items]
                + ["};", f"#define VTTS_HI_N_{name} {len(items)}", ""])

    def by_len(d: dict) -> list[tuple[str, str]]:
        return [(k, d[k]) for k in sorted(d, key=len, reverse=True)]

    out += pairs("ABBREV", by_len(nh.ABBREVIATIONS), "longest first")
    out += pairs("UNITS", by_len(nh.UNITS), "alternation order")
    out += pairs("CURRENCY", by_len(nh.CURRENCY), "alternation order")
    assert all(len(k) == 1 for k in nh.SYMBOLS)
    out += pairs("SYMBOLS", list(nh.SYMBOLS.items()), "replaced in this order")
    out += pairs("ORD_ENDINGS", list(nh.ORDINAL_ENDINGS.items()), "alternation order")
    out += ["static const struct { int n; const char *stem; } VTTS_HI_ORD_STEMS[] = {"]
    out += [f"    {{{n}, {c_str(v)}}}," for n, v in nh.ORDINAL_STEMS.items()]
    out += ["};", f"#define VTTS_HI_N_ORD_STEMS {len(nh.ORDINAL_STEMS)}", ""]
    m = re.search(r"\(\\s\?\(\?:([^)]*)\)\)\?$", nh.MONEY.pattern)
    assert m, nh.MONEY.pattern
    out += c_list("VTTS_HI_MONEY_SCALES", m.group(1).split("|"))
    out += [f"#define VTTS_HI_N_MONEY_SCALES {len(m.group(1).split('|'))}", ""]
    out += c_list("VTTS_HI_LATIN_WORDS", sorted(nh.LATIN_WORDS))
    out += [f"#define VTTS_HI_N_LATIN_WORDS {len(nh.LATIN_WORDS)}", ""]
    out += ["static const uint32_t VTTS_HI_DROP[] = {  /* latin_norm.DROP: replaced by a space */"]
    drop = [f"0x{ord(c):04X}" for c in latin_norm.DROP]
    out += ["    " + ", ".join(drop[i:i + 8]) + "," for i in range(0, len(drop), 8)]
    out += ["};", f"#define VTTS_HI_N_DROP {len(drop)}", ""]
    fold = []
    for cp in range(0xC0, 0x250):
        f = "".join(x for x in unicodedata.normalize("NFKD", chr(cp)) if x.isascii())
        assert len(f) <= 2
        fold.append(c_str(f))
    out += ["/* ASCII letters of the NFKD form of U+00C0..U+024F (the LATIN pass of normalize_hi) */",
            f"static const char VTTS_HI_FOLD[{len(fold)}][3] = {{"]
    out += ["    " + ", ".join(fold[i:i + 12]) + "," for i in range(0, len(fold), 12)] + ["};", ""]
    out += [f"#define VTTS_HI_{k} {c_str(v)}" for k, v in HI_LITERALS.items()] + [""]
    return out


def japanese_tables() -> list[str]:
    """Token ids of the ja-en set, the kana tables of ja/kana.py and the strings of the normalizer
    (ja/normalize_ja.py). The reading tables are in the JLEX blob (scripts/frontend/build_ja_blob.py).
    Kana codes: hiragana - 0x3040 (katakana are folded to hiragana first, like kana.to_hiragana)."""
    from vtts.frontend.ja import g2p_ja
    from vtts.frontend.ja import kana as k
    from vtts.frontend.ja import normalize_ja as nj

    j = phoneme_set.token_to_id_jaen

    def ids(phs) -> list[int]:
        return [j(f"JA:{p}") for p in phs]

    def code(ch: str) -> int:
        c = ord(ch) - 0x3040
        assert 0 < c < 0x60, ch
        return c

    vowels = ids(k.V)
    assert vowels == list(range(vowels[0], vowels[0] + 5))
    out = ["/* ---- Japanese (token set ja-en; ids 0..106 are the v2 ids) ---- */",
           f"#define VTTS_JAEN_VOCAB {phoneme_set.VOCAB_SIZE_JAEN}",
           f"#define VTTS_JA_V0 {vowels[0]}  /* JA:a .. JA:o are V0 .. V0 + 4 */",
           f"#define VTTS_JA_N {j('JA:N')}",
           f"#define VTTS_JA_CL {j('JA:cl')}",
           f"#define VTTS_JA_MAX_UNIT_MORAE {g2p_ja.MAX_UNIT_MORAE}",
           f"#define VTTS_JA_LONG 0x{ord(k.LONG) - 0x30A0:02X}  /* code of the long-vowel mark (katakana - 0x30A0) */",
           ""]
    single = [[0, 0, 0] for _ in range(0x60)]
    for ch, phs in k.SINGLE.items():
        v = ids(phs)
        single[code(ch)] = [len(v)] + v + [0] * (2 - len(v))
    out += ["/* SINGLE: kana code -> (count, ids) */", "static const uint8_t VTTS_JA_SINGLE[96][3] = {"]
    out += ["    " + " ".join("{" + ", ".join(map(str, r)) + "}," for r in single[i:i + 8]) for i in range(0, 96, 8)]
    out += ["};", ""]
    pairs = sorted((code(kk[0]), code(kk[1]), ids(v)) for kk, v in k.PAIRS.items())
    out += ["/* PAIRS: (first code, second code, count, ids), sorted */",
            "static const uint8_t VTTS_JA_PAIRS[][6] = {"]
    out += [f"    {{{a}, {b}, {len(v)}, {', '.join(map(str, v + [0] * (3 - len(v))))}}}," for a, b, v in pairs]
    out += ["};", f"#define VTTS_JA_N_PAIRS {len(pairs)}", ""]
    voiced = [0] * 0x60
    for a, b in k._VOICED.items():
        voiced[code(a)] = code(b)
    assert list(k.ITERATION) == ["ゝ", "ゞ"] and code("ゞ") == code("ゝ") + 1
    out += ["/* _VOICED: kana code -> voiced kana code (0: unchanged) */", "static const uint8_t VTTS_JA_VOICED[96] = {"]
    out += ["    " + ", ".join(map(str, voiced[i:i + 24])) + "," for i in range(0, 96, 24)]
    out += ["};", f"#define VTTS_JA_ITER 0x{code('ゝ'):02X}  /* code of ゝ; ゞ (voiced) is + 1 */", ""]
    out += c_list("VTTS_JA_DIGITS", list(nj.DIGITS))
    thousands = [nj.THOUSANDS.get(d, "") for d in range(10)]
    hundreds = [nj.HUNDREDS.get(d, "") for d in range(10)]
    out += ["/* THOUSANDS, HUNDREDS: special readings per digit (empty: DIGITS[d] + セン / ヒャク) */"]
    out += c_list("VTTS_JA_THOUSANDS", thousands) + c_list("VTTS_JA_HUNDREDS", hundreds)
    out += c_list("VTTS_JA_GROUPS", list(nj.GROUPS))
    order = sorted(nj.COUNTERS, key=len, reverse=True)  # the alternation order of _COUNTER_RE
    assert "|".join(order) == nj._COUNTER_RE

    def ending_mask(digits) -> int:
        return sum(1 << (d if d < 10 else 10 if d == 10 else 11) for d in digits)

    out += ["/* COUNTERS in the alternation order of _COUNTER_RE (longest first). gem_mask: bit d for the",
            " * last digit d, bit 10 for ...十, bit 11 for ...百; nasal_after: '|'-separated; last[d]: reading",
            " * of the last digit (NULL: none); whole: \"n=reading|...\" */",
            "typedef struct { const char *key, *base, *gem; uint16_t gem_mask; const char *nasal, *nasal_after;",
            "                 const char *last[10]; const char *whole; } vtts_ja_counter;",
            "static const vtts_ja_counter VTTS_JA_COUNTERS[] = {"]
    for key in order:
        c = nj.COUNTERS[key]
        last = ", ".join(c_str(c.last[d]) if c.last and d in c.last else "NULL" for d in range(10))
        whole = "|".join(f"{n}={r}" for n, r in sorted((c.whole or {}).items()))
        out.append(f"    {{{c_str(key)}, {c_str(c.base)}, {c_str(c.gem) if c.gem is not None else 'NULL'}, "
                   f"0x{ending_mask(c.gem_digits):03X}, {c_str(c.nasal) if c.nasal is not None else 'NULL'}, "
                   f"{c_str('|'.join(c.nasal_after))}, {{{last}}}, {c_str(whole)}}},")
    out += ["};", f"#define VTTS_JA_N_COUNTERS {len(order)}", ""]
    extra = {kk: v for kk, v in nj._FULLWIDTH.items() if not 0xFF01 <= kk < 0xFF5F}
    assert all(nj._FULLWIDTH[c] == c - 0xFEE0 for c in range(0xFF01, 0xFF5F))
    out += ["/* full-width forms: U+FF01..U+FF5E -> minus 0xFEE0, plus these */",
            "static const uint32_t VTTS_JA_FULLWIDTH[][2] = {"]
    out += [f"    {{0x{kk:04X}, 0x{v:04X}}}," for kk, v in extra.items()]
    out += ["};", f"#define VTTS_JA_N_FULLWIDTH {len(extra)}", ""]
    out += ["static const char *const VTTS_JA_SYMBOLS[][2] = {  /* replaced in this order */"]
    out += [f"    {{{c_str(kk)}, {c_str(v)}}}," for kk, v in nj._SYMBOLS.items()]
    out += ["};", f"#define VTTS_JA_N_SYMBOLS {len(nj._SYMBOLS)}", ""]
    out += ["static const uint32_t VTTS_JA_DROP[] = {  /* replaced by a space */"]
    drop = [f"0x{ord(c):04X}" for c in nj._DROP]
    out += ["    " + ", ".join(drop[i:i + 8]) + "," for i in range(0, len(drop), 8)]
    out += ["};", f"#define VTTS_JA_N_DROP {len(drop)}", ""]
    units = sorted(nj.UNITS, key=len, reverse=True)  # the alternation order of the UNIT regex
    out += ["static const char *const VTTS_JA_UNITS[][2] = {  /* alternation order */"]
    out += [f"    {{{c_str(u)}, {c_str(nj.UNITS[u])}}}," for u in units]
    out += ["};", f"#define VTTS_JA_N_UNITS {len(units)}", ""]
    out += ["static const struct { uint32_t cp; const char *name; } VTTS_JA_CURRENCY[] = {"]
    out += [f"    {{0x{ord(kk):04X}, {c_str(v)}}}," for kk, v in nj.CURRENCY.items()]
    out += ["};", f"#define VTTS_JA_N_CURRENCY {len(nj.CURRENCY)}", ""]
    big = [(u, v, len(str(v // 10))) for u, v in nj.BIG_UNITS]
    out += ["/* BIG_UNITS in order: (unit, value, digits allowed after it) */",
            "static const struct { uint32_t cp; double value; int max_digits; } VTTS_JA_BIG[] = {"]
    out += [f"    {{0x{ord(u):04X}, {v}.0, {n}}}," for u, v, n in big]
    out += ["};", f"#define VTTS_JA_N_BIG {len(big)}", f"#define VTTS_JA_MARK 0x{ord(nj.MARK):04X}", ""]
    zeros = [c for c in range(0x110000) if unicodedata.category(chr(c)) == "Nd" and unicodedata.decimal(chr(c)) == 0]
    assert all(unicodedata.decimal(chr(z + i)) == i for z in zeros for i in range(10))
    assert sum(unicodedata.category(chr(c)) == "Nd" for c in range(0x110000)) == 10 * len(zeros)
    out += [f"/* Python's \\d: Unicode decimal digits (category Nd, Unicode {unicodedata.unidata_version}) in runs of",
            " * ten from these zeros */", "static const uint32_t VTTS_ND_ZEROS[] = {"]
    zs = [f"0x{z:05X}" for z in zeros]
    out += ["    " + ", ".join(zs[i:i + 8]) + "," for i in range(0, len(zs), 8)]
    out += ["};", f"#define VTTS_N_ND_ZEROS {len(zeros)}", ""]
    return out


# ---------------- Latin-script pairs (es-en, id-en, pt-en) and the Unicode classes they need ----------------

def _str_list(name: str, items) -> list[str]:
    items = list(items)
    if not items:
        return [f"static const char *const {name}[1] = {{0}};", ""]
    return c_list(name, items)


def _ranges(pred) -> list[tuple[int, int]]:
    out, start = [], None
    for c in range(0x110000):
        p = not 0xD800 <= c < 0xE000 and pred(chr(c))
        if p and start is None:
            start = c
        if not p and start is not None:
            out.append((start, c - 1))
            start = None
    if start is not None:
        out.append((start, 0x10FFFF))
    return out


def unicode_tables() -> list[str]:
    """Python's re classes for str patterns: \\w (isalnum or _), \\d (isdecimal, blocks of ten
    digits), str.lower() as runs, and the re.IGNORECASE variants of the letters the Indonesian time
    rule looks behind for ("pukul ", "jam ")."""
    import re

    word = _ranges(lambda ch: ch.isalnum() or ch == "_")
    dec = _ranges(lambda ch: ch.isdecimal())
    for a, b in dec:  # blocks of ten digits 0..9
        assert all(unicodedata.decimal(chr(c)) == (c - a) % 10 for c in range(a, b + 1)), hex(a)
    space = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000 and chr(c).isspace()]
    multi = {c for c in range(0x110000) if not 0xD800 <= c < 0xE000 and len(chr(c).lower()) != 1}
    assert multi == {0x130} and chr(0x130).lower() == "i̇"
    low = [(c, ord(chr(c).lower()[0]) - c) for c in range(0x110000)
           if not 0xD800 <= c < 0xE000 and chr(c).lower() != chr(c)]
    runs: list[list[int]] = []  # first, count, delta, step
    for c, dl in low:
        if runs:
            r = runs[-1]
            last = r[0] + (r[1] - 1) * r[3]
            if r[2] == dl and r[1] == 1 and c - last in (1, 2):
                r[1], r[3] = 2, c - last
                continue
            if r[2] == dl and r[1] > 1 and c - last == r[3]:
                r[1] += 1
                continue
        runs.append([c, 1, dl, 1])
    for r0, r1 in pairwise(runs):  # disjoint and sorted (binary search)
        assert r0[0] + (r0[1] - 1) * r0[3] < r1[0]
    out = ["/* ---- Unicode classes of Python's re (str patterns), for the Latin-script pairs ---- */",
           f"static const uint32_t VTTS_U_WORD[{len(word)}][2] = {{  /* \\w: isalnum() or _ */"]
    out += ["    " + " ".join(f"{{0x{a:X}, 0x{b:X}}}," for a, b in word[i:i + 6]) for i in range(0, len(word), 6)]
    out += ["};", f"#define VTTS_U_N_WORD {len(word)}", "",
            f"static const uint32_t VTTS_U_DECIMAL[{len(dec)}][2] = {{  /* \\d: isdecimal(), blocks of 0..9 */"]
    out += ["    " + " ".join(f"{{0x{a:X}, 0x{b:X}}}," for a, b in dec[i:i + 6]) for i in range(0, len(dec), 6)]
    out += ["};", f"#define VTTS_U_N_DECIMAL {len(dec)}", "",
            f"static const uint32_t VTTS_U_SPACE[{len(space)}] = {{  /* \\s and str.split(): isspace() */",
            "    " + ", ".join(f"0x{c:X}" for c in space) + ",", "};", f"#define VTTS_U_N_SPACE {len(space)}", "",
            "/* str.lower() of one code point: runs (first, count, delta, step); U+0130 lowers to i U+0307 */",
            f"static const int32_t VTTS_U_LOWER[{len(runs)}][4] = {{"]
    out += ["    " + " ".join(f"{{0x{a:X}, {n}, {d}, {s}}}," for a, n, d, s in runs[i:i + 5])
            for i in range(0, len(runs), 5)]
    out += ["};", f"#define VTTS_U_N_LOWER {len(runs)}", ""]
    letters = sorted(set("pukuljam"))
    var = {ch: [c for c in range(0x110000)
                if not 0xD800 <= c < 0xE000 and re.fullmatch(ch, chr(c), re.IGNORECASE)] for ch in letters}
    width = max(len(v) for v in var.values()) + 1
    out += [f"static const uint32_t VTTS_U_ICASE[{len(letters)}][{width}] = {{  /* re.I variants (0 ends) */"]
    out += [f"    {{{', '.join(f'0x{c:X}' for c in var[ch])}{', 0' * (width - len(var[ch]))}}},  /* {ch} */"
            for ch in letters]
    out += ["};", f"#define VTTS_U_N_ICASE {len(letters)}", ""]
    return out


def latin_tables() -> list[str]:
    """Tables of the Latin-script pair front-ends (es/, id/, pt/, latin.py, latin_norm.py): token
    names, normalizer tables in the order the regexes and replacements use them, number words, the
    word lists of the tagger, the exception tables and the letters of each g2p (fold() of every code
    point as runs, spelling-check clusters)."""
    from vtts.frontend import latin, latin_norm
    from vtts.frontend.es import g2p_es, normalize_es
    from vtts.frontend.id import g2p_id, normalize_id
    from vtts.frontend.lexicons import load_words
    from vtts.frontend.pt import g2p_pt, normalize_pt

    out = ["/* ---- Latin-script pairs (token sets es-en, id-en, pt-en; ids 0..106 are the v2 ids) ---- */"]
    english = sorted(load_words("latin", "english"))
    assert all(w.isascii() for w in english)
    out += c_list("VTTS_LT_ENGLISH", english) + [f"#define VTTS_LT_N_ENGLISH {len(english)}", ""]
    assert latin_norm.MARKS == ",.?!;:"
    out += ["typedef struct { const char *key, *one, *many; } vtts_lt_reading;",
            "typedef struct { uint32_t cp; const char *name; } vtts_lt_letter;",
            "typedef struct { uint32_t start; uint16_t count; uint8_t first, step; } vtts_lt_fold;",
            "typedef struct {",
            "    const char *code;",
            "    int tok0, n_tokens, vocab;",
            "    const char *const *tokens;          /* names of the ids tok0.. without the prefix */",
            "    const char *const (*abbrev)[2]; int n_abbrev;  /* in the order they are applied */",
            "    const char *drop;                  /* characters replaced by a space */",
            "    const vtts_lt_letter *letters; int n_letters;   /* letter names (spelling) */",
            "    const char *const *acronym_words; int n_acronym_words;",
            "    const vtts_lt_reading *units; int n_units;       /* alternation order */",
            "    const vtts_lt_reading *currency; int n_currency; /* alternation order */",
            "    const vtts_lt_letter *symbols; int n_symbols;   /* replaced in this order */",
            "    const char *comma, *period;        /* MARK_WORDS */",
            "    const char *const *months;",
            "    const char *const *native; int n_native;        /* sorted */",
            "    const char *const *table_keys; int n_table_keys; /* sorted */",
            "    const char *const (*overrides)[2]; int n_overrides;",
            "    const char *const *unstressed; int n_unstressed;",
            "    const char *own;                   /* LATIN_PAIRS letters */",
            "    const char *g2p_letters;           /* LETTERS of the g2p outside a-z */",
            "    const vtts_lt_fold *fold; int n_fold;           /* fold() of code points >= 0x80 */",
            "    const char *const *onsets; int n_onsets;",
            "    const char *const *codas; int n_codas;",
            "    const char *const *finals; int n_finals;",
            "    const char *const *doubles; int n_doubles;",
            "    const char *const *foreign; int n_foreign;",
            "    const char *const (*digraphs)[2]; int n_digraphs;",
            "} vtts_lt_lang;", ""]
    langs = (("es", "ES", g2p_es, normalize_es), ("id", "ID", g2p_id, normalize_id),
             ("pt", "PT", g2p_pt, normalize_pt))
    descs = []
    for code, up, g, nm in langs:
        tset = phoneme_set.TOKEN_SETS[phoneme_set.PAIR_MODES[code]]
        tok0 = phoneme_set.VOCAB_SIZE_V2
        assert all(t.startswith(up + ":") for t in tset[tok0:])
        names = [t.split(":", 1)[1] for t in tset[tok0:]]
        out += [f"/* {code}: token set {phoneme_set.PAIR_MODES[code]} */"]
        out += c_list(f"VTTS_{up}_TOKENS", names)
        abbrev = sorted(nm.ABBREVIATIONS, key=len, reverse=True)  # apply_abbreviations order
        out += [f"static const char *const VTTS_{up}_ABBREV[][2] = {{"]
        out += [f"    {{{c_str(k)}, {c_str(nm.ABBREVIATIONS[k])}}}," for k in abbrev] + ["};", ""]
        drop = latin_norm.DROP.replace("(", "").replace(")", "") if code == "pt" else latin_norm.DROP
        letters = list(nm.LETTERS.items())
        out += [f"static const vtts_lt_letter VTTS_{up}_LETTERS[] = {{"]
        out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in letters] + ["};", ""]
        out += _str_list(f"VTTS_{up}_ACRONYM_WORDS", sorted(nm.ACRONYM_WORDS))

        def reading(v):
            return (v, v) if isinstance(v, str) else v

        units = sorted(nm.UNITS, key=len, reverse=True)  # the alternation order of the regexes
        out += [f"static const vtts_lt_reading VTTS_{up}_UNITS[] = {{"]
        out += [f"    {{{c_str(k)}, {c_str(reading(nm.UNITS[k])[0])}, {c_str(reading(nm.UNITS[k])[1])}}},"
                for k in units] + ["};", ""]
        cur = sorted(nm.CURRENCY, key=len, reverse=True)
        out += [f"static const vtts_lt_reading VTTS_{up}_CURRENCY[] = {{"]
        out += [f"    {{{c_str(k)}, {c_str(reading(nm.CURRENCY[k])[0])}, {c_str(reading(nm.CURRENCY[k])[1])}}},"
                for k in cur] + ["};", ""]
        assert all(len(k) == 1 for k in nm.SYMBOLS)
        out += [f"static const vtts_lt_letter VTTS_{up}_SYMBOLS[] = {{"]
        out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.SYMBOLS.items()] + ["};", ""]
        out += c_list(f"VTTS_{up}_MONTHS", list(nm.MONTHS))
        native = sorted(load_words(code, "native"))
        out += _str_list(f"VTTS_{up}_NATIVE", native)
        keys = sorted(latin._table_keys(code))
        out += _str_list(f"VTTS_{up}_TABLE_KEYS", keys)
        ovr = g.override_table()
        out += [f"static const char *const VTTS_{up}_OVERRIDES[][2] = {{"]
        out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ovr.items()] + ["};", ""]
        out += _str_list(f"VTTS_{up}_UNSTRESSED", sorted(g.UNSTRESSED))
        assert set("abcdefghijklmnopqrstuvwxyz") <= g.LETTERS
        extra = "".join(sorted(g.LETTERS - set("abcdefghijklmnopqrstuvwxyz")))
        for c in range(0x80):  # ASCII: lower-case a-z (and ' in Indonesian), nothing else
            want = chr(c).lower() if chr(c).isalpha() else ("'" if code == "id" and chr(c) == "'" else "")
            assert g.fold(chr(c)) == want, (code, c)
        folded = [(c, g.fold(chr(c))) for c in range(0x80, 0x110000) if not 0xD800 <= c < 0xE000]
        folded = [(c, f) for c, f in folded if f]
        assert all(len(f) == 1 and ord(f) < 256 for _, f in folded)
        runs: list[list[int]] = []  # start, count, first result, step 0/1
        for c, f in folded:
            if runs and c == runs[-1][0] + runs[-1][1] and runs[-1][1] < 65535:
                r = runs[-1]
                if r[1] == 1 and ord(f) in (r[2], r[2] + 1):
                    r[1], r[3] = 2, ord(f) - r[2]
                    continue
                if r[1] > 1 and ord(f) == r[2] + r[1] * r[3]:
                    r[1] += 1
                    continue
            runs.append([c, 1, ord(f), 0])
        out += [f"static const vtts_lt_fold VTTS_{up}_FOLD[{len(runs)}] = {{"]
        out += ["    " + " ".join(f"{{0x{a:X}, {n}, 0x{f:02X}, {s}}}," for a, n, f, s in runs[i:i + 5])
                for i in range(0, len(runs), 5)] + ["};", ""]
        for attr in ("ONSETS", "CODAS", "FINALS", "DOUBLES"):
            out += _str_list(f"VTTS_{up}_{attr}", sorted(getattr(g, attr)))
        out += _str_list(f"VTTS_{up}_FOREIGN", list(g.FOREIGN))
        out += [f"static const char *const VTTS_{up}_DIGRAPHS[][2] = {{  /* replaced in this order */"]
        out += [f"    {{{c_str(a)}, {c_str(b)}}}," for a, b in g.DIGRAPHS] + ["};", ""]
        n = len
        descs.append(  # a language that is not compiled in (vtts_langs.h) keeps an empty row
            f"#if VTTS_ENABLE_{up}\n"
            f"    {{{c_str(code)}, {tok0}, {n(names)}, {n(tset)}, VTTS_{up}_TOKENS, VTTS_{up}_ABBREV, {n(abbrev)},\n"
            f"     {c_str(drop)}, VTTS_{up}_LETTERS, {n(letters)}, VTTS_{up}_ACRONYM_WORDS, {n(nm.ACRONYM_WORDS)},\n"
            f"     VTTS_{up}_UNITS, {n(units)}, VTTS_{up}_CURRENCY, {n(cur)}, VTTS_{up}_SYMBOLS, {n(nm.SYMBOLS)},\n"
            f"     {c_str(nm.MARK_WORDS[','])}, {c_str(nm.MARK_WORDS['.'])}, VTTS_{up}_MONTHS,\n"
            f"     VTTS_{up}_NATIVE, {n(native)}, VTTS_{up}_TABLE_KEYS, {n(keys)}, VTTS_{up}_OVERRIDES, {n(ovr)},\n"
            f"     VTTS_{up}_UNSTRESSED, {n(g.UNSTRESSED)}, {c_str(latin.LATIN_PAIRS[code])}, {c_str(extra)},\n"
            f"     VTTS_{up}_FOLD, {n(runs)}, VTTS_{up}_ONSETS, {n(g.ONSETS)}, VTTS_{up}_CODAS, {n(g.CODAS)},\n"
            f"     VTTS_{up}_FINALS, {n(g.FINALS)}, VTTS_{up}_DOUBLES, {n(g.DOUBLES)}, VTTS_{up}_FOREIGN, {n(g.FOREIGN)},\n"
            f"     VTTS_{up}_DIGRAPHS, {n(g.DIGRAPHS)}}},\n"
            f"#else\n    {{0}},\n#endif")
    es, id_, pt = normalize_es, normalize_id, normalize_pt
    out += ["/* es: number words (normalize_es) and the letters of g2p_es */"]
    out += c_list("VTTS_ES_ONES", list(es.ONES)) + c_list("VTTS_ES_TENS", list(es.TENS))
    out += c_list("VTTS_ES_HUNDREDS", list(es.HUNDREDS))
    assert [s for s, _, _ in es.SCALES] == [10 ** 18, 10 ** 12, 10 ** 6]
    out += ["static const char *const VTTS_ES_SCALES[3][2] = {  /* 10^18, 10^12, 10^6 */"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for _, a, b in es.SCALES] + ["};", ""]
    out += c_list("VTTS_ES_ORD_ONES", list(es.ORD_ONES)) + c_list("VTTS_ES_ORD_TENS", list(es.ORD_TENS))
    out += c_list("VTTS_ES_ORD_HUNDREDS", list(es.ORD_HUNDREDS))
    out += [f"#define VTTS_ES_VOWELS {c_str(g2p_es.VOWELS)}", f"#define VTTS_ES_FRONT {c_str(g2p_es.FRONT)}",
            f"#define VTTS_ES_ACCENTED {c_str(''.join(g2p_es.ACCENTED))}",
            f"#define VTTS_ES_ACCENTED_BASE {c_str(''.join(g2p_es.ACCENTED.values()))}", ""]
    out += ["/* id: number words (normalize_id) and the affixes and letters of g2p_id */"]
    out += c_list("VTTS_ID_ONES", list(id_.ONES))
    assert [s for s, _ in id_.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6]
    out += c_list("VTTS_ID_SCALES", [x for _, x in id_.SCALES])
    out += c_list("VTTS_ID_PREFIXES", list(g2p_id.PREFIXES)) + c_list("VTTS_ID_SUFFIXES", list(g2p_id.SUFFIXES))
    out += [f"#define VTTS_ID_VOWELS {c_str(g2p_id.VOWELS)}", ""]
    out += ["/* pt: number words (normalize_pt) and the letters of g2p_pt */"]
    out += c_list("VTTS_PT_ONES", list(pt.ONES)) + c_list("VTTS_PT_TENS", list(pt.TENS))
    out += c_list("VTTS_PT_HUNDREDS", list(pt.HUNDREDS))
    assert [s for s, _, _ in pt.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6, 10 ** 3]
    out += ["static const char *const VTTS_PT_SCALES[4][2] = {  /* 10^12, 10^9, 10^6, 10^3 */"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for _, a, b in pt.SCALES] + ["};", ""]
    out += c_list("VTTS_PT_ORD_ONES", list(pt.ORD_ONES)) + c_list("VTTS_PT_ORD_TENS", list(pt.ORD_TENS))
    out += c_list("VTTS_PT_ORD_HUNDREDS", list(pt.ORD_HUNDREDS))
    acc = {"acute": 1, "circ": 2, "tilde": 3, None: 0}
    out += [f"#define VTTS_PT_VOWEL_LETTERS {c_str(g2p_pt.VOWEL_LETTERS)}",
            f"#define VTTS_PT_FRONT {c_str(g2p_pt.FRONT)}",
            "/* BASE: letter, base vowel, accent (1 acute, 2 circumflex, 3 tilde, 0 none) */",
            "static const struct { uint32_t cp; char base; uint8_t accent; } VTTS_PT_BASE[] = {"]
    out += [f"    {{0x{ord(k):04X}, '{b}', {acc[a]}}}," for k, (b, a) in g2p_pt.BASE.items()]
    out += ["};", f"#define VTTS_PT_N_BASE {len(g2p_pt.BASE)}", ""]
    out += ["static const vtts_lt_lang VTTS_LT_LANGS[3] = {  /* es, id, pt */"] + descs + ["};", ""]
    return out


MS_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_ms_tables.h"


def malay_tables() -> list[str]:
    """Tables of the Malay front-end (ms/g2p_ms.py, ms/normalize_ms.py, lexicons/ms/): the
    vtts_lt_lang row of mode ms (the Indonesian letters, fold, clusters and foreign groups are
    shared with id, the e table is the Indonesian one under the Malay one), the Malay digraphs and
    letter sounds, numbers, month names and abbreviations, the day-part words of the time rule and
    the re.IGNORECASE variants of their letters. Included by vtts_text_lt.c after vtts_text_tables.h
    when VTTS_ENABLE_MS is set."""
    import re

    from vtts.frontend import latin
    from vtts.frontend.id import g2p_id
    from vtts.frontend.lexicons import load_words
    from vtts.frontend.ms import g2p_ms as g
    from vtts.frontend.ms import normalize_ms as nm

    tset = phoneme_set.TOKEN_SETS[phoneme_set.PAIR_MODES["ms"]]
    tok0 = phoneme_set.VOCAB_SIZE_V2
    assert all(t.startswith("MS:") for t in tset[tok0:])
    names = [t.split(":", 1)[1] for t in tset[tok0:]]
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Malay front-end tables (token set ms-en): src/vtts/frontend/ms and lexicons/ms; the letters,",
           " * fold, clusters and foreign groups are the Indonesian ones of vtts_text_tables.h. */",
           "#ifndef VTTS_TEXT_MS_TABLES_H", "#define VTTS_TEXT_MS_TABLES_H", "#include <stdint.h>", "",
           "#include \"vtts_text_tables.h\"", ""]
    out += c_list("VTTS_MS_TOKENS", names)
    abbrev = sorted(nm.ABBREVIATIONS, key=len, reverse=True)  # apply_abbreviations order
    out += ["static const char *const VTTS_MS_ABBREV[][2] = {"]
    out += [f"    {{{c_str(k)}, {c_str(nm.ABBREVIATIONS[k])}}}," for k in abbrev] + ["};", ""]
    letters = list(nm.LETTERS.items())
    out += ["static const vtts_lt_letter VTTS_MS_LETTERS[] = {"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in letters] + ["};", ""]
    out += _str_list("VTTS_MS_ACRONYM_WORDS", sorted(nm.ACRONYM_WORDS))
    assert all(isinstance(v, str) for v in (*nm.UNITS.values(), *nm.CURRENCY.values()))
    units = sorted(nm.UNITS, key=len, reverse=True)  # the alternation order of the regexes
    out += ["static const vtts_lt_reading VTTS_MS_UNITS[] = {"]
    out += [f"    {{{c_str(k)}, {c_str(nm.UNITS[k])}, {c_str(nm.UNITS[k])}}}," for k in units] + ["};", ""]
    cur = sorted(nm.CURRENCY, key=len, reverse=True)
    out += ["static const vtts_lt_reading VTTS_MS_CURRENCY[] = {"]
    out += [f"    {{{c_str(k)}, {c_str(nm.CURRENCY[k])}, {c_str(nm.CURRENCY[k])}}}," for k in cur] + ["};", ""]
    assert nm.MONEY_AFTER.pattern.endswith(r"\s?(€|£|¥|\$)")
    out += ["static const vtts_lt_reading VTTS_MS_CURRENCY_AFTER[] = {  /* MONEY_AFTER alternation */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.CURRENCY[k])}, {c_str(nm.CURRENCY[k])}}}," for k in ("€", "£", "¥", "$")]
    out += ["};", ""]
    assert all(len(k) == 1 for k in nm.SYMBOLS)
    out += ["static const vtts_lt_letter VTTS_MS_SYMBOLS[] = {"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.SYMBOLS.items()] + ["};", ""]
    out += c_list("VTTS_MS_MONTHS", list(nm.MONTHS))
    native = sorted(load_words("ms", "native"))
    out += _str_list("VTTS_MS_NATIVE", native)
    keys = sorted(latin._table_keys("ms"))
    out += _str_list("VTTS_MS_TABLE_KEYS", keys)
    ovr = g.override_table()
    out += ["static const char *const VTTS_MS_OVERRIDES[][2] = {  /* lexicons/id/overrides.tsv under lexicons/ms/ */"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ovr.items()] + ["};", ""]
    out += _str_list("VTTS_MS_UNSTRESSED", sorted(g.UNSTRESSED))
    # shared with Indonesian: fold() (the same function), letters, clusters, doubles, foreign groups
    assert g.fold is g2p_id.fold and g.VOWELS == g2p_id.VOWELS and latin.LATIN_PAIRS["ms"] == ""
    assert g.DIGRAPHS[:len(g2p_id.DIGRAPHS)] == g2p_id.DIGRAPHS
    out += ["static const char *const VTTS_MS_DIGRAPHS[][2] = {  /* valid_spelling: replaced in this order */"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for a, b in g.DIGRAPHS] + ["};", ""]
    out += ["/* rule_phonemes: digraphs read as one sound, letter sounds (one or two letters) */"]
    out += c_list("VTTS_MS_DIGRAPH_SOUNDS", list(g.DIGRAPH_SOUNDS))
    out += ["static const char *const VTTS_MS_LETTER_SOUNDS[][2] = {"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for a, b in g.LETTER_SOUNDS.items()] + ["};", ""]
    assert all(len(v) <= 2 for v in g.LETTER_SOUNDS.values()) and all(len(d) == 2 for d in g.DIGRAPH_SOUNDS)
    out += ["/* numbers: digit names (ONES), the number 0 (ZERO), scales 10^12, 10^9, 10^6, decimal point */"]
    out += c_list("VTTS_MS_ONES", list(nm.ONES))
    assert [s for s, _ in nm.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6]
    out += c_list("VTTS_MS_SCALES", [x for _, x in nm.SCALES])
    out += [f"#define VTTS_MS_ZERO {c_str(nm.ZERO)}", f"#define VTTS_MS_POINT {c_str(nm.POINT)}", ""]
    # DATE_ABBR alternation: the abbreviations longest first, then the full month names
    alts = sorted(nm.MONTH_ABBR, key=len, reverse=True) + [m for m in nm.MONTHS if m]
    assert ("|".join(alts)) in nm.DATE_ABBR.pattern and all(a.isascii() and a.isalpha() for a in alts)
    out += ["static const struct { const char *key; uint8_t month; } VTTS_MS_MONTH_ALTS[] = {  /* DATE_ABBR order */"]
    out += [f"    {{{c_str(a)}, {nm.MONTH_ABBR.get(a) or nm.MONTHS.index(a)}}}," for a in alts] + ["};", ""]
    day = re.search(r"\(\?:([a-z |]+)\)\)$", nm.TIME.pattern).group(1).split("|")
    out += c_list("VTTS_MS_DAY_PARTS", day)
    letters_i = sorted(set("".join(alts + day).replace(" ", "")) | set("pukuljam"))
    var = {ch: [c for c in range(0x80, 0x110000)
                if not 0xD800 <= c < 0xE000 and re.fullmatch(ch, chr(c), re.IGNORECASE)] for ch in letters_i}
    pairs = [(c, ch) for ch in letters_i for c in var[ch]]
    out += ["/* re.IGNORECASE matches of the ASCII letters above outside ASCII: (code point, letter) */",
            "static const uint32_t VTTS_MS_ICASE[][2] = {"]
    out += [f"    {{0x{c:X}, '{ch}'}}," for c, ch in pairs] + ["};", ""]
    n = len
    out += ["static const vtts_lt_lang VTTS_MS_LANG = {",
            f"    {c_str('ms')}, {tok0}, {n(names)}, {n(tset)}, VTTS_MS_TOKENS, VTTS_MS_ABBREV, {n(abbrev)},",
            f"    {c_str(latin_norm_drop())}, VTTS_MS_LETTERS, {n(letters)}, VTTS_MS_ACRONYM_WORDS, {n(nm.ACRONYM_WORDS)},",
            f"    VTTS_MS_UNITS, {n(units)}, VTTS_MS_CURRENCY, {n(cur)}, VTTS_MS_SYMBOLS, {n(nm.SYMBOLS)},",
            "    \"\", \"\", VTTS_MS_MONTHS,",
            f"    VTTS_MS_NATIVE, {n(native)}, VTTS_MS_TABLE_KEYS, {n(keys)}, VTTS_MS_OVERRIDES, {n(ovr)},",
            f"    VTTS_MS_UNSTRESSED, {n(g.UNSTRESSED)}, \"\", {c_str(''.join(sorted(g2p_id.LETTERS - set('abcdefghijklmnopqrstuvwxyz'))))},",
            f"    VTTS_ID_FOLD, sizeof VTTS_ID_FOLD / sizeof *VTTS_ID_FOLD, VTTS_ID_ONSETS, {n(g2p_id.ONSETS)},",
            f"    VTTS_ID_CODAS, {n(g2p_id.CODAS)}, VTTS_ID_FINALS, {n(g2p_id.FINALS)}, VTTS_ID_DOUBLES, {n(g2p_id.DOUBLES)},",
            f"    VTTS_ID_FOREIGN, {n(g2p_id.FOREIGN)}, VTTS_MS_DIGRAPHS, {n(g.DIGRAPHS)}}};", ""]
    out += ["#endif", ""]
    return out


def latin_norm_drop() -> str:
    from vtts.frontend import latin_norm

    return latin_norm.DROP


TH_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_th_tables.h"
TH0 = 0x0E00  # Thai letters are coded as code point - 0x0E00 (0x01..0x4E) in the C tables


def th_bytes(s: str) -> str:
    """A C string literal of Thai letters as single-byte codes (code point - 0x0E00)."""
    out = []
    for ch in s:
        c = ord(ch) - TH0
        assert 1 <= c <= 0x4E, ch
        out.append(f"\\x{c:02x}")
    return '"' + "".join(out) + '"'


def th_word_blob(words: list[str], block: int) -> tuple[bytes, list[int]]:
    """Sorted words, front coded: a byte 0x80 | (letters shared with the previous word) starts each
    word, its other letters follow as codes < 0x80; the first word of each block of `block` words
    shares nothing (binary search over the blocks). A final 0x80 ends the data."""
    data, offsets, prev = bytearray(), [], ""
    for k, w in enumerate(words):
        p = 0
        if k % block:
            while p < min(len(prev), len(w)) and prev[p] == w[p]:
                p += 1
        else:
            offsets.append(len(data))
        assert p < 0x80
        data.append(0x80 | p)
        data.extend(ord(ch) - TH0 for ch in w[p:])
        prev = w
    data.append(0x80)
    return bytes(data), offsets


def thai_tables() -> list[str]:
    """Tables of the Thai front-end (th/g2p_th.py, th/normalize_th.py, lexicons/th/): letter
    classes and sounds, the vowel patterns, the word list (front coded), the respellings and the
    strings of the normalizer. Thai letters are coded as code point - 0x0E00."""
    import re

    from vtts.frontend.th import g2p_th as g
    from vtts.frontend.th import normalize_th as nt

    t = phoneme_set.token_index(phoneme_set.TOKEN_SET_THEN).__getitem__
    ini, vow, fin = phoneme_set.TH_INITIALS, phoneme_set.TH_VOWELS, phoneme_set.TH_FINALS
    assert [t(f"TH:I:{c}") for c in ini] == list(range(t(f"TH:I:{ini[0]}"), t(f"TH:I:{ini[0]}") + len(ini)))
    assert [t(f"TH:V:{v}") for v in vow] == list(range(t(f"TH:V:{vow[0]}"), t(f"TH:V:{vow[0]}") + len(vow)))
    assert [t(f"TH:F:{f}") for f in fin] == list(range(t(f"TH:F:{fin[0]}"), t(f"TH:F:{fin[0]}") + len(fin)))
    assert [t(f"TH:T{i}") for i in range(1, 6)] == list(range(t("TH:T1"), t("TH:T1") + 5))

    def cname(s: str) -> str:
        return s.replace("?", "Q")

    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Thai front-end tables (token set th-en): src/vtts/frontend/th and lexicons/th.",
           " * Thai letters are coded as code point - 0x0E00 (0x01..0x4E). */",
           "#ifndef VTTS_TEXT_TH_TABLES_H", "#define VTTS_TEXT_TH_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_THEN_VOCAB {phoneme_set.VOCAB_SIZE_THEN}",
           f"#define VTTS_THEN_I0 {t('TH:I:' + ini[0])}  /* + initial index */",
           f"#define VTTS_THEN_V0 {t('TH:V:' + vow[0])}  /* + vowel index */",
           f"#define VTTS_THEN_F0 {t('TH:F:' + fin[0])}  /* + final index */",
           f"#define VTTS_THEN_T1 {t('TH:T1')}  /* + tone - 1 */", ""]
    out += [f"#define VTTS_TH_I_{cname(c)} {k}" for k, c in enumerate(ini)] + [""]
    out += [f"#define VTTS_TH_V_{v} {k}" for k, v in enumerate(vow)] + [""]
    out += [f"#define VTTS_TH_F_{f} {k + 1}  /* finals are index + 1 (0 = none) */" for k, f in enumerate(fin)] + [""]
    son = sum(1 << ini.index(s) for s in g._SONORANT_SOUNDS)
    out += [f"#define VTTS_TH_SONORANT_INITIALS 0x{son:X}u  /* bit per initial index (_SONORANT_SOUNDS) */",
            "#define VTTS_TH_LIVE_FINALS 0x" + format(sum(1 << (fin.index(f) + 1) for f in ("m", "n", "ng", "w", "j")), "X")
            + "u  /* bit per final code (live syllable) */",
            "#define VTTS_TH_STOP_FINALS 0x" + format(sum(1 << (fin.index(f) + 1) for f in ("k", "p", "t")), "X")
            + "u  /* bit per final code (k p t) */", ""]
    costs = {"SYLLABLE": g.SYLLABLE, "UNWRITTEN_O": g.UNWRITTEN_O, "UNWRITTEN_A": g.UNWRITTEN_A,
             "WORD_FINAL_A": g.WORD_FINAL_A, "SPLIT_LEAD": g.SPLIT_LEAD, "OPEN_PREPOSED": g.OPEN_PREPOSED}
    out += [f"#define VTTS_TH_COST_{k} {v}" for k, v in costs.items()] + [""]
    # per-letter flags
    flag_bits = {"MID": 0, "HIGH": 1, "LOW": 2, "LOW_SONORANT": 3, "PREPOSED": 4, "TONE_MARK": 5,
                 "ABOVE_BELOW": 6, "DEPENDENT": 7, "LINKING": 8, "SILENT_R": 9, "WORD": 10}
    sets = {"MID": g.MID, "HIGH": g.HIGH, "LOW": g.LOW, "LOW_SONORANT": g.LOW_SONORANTS, "PREPOSED": g.PREPOSED,
            "TONE_MARK": g.TONE_MARKS, "ABOVE_BELOW": g.ABOVE_BELOW, "DEPENDENT": g.DEPENDENT,
            "LINKING": g.LINKING, "SILENT_R": "".join(g.SILENT_R),
            "WORD": "".join(chr(c) for c in range(TH0, TH0 + 0x80) if re.match(r"\w", chr(c)))}
    out += [f"#define VTTS_TH_{k} 0x{1 << b:X}u" for k, b in flag_bits.items()]
    out += ["/* letter code -> {flags, initial index (255: none), final code (0: none)}; WORD: Python \\w */",
            "static const struct { uint16_t flags; uint8_t initial, final; } VTTS_TH_LETTERS[128] = {"]
    rows = []
    for c in range(128):
        ch = chr(TH0 + c)
        flags = sum(1 << flag_bits[k] for k, s in sets.items() if ch in s and c)
        i = ini.index(g.INITIAL[ch]) if ch in g.INITIAL else 255
        f = fin.index(g.FINAL[ch]) + 1 if ch in g.FINAL else 0
        rows.append(f"{{0x{flags:X}, {i}, {f}}}")
    out += ["    " + ", ".join(rows[k:k + 8]) + "," for k in range(0, 128, 8)] + ["};", ""]
    out += [f"static const char VTTS_TH_CLUSTERS[] = {th_bytes(''.join(sorted(g.CLUSTERS)))};  /* pairs */",
            f"#define VTTS_TH_N_CLUSTERS {len(g.CLUSTERS)}", ""]
    fk = {"": 0, "F": 1, "f": 2}
    out += ["/* VOWELS: preposed letter (0: none), letters after the initial, vowel index, short,",
            " * final kind (0 none, 1 required, 2 optional, 3 the final `eq` itself) */",
            "static const struct { uint8_t pre; const char *letters; uint8_t vowel, shrt, kind, eq; } VTTS_TH_VOWELS[] = {"]
    for pre, letters, vowel, f in g.VOWELS:
        short = vowel in g.SHORT or vowel.endswith(".")
        v = vow.index(vowel.rstrip("."))
        kind, eq = (3, fin.index(f[1:]) + 1) if f.startswith("=") else (fk[f], 0)
        p = f"0x{ord(pre) - TH0:02X}" if pre else "0"
        out.append(f"    {{{p}, {th_bytes(letters)}, {v}, {int(short)}, {kind}, {eq}}},  /* {pre}-{letters} {vowel} {f} */")
    out += ["};", f"#define VTTS_TH_N_VOWELS {len(g.VOWELS)}", ""]
    # words (word list plus the keys of the respellings, like word_set())
    words = sorted(g.word_set())
    block = 16
    data, offsets = th_word_blob(words, block)
    out += [f"#define VTTS_TH_N_WORDS {len(words)}", f"#define VTTS_TH_WORD_BLOCK {block}",
            f"#define VTTS_TH_N_BLOCKS {len(offsets)}", f"#define VTTS_TH_MAX_WORD {max(map(len, words))}",
            f"#define VTTS_TH_WORDS_BYTES {len(data)}",
            "/* lexicons/th/words.txt and the keys of overrides.tsv, sorted and front coded */",
            f"static const uint8_t VTTS_TH_WORDS[{len(data)}] = {{"]
    hexes = [f"0x{b:02X}" for b in data]
    out += ["    " + ",".join(hexes[k:k + 24]) + "," for k in range(0, len(hexes), 24)] + ["};"]
    out += [f"static const uint32_t VTTS_TH_BLOCKS[{len(offsets)}] = {{"]
    out += ["    " + ", ".join(map(str, offsets[k:k + 12])) + "," for k in range(0, len(offsets), 12)] + ["};", ""]
    table = g.override_table()
    out += ["/* lexicons/th/overrides.tsv: word -> respelling, pieces separated by 0x7F */",
            "static const struct { const char *word, *reading; } VTTS_TH_OVERRIDES[] = {"]
    for k, v in table.items():
        reading = '"\\x7f"'.join(th_bytes(p) for p in v)
        out.append(f"    {{{th_bytes(k)}, {reading}}},  /* {k} {'-'.join(v)} */")
    out += ["};", f"#define VTTS_TH_N_OVERRIDES {len(table)}", f"#define VTTS_TH_MAX_OVERRIDE {max(map(len, table))}", ""]
    # normalizer strings
    out += c_list("VTTS_TH_DIGITS", list(nt.DIGITS)) + c_list("VTTS_TH_PLACES", list(nt.PLACES))
    out += [f"#define VTTS_TH_MILLION {c_str(nt.MILLION)}", ""] + c_list("VTTS_TH_MONTHS", list(nt.MONTHS))
    plain = ["ฯลฯ", "ฯพณฯ", "กรุงเทพฯ"]  # replaced before the dotted abbreviations (normalize_th)
    out += ["static const char *const VTTS_TH_ABBREV_PLAIN[][2] = {  /* str.replace, in this order */"]
    out += [f"    {{{c_str(k)}, {c_str(nt.ABBREVIATIONS[k])}}}," for k in plain] + ["};",
            f"#define VTTS_TH_N_ABBREV_PLAIN {len(plain)}", ""]
    dotted = sorted((k for k in nt.ABBREVIATIONS if "." in k), key=len, reverse=True)  # ABBREV alternation
    out += ["static const char *const VTTS_TH_ABBREV[][2] = {  /* alternation order */"]
    out += [f"    {{{c_str(k)}, {c_str(nt.ABBREVIATIONS[k])}}}," for k in dotted] + ["};",
            f"#define VTTS_TH_N_ABBREV {len(dotted)}", ""]
    units = sorted(nt.UNITS, key=len, reverse=True)  # the alternation order of UNIT
    out += ["static const char *const VTTS_TH_UNITS[][2] = {  /* alternation order */"]
    out += [f"    {{{c_str(u)}, {c_str(nt.UNITS[u])}}}," for u in units] + ["};", f"#define VTTS_TH_N_UNITS {len(units)}", ""]
    out += ["static const struct { uint32_t cp; const char *name; } VTTS_TH_CURRENCY[] = {"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nt.CURRENCY.items()]
    out += ["};", f"#define VTTS_TH_N_CURRENCY {len(nt.CURRENCY)}", ""]
    out += ["static const struct { uint32_t cp; const char *text; uint8_t glue; } VTTS_TH_SYMBOLS[] = {  /* in this order */"]
    for k, v in nt.SYMBOLS.items():
        assert len(k) == 1
        out.append(f"    {{0x{ord(k):04X}, {c_str(v)}, {int(v.strip() == v)}}},")
    out += ["};", f"#define VTTS_TH_N_SYMBOLS {len(nt.SYMBOLS)}", ""]
    out += ["static const uint32_t VTTS_TH_DROP[] = {  /* replaced by a space */"]
    drop = [f"0x{ord(c):04X}" for c in nt._DROP]
    out += ["    " + ", ".join(drop[i:i + 8]) + "," for i in range(0, len(drop), 8)]
    out += ["};", f"#define VTTS_TH_N_DROP {len(drop)}", ""]
    assert nt._FULLWIDTH == {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
    assert nt._GLUE == "\x01"
    out += ["#endif", ""]
    return out


FR_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_fr_tables.h"


def french_tables() -> list[str]:
    """Tables of the French front-end (fr/normalize_fr.py, fr/g2p_fr.py, the fr rules of lang.py and
    latin.py) for runtime/src/vtts_text_fr.c: token names, normalizer strings in the order the regexes
    and replacements use them, liaison word lists, the lexicons/fr tables, fold() of every code point
    as runs and the spelling-check clusters. Sorted lists are searched with strcmp (UTF-8 byte order
    is code point order, as Python's sorted())."""
    import re

    from vtts.frontend import lang, latin
    from vtts.frontend.fr import g2p_fr as g
    from vtts.frontend.fr import normalize_fr as nf
    from vtts.frontend.lexicons import load_words

    def s_list(name, items):
        return _str_list(name, items) + [f"#define {name.replace('VTTS_FR_', 'VTTS_FR_N_', 1)} {len(list(items))}", ""]

    def pairs(name, items):
        items = list(items)
        out = [f"static const char *const {name}[{len(items)}][2] = {{"]
        out += [f"    {{{c_str(a)}, {c_str(b)}}}," for a, b in items] + ["};"]
        return out + [f"#define {name.replace('VTTS_FR_', 'VTTS_FR_N_', 1)} {len(items)}", ""]

    tset = phoneme_set.TOKENS_FREN
    tok0 = phoneme_set.VOCAB_SIZE_V2
    names = [t.split(":", 1)[1] for t in tset[tok0:]]
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "#ifndef VTTS_TEXT_FR_TABLES_H", "#define VTTS_TEXT_FR_TABLES_H", "#include <stdint.h>", "",
           f"/* ---- French (token set fr-en; ids 0..{tok0 - 1} are the v2 ids) ---- */",
           f"#define VTTS_FR_TOK0 {tok0}", f"#define VTTS_FR_VOCAB {len(tset)}"]
    out += s_list("VTTS_FR_TOKENS", names)
    # normalize_fr
    out += c_list("VTTS_FR_ONES", list(nf.ONES)) + c_list("VTTS_FR_TENS", list(nf.TENS))
    out += c_list("VTTS_FR_MONTHS", list(nf.MONTHS))
    assert list(nf.LETTERS) == list("abcdefghijklmnopqrstuvwxyz")
    out += c_list("VTTS_FR_LETTER_NAMES", list(nf.LETTERS.values()))
    out += s_list("VTTS_FR_ACRONYM_WORDS", sorted(nf.ACRONYM_WORDS))
    abbrev = sorted(nf.ABBREVIATIONS, key=len, reverse=True)  # _apply_abbreviations order
    out += pairs("VTTS_FR_ABBREV", [(k, nf.ABBREVIATIONS[k]) for k in abbrev])
    units = sorted(nf.UNITS, key=len, reverse=True)  # the alternation order of UNIT
    out += ["typedef struct { const char *key, *one, *many; uint8_t fem; } vtts_fr_unit;",
            f"static const vtts_fr_unit VTTS_FR_UNITS[{len(units)}] = {{"]
    out += [f"    {{{c_str(k)}, {c_str(nf.UNITS[k][0])}, {c_str(nf.UNITS[k][1])}, {int(nf.UNITS[k][2])}}},"
            for k in units] + ["};", f"#define VTTS_FR_N_UNITS {len(units)}", ""]
    cur = sorted(nf.CURRENCY, key=len, reverse=True)  # the alternation order of MONEY_BEFORE
    assert set(nf.MONEY_AFTER_KEYS) <= set(cur)
    out += ["typedef struct { const char *key, *one, *many, *cent1, *cents; } vtts_fr_currency;",
            f"static const vtts_fr_currency VTTS_FR_CURRENCY[{len(cur)}] = {{"]
    out += [f"    {{{', '.join(c_str(x) for x in (k, *nf.CURRENCY[k]))}}}," for k in cur]
    out += ["};", f"#define VTTS_FR_N_CURRENCY {len(cur)}", ""]
    out += s_list("VTTS_FR_MONEY_AFTER", list(nf.MONEY_AFTER_KEYS))
    out += s_list("VTTS_FR_SCALES_AFTER", list(nf.SCALES_AFTER))
    out += [f"#define VTTS_FR_N_SCALES_BEFORE {len(nf.SCALES_BEFORE)}  /* the first ones of SCALES_AFTER */"]
    assert nf.SCALES_AFTER[:len(nf.SCALES_BEFORE)] == nf.SCALES_BEFORE
    assert all(len(k) == 1 for k in nf.SYMBOLS)
    out += ["typedef struct { uint32_t cp; const char *text; } vtts_fr_symbol;",
            f"static const vtts_fr_symbol VTTS_FR_SYMBOLS[{len(nf.SYMBOLS)}] = {{  /* replaced in this order */"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nf.SYMBOLS.items()]
    out += ["};", f"#define VTTS_FR_N_SYMBOLS {len(nf.SYMBOLS)}", ""]
    from vtts.frontend import latin_norm

    group_spaces = nf._SP.strip("[]")
    out += [f"#define VTTS_FR_DROP {c_str(latin_norm.DROP.replace('(', '').replace(')', ''))}",
            f"#define VTTS_FR_COMMA {c_str(nf.MARK_WORDS[','])}", f"#define VTTS_FR_PERIOD {c_str(nf.MARK_WORDS['.'])}",
            f"#define VTTS_FR_GROUP_SPACES {c_str(group_spaces)}", ""]
    out += s_list("VTTS_FR_FEMININE", sorted(nf.FEMININE))
    # liaison
    out += pairs("VTTS_FR_LIAISON", sorted(nf.LIAISON.items()))
    out += pairs("VTTS_FR_DENASAL", sorted(nf.DENASAL.items()))
    for name in ("NO_LIAISON", "H_ASPIRE", "NUMBER_WORDS", "UNIT_WORDS", "PREPOSITIONS"):
        out += s_list(f"VTTS_FR_{name}", sorted(getattr(nf, name)))
    # g2p_fr
    ovr = g.override_table()
    out += pairs("VTTS_FR_OVERRIDES", sorted(ovr.items()))
    for name in ("final", "ent", "er", "ment_verbs", "c_silent", "l_silent", "f_silent"):
        out += s_list(f"VTTS_FR_W_{name.upper()}", sorted(load_words("fr", name)))
    out += pairs("VTTS_FR_PREFIX", sorted((k, " ".join(v)) for k, v in g.PREFIX.items()))
    for name in ("CH_HARD", "GN_SPLIT", "ILL_L", "X_Z", "X_S", "EX_GZ_HEADS"):
        out += s_list(f"VTTS_FR_{name}", list(getattr(g, name)))
    out += s_list("VTTS_FR_ONSET2", sorted(g.ONSET2))
    out += [f"#define VTTS_FR_VOWELS {c_str(''.join(sorted(g.VOWELS - {g.NASAL_E})))}",
            f"#define VTTS_FR_FRONT {c_str(''.join(sorted(g.FRONT - {g.NASAL_E})))}",
            f"#define VTTS_FR_LETTERS_EXTRA {c_str(''.join(sorted(g.LETTERS - set('abcdefghijklmnopqrstuvwxyz'))))}",
            f"#define VTTS_FR_NASAL_E 0x{ord(g.NASAL_E):04X}",
            f"#define VTTS_FR_SILENT_E_VOWELS {c_str(g.SILENT_E_VOWELS)}", ""]
    # fold(): one code point -> "" | one letter (runs) | several letters (FOLD)
    for c in range(0x80):
        want = chr(c).lower() if chr(c).isalpha() else ("'" if chr(c) == "'" else "")
        assert g.fold(chr(c)) == want, c
    folded = [(c, g.fold(chr(c))) for c in range(0x80, 0x110000) if not 0xD800 <= c < 0xE000]
    multi = [(c, f) for c, f in folded if len(f) > 1]
    single = [(c, ord(f)) for c, f in folded if len(f) == 1]
    runs: list[list[int]] = []  # start, count, first result, step 0/1
    for c, f in single:
        if runs and c == runs[-1][0] + runs[-1][1] and runs[-1][1] < 65535:
            r = runs[-1]
            if r[1] == 1 and f in (r[2], r[2] + 1):
                r[1], r[3] = 2, f - r[2]
                continue
            if r[1] > 1 and f == r[2] + r[1] * r[3]:
                r[1] += 1
                continue
        runs.append([c, 1, f, 0])
    out += ["typedef struct { uint32_t start; uint16_t count; uint16_t first; uint8_t step; } vtts_fr_fold;",
            f"static const vtts_fr_fold VTTS_FR_FOLD[{len(runs)}] = {{"]
    out += ["    " + " ".join(f"{{0x{a:X}, {n}, 0x{f:02X}, {s}}}," for a, n, f, s in runs[i:i + 5])
            for i in range(0, len(runs), 5)] + ["};", f"#define VTTS_FR_N_FOLD {len(runs)}", ""]
    out += ["typedef struct { uint32_t cp; const char *text; } vtts_fr_multi;",
            f"static const vtts_fr_multi VTTS_FR_FOLD_MULTI[{len(multi)}] = {{"]
    out += [f"    {{0x{c:04X}, {c_str(f)}}}," for c, f in multi] + ["};", f"#define VTTS_FR_N_FOLD_MULTI {len(multi)}", ""]
    # tagging: lang._fr_tags, latin.latin_word_lang
    out += [f"#define VTTS_FR_OWN {c_str(latin.LATIN_PAIRS['fr'])}"]
    out += s_list("VTTS_FR_CLITICS", list(lang.FR_CLITICS))
    out += s_list("VTTS_FR_NATIVE", sorted(load_words("fr", "native")))
    out += s_list("VTTS_FR_TABLE_KEYS", sorted(latin._table_keys("fr")))
    for attr in ("ONSETS", "CODAS", "FINALS", "DOUBLES"):
        out += s_list(f"VTTS_FR_{attr}", sorted(getattr(g, attr)))
    out += s_list("VTTS_FR_FOREIGN", list(g.FOREIGN))
    out += pairs("VTTS_FR_DIGRAPHS", list(g.DIGRAPHS))
    # re.IGNORECASE variants of the letters of the case-insensitive French patterns
    letters = sorted(set("tdilensozyjmcqu"))
    var = {ch: [c for c in range(0x110000)
                if not 0xD800 <= c < 0xE000 and re.fullmatch(ch, chr(c), re.IGNORECASE)] for ch in letters}
    width = max(len(v) for v in var.values()) + 1
    out += [f"static const uint32_t VTTS_FR_ICASE[{len(letters)}][{width}] = {{  /* re.I variants (0 ends) */"]
    out += [f"    {{{', '.join(f'0x{c:X}' for c in var[ch])}{', 0' * (width - len(var[ch]))}}},  /* {ch} */"
            for ch in letters]
    out += ["};", f"#define VTTS_FR_N_ICASE {len(letters)}", "", "#endif", ""]
    return out


DE_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_de_tables.h"
DE_CODE = {"ä": "A", "ö": "O", "ü": "U", "ß": "Z"}  # German letters as single bytes in the C tables


def de_code(s: str) -> str:
    """German letters of the g2p as bytes: a-z as is, ä ö ü ß as A O U Z."""
    out = "".join(DE_CODE.get(ch, ch) for ch in s)
    assert out.isascii(), s
    return out


def de_list(name: str, items, coded: bool = True) -> list[str]:
    items = [de_code(x) if coded else x for x in items]
    return _str_list(name, items) + [f"#define {name.replace('VTTS_DE_', 'VTTS_DE_N_')} {len(items)}", ""]


def german_tables() -> list[str]:
    """Tables of the German front-end (de/g2p_de.py, de/normalize_de.py, lexicons/de/): token names,
    prefixes and suffixes, the stem list and exception table, the stress and spelling lists, fold()
    of every code point, the strings of the normalizer and the word lists of the tagger. g2p letters
    are coded as single bytes (de_code); normalizer strings are UTF-8."""
    from vtts.frontend import latin_norm
    from vtts.frontend.de import g2p_de as g
    from vtts.frontend.de import normalize_de as nd
    from vtts.frontend.lexicons import load_words

    tset = phoneme_set.TOKEN_SETS["de-en"]
    tok0 = phoneme_set.VOCAB_SIZE_V2
    names = [t.split(":", 1)[1] for t in tset[tok0:]]
    idx = {nm: tok0 + k for k, nm in enumerate(names)}

    def ids(ph: str) -> str:
        return '"' + "".join(f"\\x{idx[p]:02x}" for p in ph.split()) + '"'

    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* German front-end (token set de-en): g2p letters as bytes, a-z and A O U Z for ä ö ü ß */",
           "#ifndef VTTS_TEXT_DE_TABLES_H", "#define VTTS_TEXT_DE_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_DE_TOK0 {tok0}", f"#define VTTS_DE_VOCAB {len(tset)}",
           f"#define VTTS_DE_N_VOWELS {len(phoneme_set.DE_VOWELS)}  /* stressed id = id + this */"]
    out += c_list("VTTS_DE_PH", names) + [f"#define VTTS_DE_N_PH {len(names)}", ""]
    # prefixes in dict order: text, kind (0 up, 1 sp), phoneme ids
    out += ["static const struct { const char *text; uint8_t sp; const char *ids; } VTTS_DE_PREFIXES[] = {"]
    for k, (kind, ph) in g.PREFIXES.items():
        out.append(f"    {{{c_str(de_code(k))}, {int(kind == 'sp')}, {ids(ph)}}},")
    out += ["};", f"#define VTTS_DE_N_PREFIXES {len(g.PREFIXES)}", ""]
    out += de_list("VTTS_DE_INSEPARABLE", sorted(g.INSEPARABLE_TOO))
    out += de_list("VTTS_DE_VERB_ENDINGS", sorted(g.VERB_ENDINGS))
    out += de_list("VTTS_DE_VOWEL_SUFFIXES", sorted(g.VOWEL_SUFFIXES))
    out += de_list("VTTS_DE_DERIVATION", sorted(g.DERIVATION))
    out += de_list("VTTS_DE_INFLECTION", sorted(g.INFLECTION))
    out += de_list("VTTS_DE_LINKERS", sorted(g.LINKERS))
    out += de_list("VTTS_DE_ALL_SUFFIXES", g.ALL_SUFFIXES)
    out += ["static const char *const VTTS_DE_SUFFIX_READING[][2] = {"]
    out += [f"    {{{c_str(de_code(k))}, {c_str(de_code(v))}}}," for k, v in g.SUFFIX_READING.items()]
    out += ["};", f"#define VTTS_DE_N_SUFFIX_READING {len(g.SUFFIX_READING)}", ""]
    out += de_list("VTTS_DE_NUMBER_MORPHS", g.NUMBER_MORPHS)
    out += de_list("VTTS_DE_NUMBER_MORPHS_LONG", sorted(g.NUMBER_MORPHS, key=len, reverse=True))
    out += de_list("VTTS_DE_NUMBER_TAILS", g.NUMBER_TAILS)
    out += de_list("VTTS_DE_ONSETS", sorted(g.ONSETS))
    out += de_list("VTTS_DE_INITIAL_CH_S", g.INITIAL_CH_S)
    out += de_list("VTTS_DE_CONS_GRAPHEMES", g.CONS_GRAPHEMES)
    out += ["static const char *const VTTS_DE_DIGRAPHS[][2] = {"]
    out += [f"    {{{c_str(de_code(k))}, {c_str(v)}}}," for k, v in g.DIGRAPHS.items()]
    out += ["};", f"#define VTTS_DE_N_DIGRAPHS {len(g.DIGRAPHS)}", ""]
    out += ["static const char *const VTTS_DE_LONG_SHORT[][3] = {  /* letter, long, short */"]
    out += [f"    {{{c_str(de_code(k))}, {c_str(g.LONG[k])}, {c_str(g.SHORT[k])}}}," for k in g.LONG]
    out += ["};", f"#define VTTS_DE_N_LONG_SHORT {len(g.LONG)}", ""]
    out += [f"#define VTTS_DE_VOWELS {c_str(de_code(g.VOWELS))}", f"#define VTTS_DE_FRONT {c_str(de_code(g.FRONT))}"]
    out += de_list("VTTS_DE_BACK", g.BACK)
    # stress rules
    for k, (bef, grp, aft, tails, na) in enumerate(g.STRESSED_ENDINGS):
        out += _str_list(f"VTTS_DE_SE{k}_B", [de_code(x) for x in bef])
        out += _str_list(f"VTTS_DE_SE{k}_G", [de_code(x) for x in grp])
        out += _str_list(f"VTTS_DE_SE{k}_T", [de_code(x) for x in tails])
        out += _str_list(f"VTTS_DE_SE{k}_N", [de_code(x) for x in na])
    out += ["typedef struct { const char *const *b; int nb; const char *const *g; int ng; const char *after;",
            "                 const char *const *t; int nt; const char *const *na; int nna; } vtts_de_rule;",
            "static const vtts_de_rule VTTS_DE_STRESSED_ENDINGS[] = {"]
    for k, (bef, grp, aft, tails, na) in enumerate(g.STRESSED_ENDINGS):
        out.append(f"    {{VTTS_DE_SE{k}_B, {len(bef)}, VTTS_DE_SE{k}_G, {len(grp)}, {c_str(de_code(aft))}, "
                   f"VTTS_DE_SE{k}_T, {len(tails)}, VTTS_DE_SE{k}_N, {len(na)}}},")
    out += ["};", f"#define VTTS_DE_N_STRESSED_ENDINGS {len(g.STRESSED_ENDINGS)}", ""]
    out += de_list("VTTS_DE_NOT_STRESSED_ENDS", g.NOT_STRESSED_ENDS)
    out += de_list("VTTS_DE_NOT_STRESSED_TAILS", g.NOT_STRESSED_TAILS)
    out += de_list("VTTS_DE_NOT_STRESSED_WORDS", sorted(g.NOT_STRESSED_WORDS))
    out += de_list("VTTS_DE_BEFORE_ENDINGS", g.BEFORE_ENDINGS)
    out += de_list("VTTS_DE_STRESSED_IK", sorted(g.STRESSED_IK))
    out += de_list("VTTS_DE_OREN_TAILS", g.OREN_TAILS)
    out += de_list("VTTS_DE_UNSTRESSED_IE", g.UNSTRESSED_IE)
    out += de_list("VTTS_DE_STRESSED_IEN", g.STRESSED_IEN)
    out += de_list("VTTS_DE_FOREIGN_ENDS", g.FOREIGN_ENDS)
    out += de_list("VTTS_DE_FOREIGN_ENDS_IER", g.FOREIGN_ENDS_IER)
    out += [f"#define VTTS_DE_PENULT_VOWELS {c_str(de_code(g.PENULT_VOWELS))}",
            f"#define VTTS_DE_PENULT_E_BEFORE {c_str(g.PENULT_E_BEFORE)}",
            f"#define VTTS_DE_PENULT_CONS {c_str(g.PENULT_CONS)}",
            f"#define VTTS_DE_FULL_VOWEL_ENDING {c_str(g.FULL_VOWEL_ENDING)}", ""]
    out += de_list("VTTS_DE_TI_ENDS", g.TI_ENDS)
    out += de_list("VTTS_DE_IE_HIATUS_ENDS", g.IE_HIATUS_ENDS)
    out += de_list("VTTS_DE_IG_REST", sorted(g.IG_REST))
    out += de_list("VTTS_DE_NATIVE_V_START", g.NATIVE_V_START)
    out += de_list("VTTS_DE_NATIVE_V_WORD", g.NATIVE_V_WORD)
    out += de_list("VTTS_DE_REDUCE_CODA", sorted(g.REDUCE_CODA))
    out += ["static const char *const VTTS_DE_OTHER_CONSONANTS[][2] = {"]
    out += [f"    {{{c_str(de_code(k))}, {c_str(' '.join(v))}}}," for k, v in g.OTHER_CONSONANTS.items()]
    out += ["};", f"#define VTTS_DE_N_OTHER_CONSONANTS {len(g.OTHER_CONSONANTS)}", ""]
    # stems (sorted by coded key) and overrides
    stems = sorted((de_code(k), de_code(v)) for k, v in g.stem_table().items())
    out += [f"static const char *const VTTS_DE_STEMS[{len(stems)}][2] = {{  /* key, annotated; sorted */"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in stems] + ["};", f"#define VTTS_DE_N_STEMS {len(stems)}", ""]
    ov = sorted((de_code(k), v) for k, v in g.override_table().items())
    out += [f"static const char *const VTTS_DE_OVERRIDES[{len(ov)}][2] = {{  /* word, phoneme ids; sorted */"]
    out += [f"    {{{c_str(k)}, {ids(v)}}}," for k, v in ov] + ["};", f"#define VTTS_DE_N_OVERRIDES {len(ov)}", ""]
    # fold(): code point >= 0x80 -> one coded letter (runs) or two (pairs)
    codes = "abcdefghijklmnopqrstuvwxyzäöüß"
    single, pairs = {}, {}
    for c in range(0x80, 0x110000):
        if 0xD800 <= c < 0xE000:
            continue
        f = g.fold(chr(c))
        if len(f) == 1:
            single[c] = codes.index(f)
        elif f:
            pairs[c] = de_code(f)
    runs: list[list[int]] = []
    for c, o in sorted(single.items()):
        if runs:
            s, n, o0, st = runs[-1]
            if c == s + n and (o == o0 + n * st if n > 1 else True):
                if n == 1:
                    runs[-1] = [s, 2, o0, o - o0]
                else:
                    runs[-1][1] += 1
                continue
        runs.append([c, 1, o, 0])
    out += [f"#define VTTS_DE_FOLD_LETTERS {c_str(de_code(codes))}  /* letter index -> code */",
            "typedef struct { uint32_t start; uint16_t count; int8_t first, step; } vtts_de_fold;",
            f"static const vtts_de_fold VTTS_DE_FOLD[{len(runs)}] = {{  /* index = first + (c - start) * step */"]
    out += ["    " + " ".join(f"{{0x{s:X}, {n}, {o}, {st}}}," for s, n, o, st in runs[i:i + 4]) for i in range(0, len(runs), 4)]
    out += ["};", f"#define VTTS_DE_N_FOLD {len(runs)}", "",
            "static const struct { uint32_t cp; const char *letters; } VTTS_DE_FOLD2[] = {"]
    out += [f"    {{0x{c:X}, {c_str(v)}}}," for c, v in sorted(pairs.items())] + ["};", f"#define VTTS_DE_N_FOLD2 {len(pairs)}", ""]
    # tagger
    out += _str_list("VTTS_DE_NATIVE", sorted(load_words("de", "native"))) + [
        f"#define VTTS_DE_N_NATIVE {len(load_words('de', 'native'))}", ""]
    out += _str_list("VTTS_DE_ENGLISH", sorted(load_words("de", "english"))) + [
        f"#define VTTS_DE_N_ENGLISH {len(load_words('de', 'english'))}", ""]
    keys = sorted({k.lower().rstrip(".") for k in list(nd.UNITS) + list(nd.ABBREVIATIONS)})
    out += _str_list("VTTS_DE_TABLE_KEYS", keys) + [f"#define VTTS_DE_N_TABLE_KEYS {len(keys)}", ""]
    own = "äöüßÄÖÜẞ"
    assert own == __import__("vtts.frontend.latin", fromlist=["x"]).LATIN_PAIRS["de"]
    out += [f"static const uint32_t VTTS_DE_OWN[] = {{{', '.join(f'0x{ord(c):X}' for c in own)}}};",
            f"#define VTTS_DE_N_OWN {len(own)}", ""]
    # normalizer (UTF-8)
    out += c_list("VTTS_DE_DIGITS", list(nd.DIGITS)) + c_list("VTTS_DE_ONES", list(nd.ONES))
    out += c_list("VTTS_DE_TENS", list(nd.TENS)) + c_list("VTTS_DE_MONTHS", list(nd.MONTHS))
    out += _str_list("VTTS_DE_MONTH_NAMES", sorted(nd.MONTH_NAMES)) + [f"#define VTTS_DE_N_MONTH_NAMES {len(nd.MONTH_NAMES)}", ""]
    out += ["static const char *const VTTS_DE_ORD_IRREGULAR[20] = {"]
    out += ["    " + ", ".join(c_str(nd.ORD_IRREGULAR.get(k, "")) for k in range(20)) + ",", "};", ""]
    out += ["static const struct { uint32_t cp; const char *name; } VTTS_DE_LETTERS[] = {"]
    out += [f"    {{0x{ord(k):X}, {c_str(v)}}}," for k, v in nd.LETTERS.items()] + ["};", f"#define VTTS_DE_N_LETTERS {len(nd.LETTERS)}", ""]
    out += _str_list("VTTS_DE_ACRONYM_WORDS", sorted(nd.ACRONYM_WORDS)) + [f"#define VTTS_DE_N_ACRONYM_WORDS {len(nd.ACRONYM_WORDS)}", ""]
    abbrev = sorted(nd.ABBREVIATIONS, key=len, reverse=True)
    out += ["static const char *const VTTS_DE_ABBREV[][2] = {  /* in the order they are applied */"]
    out += [f"    {{{c_str(k)}, {c_str(nd.ABBREVIATIONS[k])}}}," for k in abbrev] + ["};", f"#define VTTS_DE_N_ABBREV {len(abbrev)}", ""]
    dots = [k[:-1] for k in nd.ABBREVIATIONS if k.endswith(".")]
    out += _str_list("VTTS_DE_ABBREV_DOT", dots) + [f"#define VTTS_DE_N_ABBREV_DOT {len(dots)}", ""]
    units = sorted(nd.UNITS, key=len, reverse=True)
    out += ["static const struct { const char *key, *one, *many; uint8_t fem; } VTTS_DE_UNITS[] = {  /* alternation order */"]
    out += [f"    {{{c_str(k)}, {c_str(nd.UNITS[k][0])}, {c_str(nd.UNITS[k][1])}, {int(k in nd.FEMININE_UNITS)}}}," for k in units]
    out += ["};", f"#define VTTS_DE_N_UNITS {len(units)}", ""]
    cur = sorted(nd.CURRENCY, key=len, reverse=True)
    out += ["static const struct { const char *key, *one, *many, *cent; } VTTS_DE_CURRENCY[] = {  /* alternation order */"]
    out += [f"    {{{c_str(k)}, {c_str(nd.CURRENCY[k][0])}, {c_str(nd.CURRENCY[k][1])}, {c_str(nd.CENTS.get(k, 'Cent'))}}}," for k in cur]
    out += ["};", f"#define VTTS_DE_N_CURRENCY {len(cur)}", ""]
    assert all(len(k) == 1 for k in nd.SYMBOLS)
    out += ["static const struct { uint32_t cp; const char *text; } VTTS_DE_SYMBOLS[] = {  /* in this order */"]
    out += [f"    {{0x{ord(k):X}, {c_str(v)}}}," for k, v in nd.SYMBOLS.items()] + ["};", f"#define VTTS_DE_N_SYMBOLS {len(nd.SYMBOLS)}", ""]
    out += _str_list("VTTS_DE_ORD_EN", sorted(nd.ORD_EN)) + [f"#define VTTS_DE_N_ORD_EN {len(nd.ORD_EN)}", ""]
    out += _str_list("VTTS_DE_ORD_E", sorted(nd.ORD_E)) + [f"#define VTTS_DE_N_ORD_E {len(nd.ORD_E)}", ""]
    out += _str_list("VTTS_DE_FEMININE_END", list(nd.FEMININE_END)) + [f"#define VTTS_DE_N_FEMININE_END {len(nd.FEMININE_END)}", ""]
    out += [f"#define VTTS_DE_LOWER {c_str(nd.LOWER)}", f"#define VTTS_DE_UPPER {c_str(nd.UPPER)}",
            f"#define VTTS_DE_DROP {c_str(latin_norm.DROP.replace('(', '').replace(')', ''))}", ""]
    out += ["#endif", ""]
    return out


# ---------------- Arabic (token set ar-en) ----------------

AR_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_ar_tables.h"
AR0 = 0x0600  # lexicon letters and marks are coded as code point - 0x0600 (one byte) in the C tables


def ar_bytes(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        c = ord(ch) - AR0
        assert 0 < c < 0x100, (s, ch)
        out.append(c)
    return bytes(out)


def c_bytes(b: bytes) -> str:
    return '"' + "".join(f"\\x{x:02x}" for x in b) + '"'


def c_utf8(s: str) -> str:
    """A C string literal of s in UTF-8 with every non-ASCII byte escaped."""
    out = []
    for x in s.encode("utf-8"):
        out.append(chr(x) if 0x20 <= x < 0x7F and chr(x) not in '"\\?' else f"\\x{x:02x}")
    # an escape followed by a hex digit would extend the escape: close and reopen the literal
    return '"' + '""'.join(_split_hex("".join(out))) + '"'


def _split_hex(s: str) -> list[str]:
    parts, cur, i = [], "", 0
    while i < len(s):
        if s[i] == "\\" and s[i + 1] == "x":
            cur += s[i:i + 4]
            i += 4
            if i < len(s) and s[i] in "0123456789abcdefABCDEF":
                parts.append(cur)
                cur = ""
            continue
        cur += s[i]
        i += 1
    parts.append(cur)
    return parts


def arabic_tables() -> list[str]:
    """Tables of the Arabic front-end (ar/g2p_ar.py, ar/normalize_ar.py, lexicons/ar/): the letter
    and mark classes of U+0600..U+06FF, NFC data, the word table and spelling exceptions (letters
    coded as code point - 0x0600), the clitics, endings and word patterns, and the strings of the
    normalizer (UTF-8)."""
    import re

    from vtts.frontend.ar import g2p_ar as g
    from vtts.frontend.ar import normalize_ar as na

    t = phoneme_set.token_index(phoneme_set.TOKEN_SET_AREN).__getitem__
    ph = list(g.PHONEMES)
    base = t("AR:" + ph[0])
    assert [t("AR:" + p) for p in ph] == list(range(base, base + len(ph)))
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Arabic front-end tables (mirror src/vtts/frontend/ar/ and lexicons/ar/). */",
           "#ifndef VTTS_TEXT_AR_TABLES_H", "#define VTTS_TEXT_AR_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_AREN_AR0 {base}  /* id of AR:{ph[0]} */",
           f"#define VTTS_AR_N_PHONEMES {len(ph)}"]
    out += _str_list("VTTS_AR_PHONEMES", ph)
    assert ph[len(g.CONSONANTS):len(g.CONSONANTS) + 6] == ["a", "i", "u", "aa", "ii", "uu"]
    assert ph[len(g.CONSONANTS) + 6:] == ["a1", "i1", "u1", "aa1", "ii1", "uu1"]
    out += [f"#define VTTS_AR_V0 {len(g.CONSONANTS)}  /* a i u aa ii uu from here, then the stressed ones */",
            f"#define VTTS_AR_PH_GLOTTAL {ph.index('?')}", f"#define VTTS_AR_PH_L {ph.index('l')}",
            f"#define VTTS_AR_PH_T {ph.index('t')}", ""]
    # per code point U+0600..U+06FF: flags, consonant phoneme (255 none), fold target (low byte), ccc
    F_LO, F_LETTER, F_MARK, F_VOWEL_MARK, F_STRIP, F_SUN, F_WORDCLS = 1, 2, 4, 8, 16, 32, 64
    word_cls = re.compile(f"[{na.AR}]")
    rows = []
    for c in range(0x600, 0x700):
        ch = chr(c)
        f = 0
        f |= F_LO * (unicodedata.category(ch) == "Lo")
        f |= F_LETTER * (ch in g.LETTERS)
        f |= F_MARK * (ch in g.MARKS)
        f |= F_VOWEL_MARK * (ch in g.VOWEL_MARKS)
        stripped = (ch in g.MARKS or ch == g.TATWEEL or 0x6D6 <= c <= 0x6ED or 0x610 <= c <= 0x61A
                    or ch in "ٕٓٔ")
        f |= F_STRIP * stripped
        f |= F_SUN * (ch in g.SUN)
        f |= F_WORDCLS * bool(word_cls.match(ch))
        cons = g.CONSONANT_LETTERS.get(ch)
        fold = g.FOLD.get(ch, ch)
        assert 0x600 <= ord(fold) < 0x700
        rows.append((f, ph.index(cons) if cons else 255, ord(fold) - AR0, unicodedata.combining(ch)))
    for c in list(g.FOLD) + list(g.CONSONANT_LETTERS):
        assert 0x600 <= ord(c) < 0x700, c
    out += [f"#define VTTS_AR_F_LO {F_LO}", f"#define VTTS_AR_F_LETTER {F_LETTER}", f"#define VTTS_AR_F_MARK {F_MARK}",
            f"#define VTTS_AR_F_VOWEL_MARK {F_VOWEL_MARK}", f"#define VTTS_AR_F_STRIP {F_STRIP}",
            f"#define VTTS_AR_F_SUN {F_SUN}", f"#define VTTS_AR_F_WORDCLS {F_WORDCLS}",
            "/* U+0600 + i: flags, consonant phoneme index (255 none), FOLD target - 0x600, canonical combining class */",
            "static const uint8_t VTTS_AR_CHARS[256][4] = {"]
    out += ["    " + " ".join(f"{{{a}, {b}, {c}, {d}}}," for a, b, c, d in rows[i:i + 8]) for i in range(0, 256, 8)]
    out += ["};", ""]
    # Lo bits outside U+0600..U+06FF (is_arabic ranges) for is_arabic_letter, and the word class
    ext = [(0x750, 0x77F), (0x8A0, 0x8FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]
    for name, pred in (("LO", lambda ch: unicodedata.category(ch) == "Lo"), ("WCLS", lambda ch: bool(word_cls.match(ch)))):
        bits = []
        for a, b in ext:
            for c in range(a, b + 1, 8):
                bits.append(sum(1 << k for k in range(8) if c + k <= b and pred(chr(c + k))))
        out += [f"static const uint8_t VTTS_AR_EXT_{name}[{len(bits)}] = {{  /* bits of {', '.join(f'{a:04X}-{b:04X}' for a, b in ext)} */"]
        out += ["    " + ", ".join(str(x) for x in bits[i:i + 24]) + "," for i in range(0, len(bits), 24)]
        out += ["};"]
    out += ["static const uint32_t VTTS_AR_EXT[4][2] = {" + ", ".join(f"{{0x{a:X}, 0x{b:X}}}" for a, b in ext) + "};", ""]
    # NFC: canonical decompositions of the block (letter -> base + mark)
    comp = []
    for c in range(0x600, 0x700):
        d = unicodedata.decomposition(chr(c))
        if d and not d.startswith("<"):
            a, b = (int(x, 16) for x in d.split())
            assert unicodedata.normalize("NFC", chr(a) + chr(b)) == chr(c)
            comp.append((c, a, b))
    cccx = [(c, unicodedata.combining(chr(c))) for r in ((0x300, 0x36F), (0x8A0, 0x8FF), (0xFE20, 0xFE2F))
            for c in range(r[0], r[1] + 1) if unicodedata.combining(chr(c))]
    out += [f"static const uint16_t VTTS_AR_CCC_EXT[{len(cccx)}][2] = {{  /* combining classes outside U+06xx (canonical order) */"]
    out += ["    " + " ".join(f"{{0x{c:04X}, {k}}}," for c, k in cccx[i:i + 8]) for i in range(0, len(cccx), 8)]
    out += ["};", f"#define VTTS_AR_N_CCC_EXT {len(cccx)}", ""]
    out += [f"static const uint16_t VTTS_AR_COMPOSE[{len(comp)}][3] = {{  /* composed, base, mark */"]
    out += ["    " + " ".join(f"{{0x{c:04X}, 0x{a:04X}, 0x{b:04X}}}," for c, a, b in comp)]
    out += ["};", f"#define VTTS_AR_N_COMPOSE {len(comp)}", ""]

    # word table and spelling table: entries sorted by key bytes; blob = keylen key vallen val
    def table(name: str, items: list[tuple[str, str]]) -> list[str]:
        ent = sorted((ar_bytes(k), ar_bytes(v)) for k, v in items)
        blob, offs = bytearray(), []
        for k, v in ent:
            assert len(k) < 256 and len(v) < 256
            offs.append(len(blob))
            blob += bytes([len(k)]) + k + bytes([len(v)]) + v
        assert len(blob) < 65536
        lines = [f"static const uint8_t VTTS_AR_{name}_BLOB[{len(blob)}] = {{  /* [klen][key][vlen][value] */"]
        lines += ["    " + ",".join(str(x) for x in blob[i:i + 40]) + "," for i in range(0, len(blob), 40)]
        lines += ["};", f"static const uint16_t VTTS_AR_{name}_OFF[{len(offs)}] = {{"]
        lines += ["    " + ",".join(str(x) for x in offs[i:i + 20]) + "," for i in range(0, len(offs), 20)]
        lines += ["};", f"#define VTTS_AR_N_{name} {len(offs)}", ""]
        return lines, ent

    # the word table, compact: [key length][key letters][one marks byte per letter]; the marks byte
    # holds the codes (1..9 = U+064B..U+0652, U+0670; 0 none) of the first (low nibble) and second
    # (high nibble) mark after the letter, in the order of the value. Entries sorted by key; an
    # offset for every LEX_BLOCK-th entry.
    mark_codes = {chr(0x64B + i): i + 1 for i in range(8)} | {"\u0670": 9}
    lex_items = list(g.lexicon().items())
    ent = sorted((ar_bytes(k), k, v) for k, v in lex_items)
    blob, block = bytearray(), []
    for i, (kb, k, v) in enumerate(ent):
        letters, marks = [], []
        for ch in v:
            if ch in mark_codes:
                assert marks and len(marks[-1]) < 2, (k, v)
                marks[-1].append(mark_codes[ch])
            else:
                letters.append(ch)
                marks.append([])
        assert "".join(letters) == k and len(kb) < 256, (k, v)
        if i % 16 == 0:
            block.append(len(blob))
        blob += bytes([len(kb)]) + kb + bytes((m + [0, 0])[0] | (m + [0, 0])[1] << 4 for m in marks)
    out += ["/* lexicons/ar/words.tsv: [key length][key][a marks byte per letter], sorted by key */",
            "#define VTTS_AR_LEX_BLOCK 16",
            f"static const uint8_t VTTS_AR_LEX_BLOB[{len(blob)}] = {{"]
    out += ["    " + ",".join(str(x) for x in blob[i:i + 40]) + "," for i in range(0, len(blob), 40)]
    out += ["};", f"static const uint32_t VTTS_AR_LEX_BLOCKS[{len(block)}] = {{  /* offset of every 16th entry */"]
    out += ["    " + ",".join(str(x) for x in block[i:i + 16]) + "," for i in range(0, len(block), 16)]
    out += ["};", f"#define VTTS_AR_N_LEX {len(ent)}", ""]
    index = {kb: i for i, (kb, _k, _v) in enumerate(ent)}
    unseated: dict[bytes, int] = {}
    for k, _v in lex_items:  # _unseated(): first entry wins, file order
        if k[0] in "أإآ":
            unseated.setdefault(ar_bytes("ا" + k[1:]), index[ar_bytes(k)])
    us = sorted(unseated.items())
    out += [f"static const uint16_t VTTS_AR_UNSEATED[{len(us)}] = {{  /* entries whose key starts with أ إ آ, sorted by the key with ا */"]
    out += ["    " + ",".join(str(i) for _, i in us[j:j + 20]) + "," for j in range(0, len(us), 20)]
    out += ["};", f"#define VTTS_AR_N_UNSEATED {len(us)}", ""]
    lines, _ = table("SPELL", list(g.spelling_table().items()))
    out += ["/* lexicons/ar/spelling.tsv */"] + lines

    def pairs(name: str, items, comment: str) -> list[str]:
        lines = [f"static const char *const VTTS_AR_{name}[][2] = {{  /* {comment} */"]
        lines += [f"    {{{c_utf8(a)}, {c_utf8(b)}}}," for a, b in items]
        return lines + ["};", f"#define VTTS_AR_N_{name} {len(items)}", ""]

    out += pairs("PROCLITICS", list(g.PROCLITICS.items()), "letter, vowelled")
    out += pairs("PRONOUNS", list(g.PRONOUNS), "suffix, vowelled (longest first)")
    out += pairs("HI", list(g._HI.items()), "pronoun after i / ii / y")
    out += ["static const char *const VTTS_AR_ENDINGS[][3] = {  /* ending, stem ending, vowelled */"]
    out += [f"    {{{c_utf8(a)}, {c_utf8(b)}, {c_utf8(c)}}}," for a, b, c in g.ENDINGS]
    out += ["};", f"#define VTTS_AR_N_ENDINGS {len(g.ENDINGS)}", ""]
    out += pairs("FALLBACK_ENDINGS", list(g.FALLBACK_ENDINGS), "ending, vowelled")
    # word patterns: element codes 1 = C, 2 = CW, 3 = [اإ], else a letter; template digits 1..5 slots
    pats = []
    for p, tpl in g.PATTERNS:
        elems, i = [], 0
        while i < len(p):
            if p.startswith(g.C, i):
                elems.append(1)
                i += len(g.C)
            elif p.startswith(g.CW, i):
                elems.append(2)
                i += len(g.CW)
            elif p.startswith("[اإ]", i):
                elems.append(3)
                i += 4
            else:
                elems.append(ord(p[i]))
                i += 1
        pats.append((elems, tpl))
    assert all(len(e) <= 8 for e, _ in pats)
    out += ["typedef struct { uint16_t el[8]; uint8_t n; const char *tpl; } vtts_ar_pattern;",
            ("/* PATTERNS: elements (1 consonant [^اويىةآ], 2 consonant or و ي [^اىةآ], 3 [اإ], else the letter); template "
            "with slots '1'..'5' */"),
            f"static const vtts_ar_pattern VTTS_AR_PATTERNS[{len(pats)}] = {{"]
    out += [f"    {{{{{', '.join(f'0x{x:X}' for x in e)}}}, {len(e)}, {c_utf8(tpl)}}}," for e, tpl in pats]
    out += ["};", f"#define VTTS_AR_N_PATTERNS {len(pats)}", ""]
    out += [f"#define VTTS_AR_LINK 0x{ord(g.LINK):04X}"]
    out += [f"#define VTTS_AR_STR_{k} {c_utf8(v)}" for k, v in (
        ("LIL", "لِل"), ("AL", "ال"))]
    out += [""]

    # ---- normalizer ----
    out += ["/* ---- normalize_ar ---- */"]
    def ulist(name: str, items) -> list[str]:
        items = list(items)
        lines = [f"static const char *const VTTS_AR_{name}[{len(items)}] = {{"]
        lines += ["    " + ", ".join(c_utf8(s) for s in items[i:i + 4]) + "," for i in range(0, len(items), 4)]
        return lines + ["};", ""]

    out += ulist("ONES", na.ONES)
    out += ulist("TENS", na.TENS) + ulist("TENS_GEN", na.TENS_GEN) + ulist("HUNDREDS", na.HUNDREDS)
    assert na.ONES_GEN == {2: "اِثْنَيْن"} and set(na.TEENS) == {11, 12} and set(na.TEENS_GEN) == {12}
    assert set(na.HUNDREDS_GEN) == {2}
    lit = {"ONE_GEN2": na.ONES_GEN[2], "TEEN11": na.TEENS[11], "TEEN12": na.TEENS[12], "TEEN12_GEN": na.TEENS_GEN[12],
           "HUNDRED_GEN2": na.HUNDREDS_GEN[2], "AND": na.AND, "TEEN_TAIL": "َ عَشَرَ"}
    out += [f"#define VTTS_AR_{k} {c_utf8(v)}" for k, v in lit.items()]
    out += ["static const char *const VTTS_AR_SCALES[3][7] = {  /* value is 10^9, 10^6, 10^3: one, two, two (gen), 3-10, 11-99, 100+ */"]
    for v, one, two, few, many, hundred in na.SCALES:
        out += [f"    {{{c_utf8(one)}, {c_utf8(two[0])}, {c_utf8(two[1])}, {c_utf8(few)}, {c_utf8(many)}, {c_utf8(hundred)}, 0}},"]
    assert [s[0] for s in na.SCALES] == [10 ** 9, 10 ** 6, 1000]
    out += ["};", ""]
    out += ulist("MONTHS", na.MONTHS)
    out += ["static const char *const VTTS_AR_LETTERS[26] = {"]
    out += ["    " + ", ".join(c_utf8(na.LETTERS[chr(97 + i)]) for i in range(j, min(j + 4, 26))) + "," for j in range(0, 26, 4)]
    out += ["};", ""]
    abbr = sorted(na.ABBREVIATIONS.items(), key=lambda kv: len(kv[0]), reverse=True)
    out += pairs("ABBREV", abbr, "key, reading (longest first, one re.sub per key)")
    units = sorted(na.UNITS.items(), key=lambda kv: len(kv[0]), reverse=True)
    out += pairs("UNITS", units, "unit, reading (the regex alternation order)")
    kinds = list(na.CURRENCIES)
    cur = sorted(na.CURRENCY.items(), key=lambda kv: len(kv[0]), reverse=True)
    out += ["typedef struct { const char *key; uint8_t kind; const char *adj; } vtts_ar_currency;",
            f"static const vtts_ar_currency VTTS_AR_CURRENCY[{len(cur)}] = {{  /* alternation order */"]
    out += [f"    {{{c_utf8(k)}, {kinds.index(kind)}, {c_utf8(adj)}}}," for k, (kind, adj) in cur]
    out += ["};", f"#define VTTS_AR_N_CURRENCY {len(cur)}"]
    out += [f"static const char *const VTTS_AR_CUR_FORMS[{len(kinds)}][5] = {{  /* 1, 2, 3-10, 11-99, 100+ */"]
    out += ["    {" + ", ".join(c_utf8(x) for x in na.CURRENCIES[k]) + "}," for k in kinds]
    out += ["};", ""]
    out += [f"static const char *const VTTS_AR_LATIN_WORDS[{len(na.LATIN_WORDS)}] = {{"]
    out += ["    " + ", ".join(c_utf8(w) for w in sorted(na.LATIN_WORDS)) + ","]
    out += ["};", f"#define VTTS_AR_N_LATIN_WORDS {len(na.LATIN_WORDS)}", ""]
    out += pairs("SYMBOLS", list(na.SYMBOLS.items()), "symbol, replacement (in order)")
    drop = [f"0x{ord(c):04X}" for c in na.DROP]
    out += [f"static const uint32_t VTTS_AR_DROP[{len(drop)}] = {{" + ", ".join(drop) + "};",
            f"#define VTTS_AR_N_DROP {len(drop)}", ""]
    # translate tables: DIGITS then PUNCT
    dig = {ord(a): b for a, b in zip("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789", strict=True)}
    assert na.DIGITS == {k: ord(v) for k, v in dig.items()}
    assert na.PUNCT == {0x60C: ",", 0x61B: ";", 0x61F: "?", 0x6D4: ".", 0x66B: ".", 0x66C: ",", 0x66A: "%",
                        0x640: None}
    lits = {"SALIB": "سَالِب ", "FASILA": " فَاصِلَة ", "DAQIQA": " دَقِيقَة", "THANIYA": " ثَانِيَة",
            "RUB3": " وَرُبْع", "NISF": " وَنِصْف", "SABAHAN": " صَبَاحًا", "MASAAN": " مَسَاءً",
            "PERCENT": " بِالْمِئَة ", "MILADI": "مِيلَادِيّ", "HIJRI": "هِجْرِيّ", "ZAID": "زَائِد ",
            "MIN": " مِنْ ", "ILA": " إِلَى "}
    out += [f"#define VTTS_AR_{k} {c_utf8(v)}" for k, v in lits.items()]
    # the time and era suffixes and the year-after words of the regexes
    assert na.TIME.pattern.endswith("(?:\\s*(ص|م|صباحا|مساء)(?![" + na.AR + "]))?")
    out += ulist("TIME_PARTS", ["ص", "م", "صباحا", "مساء"])
    assert "(هـ|ه|م)" in na.ERA.pattern
    out += ulist("ERAS", ["هـ", "ه", "م"])
    out += ulist("YEAR_WORDS", ["عام", "سنة"])
    out += ["#endif", ""]
    # check the literals against the module source (so a change in normalize_ar.py is noticed)
    src = Path(na.__file__).read_text(encoding="utf-8")
    for v in lits.values():
        assert v.strip() in src, v
    return out


FI_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_fi_tables.h"


def _fold_runs(fold) -> tuple[list[list[int]], list[tuple[int, int, int]]]:
    """fold(chr(c)) for c >= 0x80 as runs (start, count, first, step 0/1) of one-letter results,
    plus the two-letter results (c, first, second)."""
    runs: list[list[int]] = []
    pairs = []
    for c in range(0x80, 0x110000):
        if 0xD800 <= c < 0xE000:
            continue
        f = fold(chr(c))
        if not f:
            continue
        if len(f) == 2:
            pairs.append((c, ord(f[0]), ord(f[1])))
            continue
        assert len(f) == 1
        o = ord(f)
        if runs and c == runs[-1][0] + runs[-1][1] and runs[-1][1] < 65535:
            r = runs[-1]
            if r[1] == 1 and o in (r[2], r[2] + 1):
                r[1], r[3] = 2, o - r[2]
                continue
            if r[1] > 1 and o == r[2] + r[1] * r[3]:
                r[1] += 1
                continue
        runs.append([c, 1, o, 0])
    return runs, pairs


def finnish_tables() -> list[str]:
    """Tables of the Finnish front-end (fi/g2p_fi.py, fi/normalize_fi.py, lexicons/fi/, the fi
    rules of latin.py) for runtime/src/vtts_text_fi.c, in the order the Python code uses them."""
    from vtts.frontend import latin, latin_norm
    from vtts.frontend.fi import g2p_fi as g
    from vtts.frontend.fi import normalize_fi as nm
    from vtts.frontend.lexicons import load_words

    tset = phoneme_set.TOKEN_SETS["fi-en"]
    tok0 = phoneme_set.VOCAB_SIZE_V2
    names = [t.split(":", 1)[1] for t in tset[tok0:]]
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Finnish front-end (token set fi-en; ids 0..106 are the v2 ids) */",
           "#ifndef VTTS_TEXT_FI_TABLES_H", "#define VTTS_TEXT_FI_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_FI_TOK0 {tok0}", f"#define VTTS_FI_VOCAB {len(tset)}"]
    out += c_list("VTTS_FI_TOKENS", names) + [f"#define VTTS_FI_N_TOKENS {len(names)}", ""]
    out += ["typedef struct { const char *key, *one, *many; } vtts_fi_reading;",
            "typedef struct { uint32_t cp; const char *name; } vtts_fi_letter;",
            "typedef struct { uint32_t start; uint16_t count; uint8_t step; uint32_t first; } vtts_fi_fold;", ""]
    abbrev = sorted(nm.ABBREVIATIONS, key=len, reverse=True)  # apply_abbreviations order
    out += ["static const char *const VTTS_FI_ABBREV[][2] = {  /* applied in this order */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.ABBREVIATIONS[k])}}}," for k in abbrev]
    out += ["};", f"#define VTTS_FI_N_ABBREV {len(abbrev)}", f"#define VTTS_FI_DROP {c_str(latin_norm.DROP)}", ""]
    out += ["static const vtts_fi_letter VTTS_FI_LETTERS[] = {  /* letter names (spelling) */"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.LETTERS.items()]
    out += ["};", f"#define VTTS_FI_N_LETTERS {len(nm.LETTERS)}", ""]
    out += _str_list("VTTS_FI_ACRONYM_WORDS", sorted(nm.ACRONYM_WORDS))
    out += [f"#define VTTS_FI_N_ACRONYM_WORDS {len(nm.ACRONYM_WORDS)}", ""]
    for name, table in (("UNITS", nm.UNITS), ("CURRENCY", nm.CURRENCY)):
        keys = sorted(table, key=len, reverse=True)  # the alternation order of the regexes
        out += [f"static const vtts_fi_reading VTTS_FI_{name}[] = {{"]
        out += [f"    {{{c_str(k)}, {c_str(table[k][0])}, {c_str(table[k][1])}}}," for k in keys]
        out += ["};", f"#define VTTS_FI_N_{name} {len(keys)}", ""]
    assert all(len(k) == 1 for k in nm.SYMBOLS)
    out += ["static const vtts_fi_letter VTTS_FI_SYMBOLS[] = {  /* replaced in this order */"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.SYMBOLS.items()]
    out += ["};", f"#define VTTS_FI_N_SYMBOLS {len(nm.SYMBOLS)}", ""]
    out += [f"#define VTTS_FI_COMMA {c_str(nm.MARK_WORDS[','])}", f"#define VTTS_FI_PERIOD {c_str(nm.MARK_WORDS['.'])}"]
    out += c_list("VTTS_FI_ONES", list(nm.ONES)) + c_list("VTTS_FI_MONTHS", list(nm.MONTHS))
    out += c_list("VTTS_FI_ORD_ONES", list(nm.ORD_ONES)) + c_list("VTTS_FI_ORD_PARTS", list(nm.ORD_PARTS))
    assert [s for s, _, _ in nm.SCALES] == [10 ** 9, 10 ** 6]
    out += ["static const char *const VTTS_FI_SCALES[2][2] = {  /* 10^9, 10^6: one, many */"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for _, a, b in nm.SCALES] + ["};", ""]
    assert set(nm.ELATIVE) == set(nm.ILLATIVE)
    out += ["static const char *const VTTS_FI_CASES[][3] = {  /* part, elative, illative */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.ELATIVE[k])}, {c_str(nm.ILLATIVE[k])}}}," for k in nm.ELATIVE]
    out += ["};", f"#define VTTS_FI_N_CASES {len(nm.ELATIVE)}", ""]
    native = sorted(load_words("fi", "native"))
    out += _str_list("VTTS_FI_NATIVE", native) + [f"#define VTTS_FI_N_NATIVE {len(native)}", ""]
    keys = sorted(latin._table_keys("fi"))
    out += _str_list("VTTS_FI_TABLE_KEYS", keys) + [f"#define VTTS_FI_N_TABLE_KEYS {len(keys)}", ""]
    out += [f"#define VTTS_FI_OWN {c_str(latin.LATIN_PAIRS['fi'])}", ""]
    english = sorted(load_words("latin", "english"))
    out += _str_list("VTTS_FI_ENGLISH", english) + [f"#define VTTS_FI_N_ENGLISH {len(english)}", ""]
    both = sorted(load_words("fi", "native") & load_words("latin", "english"))
    out += _str_list("VTTS_FI_BOTH", both) + [f"#define VTTS_FI_N_BOTH {len(both)}", ""]
    ovr = g.override_table()
    out += ["static const char *const VTTS_FI_OVERRIDES[][2] = {"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ovr.items()]
    out += ["};", f"#define VTTS_FI_N_OVERRIDES {len(ovr)}", ""]
    out += _str_list("VTTS_FI_UNSTRESSED", sorted(g.UNSTRESSED)) + [f"#define VTTS_FI_N_UNSTRESSED {len(g.UNSTRESSED)}", ""]
    parts = sorted(g._all_number_parts(), key=lambda p: (-len(p), p))
    out += _str_list("VTTS_FI_NUMBER_PARTS", parts) + [f"#define VTTS_FI_N_NUMBER_PARTS {len(parts)}", ""]
    for c in range(0x80):  # ASCII: lower-case a-z, nothing else
        assert g.fold(chr(c)) == (chr(c).lower() if chr(c).isalpha() else ""), c
    runs, pairs = _fold_runs(g.fold)
    out += [f"static const vtts_fi_fold VTTS_FI_FOLD[{len(runs)}] = {{  /* fold() of code points >= 0x80 */"]
    out += ["    " + " ".join(f"{{0x{a:X}, {n}, {s}, 0x{f:X}}}," for a, n, f, s in runs[i:i + 4])
            for i in range(0, len(runs), 4)] + ["};", f"#define VTTS_FI_N_FOLD {len(runs)}", ""]
    out += ["static const uint32_t VTTS_FI_FOLD2[][3] = {  /* code point -> two letters */"]
    out += [f"    {{0x{a:X}, 0x{b:X}, 0x{c:X}}}," for a, b, c in pairs] + ["};", f"#define VTTS_FI_N_FOLD2 {len(pairs)}", ""]
    for attr in ("ONSETS", "CODAS", "FINALS"):
        items = sorted(getattr(g, attr))
        out += _str_list(f"VTTS_FI_{attr}", items) + [f"#define VTTS_FI_N_{attr} {len(items)}", ""]
    out += _str_list("VTTS_FI_FOREIGN", list(g.FOREIGN)) + [f"#define VTTS_FI_N_FOREIGN {len(g.FOREIGN)}", ""]
    out += _str_list("VTTS_FI_DISHARMONY", list(g.DISHARMONY)) + [f"#define VTTS_FI_N_DISHARMONY {len(g.DISHARMONY)}", ""]
    out += ["#endif", ""]
    return out


EL_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_el_tables.h"


def greek_tables() -> list[str]:
    """Tables of the Greek front-end (el/g2p_el.py, el/normalize_el.py, lexicons/el/) for
    runtime/src/vtts_text_el.c, in the order the Python code uses them."""
    from vtts.frontend import latin_norm
    from vtts.frontend.el import g2p_el as g
    from vtts.frontend.el import normalize_el as nm

    tset = phoneme_set.TOKEN_SETS["el-en"]
    tok0 = phoneme_set.VOCAB_SIZE_V2
    names = [t.split(":", 1)[1] for t in tset[tok0:]]
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Greek front-end (token set el-en; ids 0..106 are the v2 ids) */",
           "#ifndef VTTS_TEXT_EL_TABLES_H", "#define VTTS_TEXT_EL_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_EL_TOK0 {tok0}", f"#define VTTS_EL_VOCAB {len(tset)}"]
    out += c_list("VTTS_EL_TOKENS", names) + [f"#define VTTS_EL_N_TOKENS {len(names)}", ""]
    out += ["typedef struct { const char *key, *one, *many; char gender; } vtts_el_reading;",
            "typedef struct { uint32_t cp; const char *name; } vtts_el_letter;",
            "/* a code point whose NFD starts with a Greek letter of the g2p: base, stress mark, dialytika */",
            "typedef struct { uint32_t cp; uint16_t base; uint8_t acc, dia; } vtts_el_decomp;", ""]
    letters = set(g.VOWEL_LETTERS) | set(g.CONSONANTS)
    dec = []
    for c in range(0x110000):
        if 0xD800 <= c < 0xE000:
            continue
        b, acc, dia = g.decompose(chr(c))
        if b in letters:
            dec.append((c, ord(b), int(acc), int(dia)))
    out += [f"static const vtts_el_decomp VTTS_EL_DECOMP[{len(dec)}] = {{  /* sorted by code point */"]
    out += ["    " + " ".join(f"{{0x{c:X}, 0x{b:X}, {a}, {d}}}," for c, b, a, d in dec[i:i + 4])
            for i in range(0, len(dec), 4)] + ["};", f"#define VTTS_EL_N_DECOMP {len(dec)}", ""]
    greek_alpha = _ranges(lambda ch: g.is_greek(ch) and ch.isalpha())
    out += [f"static const uint32_t VTTS_EL_ALPHA[{len(greek_alpha)}][2] = {{  /* is_greek(ch) and ch.isalpha() */"]
    out += ["    " + " ".join(f"{{0x{a:X}, 0x{b:X}}}," for a, b in greek_alpha[i:i + 6])
            for i in range(0, len(greek_alpha), 6)] + ["};", f"#define VTTS_EL_N_ALPHA {len(greek_alpha)}", ""]
    out += _str_list("VTTS_EL_UNSTRESSED", sorted(g.UNSTRESSED)) + [f"#define VTTS_EL_N_UNSTRESSED {len(g.UNSTRESSED)}", ""]
    ovr = g.override_table()
    out += ["static const char *const VTTS_EL_OVERRIDES[][2] = {  /* word, phonemes */"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in ovr.items()]
    out += ["};", f"#define VTTS_EL_N_OVERRIDES {len(ovr)}", ""]
    # normalizer
    units = sorted(nm.UNITS, key=len, reverse=True)  # the alternation order of the regexes
    out += ["static const vtts_el_reading VTTS_EL_UNITS[] = {"]
    out += [f"    {{{c_str(k)}, {c_str(nm.UNITS[k][0])}, {c_str(nm.UNITS[k][1])}, '{nm.UNITS[k][2]}'}}," for k in units]
    out += ["};", f"#define VTTS_EL_N_UNITS {len(units)}", ""]
    cur = sorted(nm.CURRENCY, key=len, reverse=True)
    out += ["static const vtts_el_reading VTTS_EL_CURRENCY[] = {"]
    out += [f"    {{{c_str(k)}, {c_str(nm.CURRENCY[k][0])}, {c_str(nm.CURRENCY[k][1])}, '{nm.CURRENCY[k][2]}'}}," for k in cur]
    out += ["};", f"#define VTTS_EL_N_CURRENCY {len(cur)}", ""]
    out += _str_list("VTTS_EL_LATIN_WORDS", sorted(nm.LATIN_WORDS)) + [f"#define VTTS_EL_N_LATIN_WORDS {len(nm.LATIN_WORDS)}", ""]
    abbrev = sorted(nm.ABBREVIATIONS, key=len, reverse=True)
    out += ["static const char *const VTTS_EL_ABBREV[][2] = {  /* applied in this order */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.ABBREVIATIONS[k])}}}," for k in abbrev]
    out += ["};", f"#define VTTS_EL_N_ABBREV {len(abbrev)}", f"#define VTTS_EL_DROP {c_str(latin_norm.DROP)}", ""]
    for gname in ("n", "m", "f"):
        out += c_list(f"VTTS_EL_ONES_{gname.upper()}", list(nm.ONES[gname]))
        out += c_list(f"VTTS_EL_TEENS_{gname.upper()}", list(nm.TEENS[gname]))
    out += c_list("VTTS_EL_TENS", list(nm.TENS)) + c_list("VTTS_EL_HUNDRED_STEMS", list(nm.HUNDRED_STEMS))
    out += [f"#define VTTS_EL_END_N {c_str(nm.GENDER_END['n'])}", f"#define VTTS_EL_END_M {c_str(nm.GENDER_END['m'])}",
            f"#define VTTS_EL_END_F {c_str(nm.GENDER_END['f'])}",
            f"#define VTTS_EL_THOUSAND_N {c_str(nm.THOUSAND['n'])}", f"#define VTTS_EL_THOUSAND_M {c_str(nm.THOUSAND['m'])}",
            f"#define VTTS_EL_THOUSAND_F {c_str(nm.THOUSAND['f'])}"]
    assert [x for x, _, _ in nm.SCALES] == [10 ** 9, 10 ** 6]
    out += ["static const char *const VTTS_EL_SCALES[2][2] = {  /* 10^9, 10^6: one, many */"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for _, a, b in nm.SCALES] + ["};", ""]
    out += c_list("VTTS_EL_MONTHS", list(nm.MONTHS))
    out += _str_list("VTTS_EL_FEMININE", sorted(nm.FEMININE_WORDS)) + [f"#define VTTS_EL_N_FEMININE {len(nm.FEMININE_WORDS)}", ""]
    out += ["static const struct { const char *stem; uint8_t oxytone; } VTTS_EL_ORD_ONES[10] = {"]
    out += ["    {\"\", 0},"] + [f"    {{{c_str(st)}, {int(ox)}}}," for st, ox in nm.ORD_ONES[1:]] + ["};", ""]
    assert sorted(nm.ORD_TEENS) == [10, 11, 12]
    out += ["static const struct { const char *stem; uint8_t oxytone; } VTTS_EL_ORD_TEENS[3] = {  /* 10, 11, 12 */"]
    out += [f"    {{{c_str(nm.ORD_TEENS[k][0])}, {int(nm.ORD_TEENS[k][1])}}}," for k in (10, 11, 12)] + ["};", ""]
    out += c_list("VTTS_EL_ORD_TENS", list(nm.ORD_TENS)) + c_list("VTTS_EL_ORD_HUNDREDS", list(nm.ORD_HUNDREDS))
    endings = sorted({*nm.ORD_ENDINGS, *nm.ACCENTED.values()}, key=lambda e: (-len(e), e))
    plain = {v: k for k, v in nm.ACCENTED.items()}
    out += ["static const char *const VTTS_EL_ENDINGS[][3] = {  /* ending (alternation order), plain, accented */"]
    out += [f"    {{{c_str(e)}, {c_str(plain.get(e, e))}, {c_str(nm.ACCENTED[plain.get(e, e)])}}}," for e in endings]
    out += ["};", f"#define VTTS_EL_N_ENDINGS {len(endings)}", ""]
    out += ["static const vtts_el_letter VTTS_EL_GREEK_LETTERS[] = {"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.GREEK_LETTERS.items()]
    out += ["};", f"#define VTTS_EL_N_GREEK_LETTERS {len(nm.GREEK_LETTERS)}", ""]
    out += ["static const vtts_el_letter VTTS_EL_LATIN_LETTERS[] = {"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.LATIN_LETTERS.items()]
    out += ["};", f"#define VTTS_EL_N_LATIN_LETTERS {len(nm.LATIN_LETTERS)}", ""]
    out += ["static const char *const VTTS_EL_ACRONYM_WORDS[][2] = {"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in nm.ACRONYM_WORDS.items()]
    out += ["};", f"#define VTTS_EL_N_ACRONYM_WORDS {len(nm.ACRONYM_WORDS)}", ""]
    assert all(len(k) == 1 for k in nm.SYMBOLS)
    out += ["static const vtts_el_letter VTTS_EL_SYMBOLS[] = {  /* replaced in this order */"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.SYMBOLS.items()]
    out += ["};", f"#define VTTS_EL_N_SYMBOLS {len(nm.SYMBOLS)}", ""]
    out += ["#endif", ""]
    return out


TL_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_tl_tables.h"


def tagalog_tables() -> list[str]:
    """Tables of the Tagalog front-end (tl/g2p_tl.py, tl/normalize_tl.py, lexicons/tl, latin.py):
    token names, the normalizer's strings in the order the regexes and replacements use them, the
    re.IGNORECASE variants of the letters its case-insensitive patterns match, the stress table
    (folded spellings and their patterns), the affixes, the tagger's word lists and spelling
    clusters, and fold() of every code point >= 0x80."""
    import re

    from vtts.frontend import latin, latin_norm
    from vtts.frontend.lexicons import load_words
    from vtts.frontend.tl import g2p_tl as g
    from vtts.frontend.tl import normalize_tl as nm

    tset = phoneme_set.TOKENS_TLEN
    tok0 = phoneme_set.VOCAB_SIZE_V2
    assert all(t.startswith("TL:") for t in tset[tok0:]) and len(tset) < 256
    names = [t[3:] for t in tset[tok0:]]
    assert g.VOWELS == "aeiou" and g.CLITICS == ("ng", "'t", "'y")
    assert (g.ACUTE, g.GRAVE, g.CIRCUMFLEX) == ("́", "̀", "̂")
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Tagalog front-end tables (token set tl-en): src/vtts/frontend/tl, lexicons/tl, latin.py. */",
           "#ifndef VTTS_TEXT_TL_TABLES_H", "#define VTTS_TEXT_TL_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_TLEN_TOK0 {tok0}  /* id of VTTS_TL_TOKENS[0] */",
           f"#define VTTS_TLEN_VOCAB {len(tset)}", ""]
    out += c_list("VTTS_TL_TOKENS", names) + [f"#define VTTS_TL_N_TOKENS {len(names)}", ""]
    # ---- normalizer ----
    abbrev = sorted(nm.ABBREVIATIONS, key=len, reverse=True)  # apply_abbreviations order
    out += ["static const char *const VTTS_TL_ABBREV[][2] = {  /* applied in this order */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.ABBREVIATIONS[k])}}}," for k in abbrev]
    out += ["};", f"#define VTTS_TL_N_ABBREV {len(abbrev)}", ""]
    out += [f"#define VTTS_TL_DROP {c_str(latin_norm.DROP)}  /* replaced by a space */", ""]
    assert list(nm.LETTERS) == list("abcdefghijklmnopqrstuvwxyz")
    out += c_list("VTTS_TL_LETTERS", list(nm.LETTERS.values()))
    out += _str_list("VTTS_TL_ACRONYM_WORDS", sorted(nm.ACRONYM_WORDS))
    out += [f"#define VTTS_TL_N_ACRONYM_WORDS {len(nm.ACRONYM_WORDS)}", ""]
    units = sorted(nm.UNITS, key=len, reverse=True)  # the alternation order of the regexes
    out += ["static const char *const VTTS_TL_UNITS[][2] = {  /* alternation order */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.UNITS[k])}}}," for k in units]
    out += ["};", f"#define VTTS_TL_N_UNITS {len(units)}", ""]
    cur = sorted(nm.CURRENCY, key=len, reverse=True)
    out += ["static const char *const VTTS_TL_CURRENCY[][2] = {  /* alternation order */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.CURRENCY[k])}}}," for k in cur]
    out += ["};", f"#define VTTS_TL_N_CURRENCY {len(cur)}", ""]
    assert nm.MONEY_BEFORE.pattern.endswith(r"(\s?(?:libo|milyon|bilyon|trilyon))?")
    assert all(len(k) == 1 and not any(c in v for c in nm.SYMBOLS) for k, v in nm.SYMBOLS.items())
    out += ["static const struct { uint32_t cp; const char *name; } VTTS_TL_SYMBOLS[] = {  /* in this order */"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.SYMBOLS.items()]
    out += ["};", f"#define VTTS_TL_N_SYMBOLS {len(nm.SYMBOLS)}", ""]
    for name in ("ONES", "TEENS", "TENS", "ES_ONES", "ES_TENS", "ES_HUNDREDS", "MONTHS"):
        out += c_list(f"VTTS_TL_{name}", list(getattr(nm, name)))
    assert [s for s, _ in nm.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6, 1000]
    out += c_list("VTTS_TL_SCALES", [x for _, x in nm.SCALES])
    # DATE_MONTH_DAY / DATE_DAY_MONTH alternation: full names (month order), then abbreviations + "."
    keys = [(m, k) for k, m in enumerate(nm.MONTHS) if m]
    keys += [(a + ".", nm.MONTH_ABBR[a]) for a in sorted(nm.MONTH_ABBR, key=len, reverse=True)]
    assert nm._MONTH_KEYS == "|".join(k[:-1] + r"\." if k.endswith(".") else k for k, _ in keys)
    out += ["static const struct { const char *key; int month; } VTTS_TL_MONTH_KEYS[] = {  /* alternation order */"]
    out += [f"    {{{c_str(k)}, {m}}}," for k, m in keys] + ["};", f"#define VTTS_TL_N_MONTH_KEYS {len(keys)}", ""]
    assert nm.NEXT_WORD.pattern == r"\s+([a-zñ']+)"
    out += _str_list("VTTS_TL_NO_LINKER", sorted(nm.NO_LINKER)) + [f"#define VTTS_TL_N_NO_LINKER {len(nm.NO_LINKER)}", ""]
    for name in ("TIME", "DATE_MONTH_DAY", "DATE_DAY_MONTH", "REDUPLICATION", "GLOTTAL_HYPHEN"):
        assert getattr(nm, name).flags & re.IGNORECASE, name
    letters = "abcdefghijklmnopqrstuvwxyz"
    var = {ch: [c for c in range(0x110000) if not 0xD800 <= c < 0xE000 and re.fullmatch(ch, chr(c), re.IGNORECASE)]
           for ch in letters}
    width = max(len(v) for v in var.values()) + 1
    out += [f"static const uint32_t VTTS_TL_ICASE[26][{width}] = {{  /* re.IGNORECASE variants of a..z (0 ends) */"]
    out += [f"    {{{', '.join(f'0x{c:X}' for c in var[ch])}{', 0' * (width - len(var[ch]))}}},  /* {ch} */"
            for ch in letters] + ["};", ""]
    m = re.fullmatch(r"\(\?<=(\[[^]]+\])\)-\(\?=(\[[^]]+\])\)", nm.GLOTTAL_HYPHEN.pattern)
    for name, cls in (("GLOTTAL_BEFORE", m.group(1)), ("GLOTTAL_AFTER", m.group(2))):
        cps = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000 and re.fullmatch(cls, chr(c), re.IGNORECASE)]
        assert max(cps) < 0x10000
        out += [f"static const uint16_t VTTS_TL_{name}[{len(cps)}] = {{  /* {cls} with re.IGNORECASE, sorted */"]
        out += ["    " + ", ".join(f"0x{c:X}" for c in cps[i:i + 10]) + "," for i in range(0, len(cps), 10)]
        out += ["};", f"#define VTTS_TL_N_{name} {len(cps)}", ""]
    # ---- g2p ----
    table = g.stress_table()
    assert all(k.isascii() and k.isalpha() and k == k.lower() for k in table)
    out += ["/* stress table, sorted: key, fold(reading) (UTF-8, NFD: marks follow their vowel), _pattern of it:",
            " * stressed syllable counted from the end (0: the default), final glottal stop */",
            "static const struct { const char *key, *spelled; int8_t stress; uint8_t glottal; } VTTS_TL_STRESS[] = {"]
    for k in sorted(table):
        sp = g.fold(table[k])
        st, gl = g._pattern(sp)
        out.append(f"    {{{c_str(k)}, {c_str(sp)}, {st or 0}, {int(gl)}}},")
    out += ["};", f"#define VTTS_TL_N_STRESS {len(table)}", ""]
    out += _str_list("VTTS_TL_UNSTRESSED", sorted(g.UNSTRESSED)) + [f"#define VTTS_TL_N_UNSTRESSED {len(g.UNSTRESSED)}", ""]
    out += c_list("VTTS_TL_PREFIXES", list(g.PREFIXES)) + [f"#define VTTS_TL_N_PREFIXES {len(g.PREFIXES)}", ""]
    out += c_list("VTTS_TL_SUFFIXES", list(g.SUFFIXES)) + [f"#define VTTS_TL_N_SUFFIXES {len(g.SUFFIXES)}", ""]
    assert g.SPECIAL == {"ng": ("n", "a", "ng"), "mga": ("m", "a", "ng", "a")}
    assert g.SPANISH_FINAL.pattern == (r"(?:[aeiou][^aeiou]*[aeiou][^aeiou]*(?:yon|[ynt]al)|dad"
                                       r"|[aeiou][^aeiou]*(?:ar|el|or))$")
    # fold() of code points >= 0x80: the letters, ' and - and marks of NFD(lower(c)) that fold keeps:
    # base (a-z or 0) and up to two marks (1 acute, 2 grave, 3 circumflex, 4 tilde), 3 bits each
    for c in range(0x80):  # ASCII: lower-case letters, ' and - (C code), nothing else
        ch = chr(c)
        want = ch.lower() if ch.isalpha() else ch if ch in "'-" else ""
        assert g.fold("a" + ch + "a") == "a" + want + "a", c
    keep = {g.ACUTE: 1, g.GRAVE: 2, g.CIRCUMFLEX: 3, "̃": 4}
    rows = []
    for c in range(0x80, 0x110000):
        if 0xD800 <= c < 0xE000:
            continue
        d = [x for x in unicodedata.normalize("NFD", chr(c).lower()) if "a" <= x <= "z" or x in keep]
        assert not any(x in "'-" for x in unicodedata.normalize("NFD", chr(c).lower())), hex(c)
        if not d:
            continue
        base = d[0] if "a" <= d[0] <= "z" else ""
        ms = [keep[x] for x in d[len(base):]]
        assert c < 0x10000 and len(ms) <= 2 and len(ms) == len(d) - len(base), hex(c)
        rows.append((c, base, ms[0] | (ms[1] << 3) if len(ms) == 2 else ms[0] if ms else 0))
    out += ["typedef struct { uint16_t cp; char base; uint8_t marks; } vtts_tl_fold;",
            "/* fold of code points >= 0x80, sorted: base letter (0: none), marks (3 bits each, first in the",
            " * low bits: 1 acute, 2 grave, 3 circumflex, 4 tilde) */",
            f"static const vtts_tl_fold VTTS_TL_FOLD[{len(rows)}] = {{"]
    out += ["    " + " ".join(f"{{0x{c:X}, {repr(b) if b else 0}, {mk}}}," for c, b, mk in rows[i:i + 6])
            for i in range(0, len(rows), 6)] + ["};", f"#define VTTS_TL_N_FOLD {len(rows)}", ""]
    # ---- tagging (latin.latin_word_lang) and valid_spelling ----
    assert "tl" in latin.HYPHEN_ENGLISH and "tl" not in getattr(latin, "APOSTROPHE_LETTER", ())
    out += [f"#define VTTS_TL_OWN {c_str(latin.LATIN_PAIRS['tl'])}  /* LATIN_PAIRS: a word with one is Tagalog */", ""]
    native = sorted(load_words("tl", "native"))
    out += _str_list("VTTS_TL_NATIVE", native) + [f"#define VTTS_TL_N_NATIVE {len(native)}", ""]
    tkeys = sorted(latin._table_keys("tl"))
    out += _str_list("VTTS_TL_TABLE_KEYS", tkeys) + [f"#define VTTS_TL_N_TABLE_KEYS {len(tkeys)}", ""]
    for name in ("ONSETS", "CODAS", "FINALS", "DOUBLES"):
        vals = sorted(getattr(g, name))
        out += _str_list(f"VTTS_TL_{name}", vals) + [f"#define VTTS_TL_N_{name} {len(vals)}", ""]
    out += c_list("VTTS_TL_FOREIGN", list(g.FOREIGN)) + [f"#define VTTS_TL_N_FOREIGN {len(g.FOREIGN)}", ""]
    out += c_list("VTTS_TL_NATIVE_OO", list(g.NATIVE_OO)) + [f"#define VTTS_TL_N_NATIVE_OO {len(g.NATIVE_OO)}", ""]
    out += ["#endif", ""]
    return out


SW_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_sw_tables.h"


def swahili_tables() -> list[str]:
    """Tables of the Swahili front-end (sw/g2p_sw.py, sw/normalize_sw.py, lexicons/sw/, latin.py):
    token names, the normalizer's tables in the order its regexes and replacements use them, the
    word lists of the tagger, the stress exceptions, fold() of every code point (letter and acute
    accent, as runs) and the re.IGNORECASE variants of the letters its case-insensitive rules use.
    The English word list is the one of vtts_text_tables.h (vtts_lt_is_english)."""
    import re

    from vtts.frontend import latin, latin_norm
    from vtts.frontend.lexicons import load_words
    from vtts.frontend.sw import g2p_sw as g
    from vtts.frontend.sw import normalize_sw as nm

    tset = phoneme_set.TOKEN_SETS[phoneme_set.PAIR_MODES["sw"]]
    tok0 = phoneme_set.VOCAB_SIZE_V2
    assert all(t.startswith("SW:") for t in tset[tok0:])
    names = [t[3:] for t in tset[tok0:]]
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
           "/* Swahili front-end (token set sw-en; ids 0..106 are the v2 ids) */",
           "#ifndef VTTS_TEXT_SW_TABLES_H", "#define VTTS_TEXT_SW_TABLES_H", "#include <stdint.h>", "",
           f"#define VTTS_SW_TOK0 {tok0}", f"#define VTTS_SW_VOCAB {len(tset)}", f"#define VTTS_SW_N_TOKENS {len(names)}"]
    out += c_list("VTTS_SW_TOKENS", names)
    abbrev = sorted(nm.ABBREVIATIONS, key=len, reverse=True)  # apply_abbreviations order
    out += ["static const char *const VTTS_SW_ABBREV[][2] = {  /* in the order they are applied */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.ABBREVIATIONS[k])}}}," for k in abbrev]
    out += ["};", f"#define VTTS_SW_N_ABBREV {len(abbrev)}", f"#define VTTS_SW_DROP {c_str(latin_norm.DROP)}", ""]
    assert list(nm.LETTERS) == [chr(c) for c in range(ord("a"), ord("z") + 1)]
    out += c_list("VTTS_SW_LETTERS", list(nm.LETTERS.values()))
    out += _str_list("VTTS_SW_ACRONYM_WORDS", sorted(nm.ACRONYM_WORDS))
    out += [f"#define VTTS_SW_N_ACRONYM_WORDS {len(nm.ACRONYM_WORDS)}", ""]
    units = sorted(nm.UNITS, key=len, reverse=True)  # the alternation order of UNIT and UNIT_BEFORE
    assert nm.UNIT_BEFORE.pattern.split("(", 2)[2].split(")")[0] == "|".join(
        re.escape(u) for u in units if len(u) > 1 and u.isalpha())
    out += ["/* UNITS in alternation order; before: also read before its number (UNIT_BEFORE) */",
            "static const struct { const char *key, *reading; uint8_t before; } VTTS_SW_UNITS[] = {"]
    out += [f"    {{{c_str(k)}, {c_str(nm.UNITS[k])}, {int(len(k) > 1 and k.isalpha())}}}," for k in units]
    out += ["};", f"#define VTTS_SW_N_UNITS {len(units)}", ""]
    cur = sorted(nm.CURRENCY, key=len, reverse=True)
    out += ["static const char *const VTTS_SW_CURRENCY[][2] = {  /* MONEY_BEFORE alternation order */"]
    out += [f"    {{{c_str(k)}, {c_str(nm.CURRENCY[k])}}}," for k in cur] + ["};", f"#define VTTS_SW_N_CURRENCY {len(cur)}", ""]
    # MONEY_AFTER: NUM \s? (?:/=|(symbols)|\s?(?:words)(?![\w]))
    m = re.search(r"\\s\?\(\?:/=\|\((.*?)\)\|\\s\?\(\?:(.*?)\)\(\?!\[\\w\]\)\)$", nm.MONEY_AFTER.pattern)
    assert m, nm.MONEY_AFTER.pattern
    after = [re.sub(r"\\(.)", r"\1", s) for s in m.group(1).split("|")]
    words = m.group(2).split("|")
    assert all(s in nm.CURRENCY for s in after)
    out += c_list("VTTS_SW_CUR_AFTER", after) + [f"#define VTTS_SW_N_CUR_AFTER {len(after)}", ""]
    out += c_list("VTTS_SW_CUR_WORDS", words) + [f"#define VTTS_SW_N_CUR_WORDS {len(words)}", ""]
    assert all(len(k) == 1 for k in nm.SYMBOLS)
    out += ["static const struct { uint32_t cp; const char *text; } VTTS_SW_SYMBOLS[] = {  /* replaced in this order */"]
    out += [f"    {{0x{ord(k):04X}, {c_str(v)}}}," for k, v in nm.SYMBOLS.items()]
    out += ["};", f"#define VTTS_SW_N_SYMBOLS {len(nm.SYMBOLS)}", ""]
    out += c_list("VTTS_SW_CONCORDS", list(nm.CONCORDS)) + [f"#define VTTS_SW_N_CONCORDS {len(nm.CONCORDS)}", ""]
    out += c_list("VTTS_SW_ONES", list(nm.ONES)) + c_list("VTTS_SW_TENS", list(nm.TENS))
    assert [s for s, _ in nm.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6]
    out += c_list("VTTS_SW_SCALES", [x for _, x in nm.SCALES]) + c_list("VTTS_SW_MONTHS", list(nm.MONTHS))
    native = sorted(load_words("sw", "native"))
    keys = sorted(k for k in latin._table_keys("sw") if k.isascii())  # others never equal a plain Latin word
    assert all(w.isascii() for w in native)
    out += _str_list("VTTS_SW_NATIVE", native) + [f"#define VTTS_SW_N_NATIVE {len(native)}", ""]
    out += _str_list("VTTS_SW_TABLE_KEYS", keys) + [f"#define VTTS_SW_N_TABLE_KEYS {len(keys)}", ""]
    stress = g.stress_table()
    out += ["static const char *const VTTS_SW_STRESS[][2] = {  /* lexicons/sw/stress.tsv: word, respelling */"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in stress.items()]
    out += ["};", f"#define VTTS_SW_N_STRESS {len(stress)}", ""]
    out += _str_list("VTTS_SW_UNSTRESSED", sorted(g.UNSTRESSED)) + [f"#define VTTS_SW_N_UNSTRESSED {len(g.UNSTRESSED)}", ""]
    assert g.VOWELS == "aeiou" and g.ACUTE == "\u0301"
    out += ["static const char *const VTTS_SW_DIGRAPHS[][2] = {  /* tried in this order: spelling, sound */"]
    out += [f"    {{{c_str(d)}, {c_str(g.SOUND.get(d, d))}}}," for d in g.DIGRAPHS]
    out += ["};", f"#define VTTS_SW_N_DIGRAPHS {len(g.DIGRAPHS)}", ""]
    out += ["static const char *const VTTS_SW_CODES[][2] = {  /* valid_spelling: replaced in this order */"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for a, b in g.CODES] + ["};", f"#define VTTS_SW_N_CODES {len(g.CODES)}", ""]
    # fold() of one code point: lower(), ’ -> ', NFD, keep a-z ' and an acute accent (kept by fold
    # only right after a vowel, which the C reader checks). Runs: start, count, first letter (0: none),
    # step 0/1, acute.
    folded = []
    for c in range(0x80, 0x110000):
        if 0xD800 <= c < 0xE000:
            continue
        d = unicodedata.normalize("NFD", chr(c).lower().replace("’", "'"))
        kept = [ch for ch in d if "a" <= ch <= "z" or ch in "'\u0301"]
        if not kept:
            continue
        s = "".join(kept)
        assert re.fullmatch("[a-z']?\u0301?", s), (hex(c), s)
        folded.append((c, ord(s[0]) if s[0] != "\u0301" else 0, int(s.endswith("\u0301"))))
    for c in range(0x80):  # ASCII: lower-case a-z and '
        assert g.fold(chr(c)) == (chr(c).lower() if chr(c).isalpha() or chr(c) == "'" else ""), c
    runs: list[list[int]] = []
    for c, f, a in folded:
        if runs and c == runs[-1][0] + runs[-1][1] and runs[-1][4] == a and runs[-1][1] < 65535:
            r = runs[-1]
            if r[1] == 1 and f and r[2] and f in (r[2], r[2] + 1):
                r[1], r[3] = 2, f - r[2]
                continue
            if r[1] > 1 and f == r[2] + r[1] * r[3] and (f or not r[2]):
                r[1] += 1
                continue
            if r[1] == 1 and not f and not r[2]:
                r[1] += 1
                continue
        runs.append([c, 1, f, 0, a])
    out += ["typedef struct { uint32_t start; uint16_t count; uint8_t first, step, acute; } vtts_sw_fold;",
            f"static const vtts_sw_fold VTTS_SW_FOLD[{len(runs)}] = {{"]
    out += ["    " + " ".join(f"{{0x{a:X}, {n}, 0x{f:02X}, {s}, {ac}}}," for a, n, f, s, ac in runs[i:i + 4])
            for i in range(0, len(runs), 4)] + ["};", f"#define VTTS_SW_N_FOLD {len(runs)}", ""]
    for c, f, a in folded[::97]:  # the runs reproduce the table
        r = next(r for r in runs if r[0] <= c < r[0] + r[1])
        assert (r[2] + (c - r[0]) * r[3] if r[2] else 0, r[4]) == (f, a)
    # re.IGNORECASE: the literal words of DATE (tarehe), TIME (saa), PERCENT (asilimia) and ORDINAL
    for pat, word in ((nm.DATE_DMY, "tarehe"), (nm.TIME, "saa"), (nm.PERCENT, "asilimia")):
        assert pat.flags & re.IGNORECASE and f"(?<![\\w]){word}\\s+" in pat.pattern
    assert nm.ORDINAL.flags & re.IGNORECASE and nm.DATE_ISO.flags & re.IGNORECASE
    letters = sorted(set("tarehesaaasilimia" + "".join(nm.CONCORDS)))
    var = {ch: [c for c in range(0x110000)
                if not 0xD800 <= c < 0xE000 and re.fullmatch(ch, chr(c), re.IGNORECASE)] for ch in letters}
    width = max(len(v) for v in var.values()) + 1
    out += [f"static const uint32_t VTTS_SW_ICASE[{len(letters)}][{width}] = {{  /* re.I variants of a letter (0 ends) */"]
    out += [f"    {{{', '.join(f'0x{c:X}' for c in var[ch])}{', 0' * (width - len(var[ch]))}}},  /* {ch} */"
            for ch in letters]
    out += ["};", f"#define VTTS_SW_N_ICASE {len(letters)}", "", "#endif", ""]
    return out


def main() -> None:
    import gen_text_tables_nx  # Dutch, Swedish, Norwegian: runtime/src/vtts_text_nx_tables.h

    gen_text_tables_nx.write()
    AR_OUT.write_text("\n".join(arabic_tables()), encoding="utf-8")
    print(f"wrote {AR_OUT}")
    TH_OUT.write_text("\n".join(thai_tables()), encoding="utf-8")
    print(f"wrote {TH_OUT}")
    MS_OUT.write_text("\n".join(malay_tables()), encoding="utf-8")
    print(f"wrote {MS_OUT}")
    TL_OUT.write_text("\n".join(tagalog_tables()), encoding="utf-8")
    print(f"wrote {TL_OUT}")
    SW_OUT.write_text("\n".join(swahili_tables()), encoding="utf-8")
    print(f"wrote {SW_OUT}")
    FI_OUT.write_text("\n".join(finnish_tables()), encoding="utf-8")
    print(f"wrote {FI_OUT}")
    EL_OUT.write_text("\n".join(greek_tables()), encoding="utf-8")
    print(f"wrote {EL_OUT}")
    DE_OUT.write_text("\n".join(german_tables()), encoding="utf-8")
    print(f"wrote {DE_OUT}")
    FR_OUT.write_text("\n".join(french_tables()), encoding="utf-8")
    print(f"wrote {FR_OUT}")
    import gen_lt_tables_it_tr  # Italian and Turkish (vtts_text_it_tables.h, vtts_text_tr_tables.h)

    gen_lt_tables_it_tr.write_all()
    rows = []
    for base in BASES:
        for tone_mark, tone in [("", 1)] + list(_TONE_MARKS.items()):
            for case in (str.lower, str.upper):
                ch = unicodedata.normalize("NFC", case(base) + tone_mark)
                if len(ch) == 1:
                    rows.append((ord(ch), letter_code(base), tone))
    rows = sorted(set(rows))
    lines = ["/* SPDX-License-Identifier: Apache-2.0 */",
             "/* generated by runtime/tools/gen_text_tables.py -- do not edit */",
             "#ifndef VTTS_TEXT_TABLES_H", "#define VTTS_TEXT_TABLES_H", "#include <stdint.h>", "",
             '#include "vtts_langs.h" /* VTTS_ENABLE_ES, _ID, _PT: rows of VTTS_LT_LANGS */', "",
             f'#define VTTS_PHONEME_SET_VERSION "{phoneme_set.PHONEME_SET_VERSION}"',
             "typedef struct { uint32_t cp; char code; uint8_t tone; } vtts_letter;",
             f"static const vtts_letter VTTS_LETTERS[{len(rows)}] = {{"]
    lines += [f"    {{0x{cp:04X}, '{code}', {tone}}}," for cp, code, tone in rows]
    lines += ["};", f"#define VTTS_N_LETTERS {len(rows)}", ""]
    lines += [f"static const char *const VTTS_TOKENS[{len(phoneme_set.TOKENS)}] = {{"]
    lines += ["    " + ", ".join(c_str(t) for t in phoneme_set.TOKENS[i:i + 8]) + ","
              for i in range(0, len(phoneme_set.TOKENS), 8)]
    lines += ["};", f"#define VTTS_N_TOKENS {len(phoneme_set.TOKENS)}", ""]
    for name, table in (("LOANWORDS", lexicon.LOANWORDS), ("ABBREVIATIONS", lexicon.ABBREVIATIONS),
                        ("LETTER_NAMES", lexicon.LETTER_NAMES)):
        items = sorted(table.items(), key=lambda kv: -len(kv[0]))
        lines += [f"static const char *const VTTS_{name}[][2] = {{"]
        lines += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in items]
        lines += ["};", f"#define VTTS_N_{name} {len(items)}", ""]
    lines += english_tables()
    lines += chinese_tables()
    lines += korean_tables()
    lines += hindi_tables()
    lines += japanese_tables()
    lines += unicode_tables()
    lines += latin_tables()
    lines += ["#endif", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} letters)")
    import gen_slavic_tables  # Russian (and Polish) tables and patterns: vtts_text_ru_tables.h ...

    gen_slavic_tables.main()


if __name__ == "__main__":
    main()
