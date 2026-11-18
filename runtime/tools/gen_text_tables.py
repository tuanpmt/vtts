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
    lines += ["#endif", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} letters)")


if __name__ == "__main__":
    main()
