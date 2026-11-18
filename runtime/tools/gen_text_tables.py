"""Generate runtime/src/vtts_text_tables.h from the Python front-end (single source of truth).

Run: uv run python runtime/tools/gen_text_tables.py
"""

import unicodedata
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


def main() -> None:
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
    lines += ["#endif", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} letters)")


if __name__ == "__main__":
    main()
