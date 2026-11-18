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
        descs.append(
            f"    {{{c_str(code)}, {tok0}, {n(names)}, {n(tset)}, VTTS_{up}_TOKENS, VTTS_{up}_ABBREV, {n(abbrev)},\n"
            f"     {c_str(drop)}, VTTS_{up}_LETTERS, {n(letters)}, VTTS_{up}_ACRONYM_WORDS, {n(nm.ACRONYM_WORDS)},\n"
            f"     VTTS_{up}_UNITS, {n(units)}, VTTS_{up}_CURRENCY, {n(cur)}, VTTS_{up}_SYMBOLS, {n(nm.SYMBOLS)},\n"
            f"     {c_str(nm.MARK_WORDS[','])}, {c_str(nm.MARK_WORDS['.'])}, VTTS_{up}_MONTHS,\n"
            f"     VTTS_{up}_NATIVE, {n(native)}, VTTS_{up}_TABLE_KEYS, {n(keys)}, VTTS_{up}_OVERRIDES, {n(ovr)},\n"
            f"     VTTS_{up}_UNSTRESSED, {n(g.UNSTRESSED)}, {c_str(latin.LATIN_PAIRS[code])}, {c_str(extra)},\n"
            f"     VTTS_{up}_FOLD, {n(runs)}, VTTS_{up}_ONSETS, {n(g.ONSETS)}, VTTS_{up}_CODAS, {n(g.CODAS)},\n"
            f"     VTTS_{up}_FINALS, {n(g.FINALS)}, VTTS_{up}_DOUBLES, {n(g.DOUBLES)}, VTTS_{up}_FOREIGN, {n(g.FOREIGN)},\n"
            f"     VTTS_{up}_DIGRAPHS, {n(g.DIGRAPHS)}}},")
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


def main() -> None:
    TH_OUT.write_text("\n".join(thai_tables()), encoding="utf-8")
    print(f"wrote {TH_OUT}")
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


if __name__ == "__main__":
    main()
