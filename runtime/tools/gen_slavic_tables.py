"""Generate runtime/src/vtts_text_ru_tables.h (Russian) and vtts_text_pl_tables.h (Polish) from the
Python front-end, including its regex patterns as parse trees for runtime/src/vtts_re.c.

Run: uv run python runtime/tools/gen_slavic_tables.py (gen_text_tables.py runs it too).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
RU_OUT = SRC / "vtts_text_ru_tables.h"


def c_str(s: str) -> str:
    """A C string literal (UTF-8, escapes for \\ and \")."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ReTables:
    """Parse trees of Python patterns (re._parser, the parser re itself uses) as the node, class item
    and alternative tables of vtts_re.h. Non-capturing groups are flattened into their sequence."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.nodes: list[list] = []
        self.items: list[tuple[str, int, int]] = []
        self.alts: list[tuple[int, int]] = []
        self.patterns: list[tuple[str, int, int, int, str]] = []

    def _flat(self, sub) -> list:
        from re import _constants as C

        out = []
        for op, av in sub:
            if op is C.SUBPATTERN and av[0] is None:
                assert not av[1] and not av[2], "inline flags are not supported"
                out += self._flat(av[3])
            else:
                out.append((op, av))
        return out

    def _seq(self, sub) -> tuple[int, int]:
        items = self._flat(sub)
        start = len(self.nodes)
        self.nodes += [None] * len(items)
        for k, (op, av) in enumerate(items):
            self.nodes[start + k] = self._node(op, av)
        return start, len(items)

    def _node(self, op, av) -> list:
        from re import _constants as C

        if op is C.LITERAL:
            return ["VTTS_RE_LIT", 0, 0, 0, av, 0]
        if op is C.NOT_LITERAL:
            return ["VTTS_RE_NLIT", 0, 0, 0, av, 0]
        if op is C.ANY:
            return ["VTTS_RE_ANY", 0, 0, 0, 0, 0]
        if op is C.IN:
            neg = 0
            first = len(self.items)
            for iop, iav in av:
                if iop is C.NEGATE:
                    neg = 1
                elif iop is C.LITERAL:
                    self.items.append(("VTTS_RE_I_LIT", iav, 0))
                elif iop is C.RANGE:
                    self.items.append(("VTTS_RE_I_RANGE", iav[0], iav[1]))
                elif iop is C.CATEGORY:
                    kind = {C.CATEGORY_DIGIT: "DIGIT", C.CATEGORY_NOT_DIGIT: "NDIGIT",
                            C.CATEGORY_WORD: "WORD", C.CATEGORY_NOT_WORD: "NWORD",
                            C.CATEGORY_SPACE: "SPACE", C.CATEGORY_NOT_SPACE: "NSPACE"}[iav]
                    self.items.append((f"VTTS_RE_I_{kind}", 0, 0))
                else:
                    raise ValueError(f"class item {iop}")
            return ["VTTS_RE_IN", neg, len(self.items) - first, 0, first, 0]
        if op is C.MAX_REPEAT:
            lo, hi, body = av
            s, n = self._seq(body)
            return ["VTTS_RE_REPEAT", 0, n, s, lo, "VTTS_RE_INF" if hi is C.MAXREPEAT else hi]
        if op is C.SUBPATTERN:
            group, add, rem, body = av
            assert not add and not rem
            s, n = self._seq(body)
            return ["VTTS_RE_GROUP", 0, n, s, group, 0]
        if op is C.BRANCH:
            seqs = [self._seq(b) for b in av[1]]
            first = len(self.alts)
            self.alts += seqs
            return ["VTTS_RE_BRANCH", 0, len(seqs), 0, first, 0]
        if op in (C.ASSERT, C.ASSERT_NOT):
            direction, body = av
            lo, hi = body.getwidth()
            if direction < 0:
                assert lo == hi, "lookbehind of a variable width"
            s, n = self._seq(body)
            flag = (1 if op is C.ASSERT_NOT else 0) | (2 if direction < 0 else 0)
            return ["VTTS_RE_ASSERT", flag, n, s, lo if direction < 0 else 0, 0]
        if op is C.AT:
            kind = {C.AT_BEGINNING: 1, C.AT_BEGINNING_STRING: 1, C.AT_END: 2, C.AT_BOUNDARY: 3,
                    C.AT_NON_BOUNDARY: 4, C.AT_END_STRING: 5}[av]
            return ["VTTS_RE_AT", 0, 0, 0, kind, 0]
        if op is C.GROUPREF:
            return ["VTTS_RE_GROUPREF", 0, 0, 0, av, 0]
        raise ValueError(f"unsupported regex op {op}")

    def add(self, name: str, pattern) -> None:
        """pattern: a compiled str re.Pattern without flags (other than the implicit re.UNICODE)."""
        from re import _parser

        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        assert pattern.flags & ~re.UNICODE == 0, name
        tree = _parser.parse(pattern.pattern, pattern.flags)
        assert tree.state.groups - 1 <= 10, name
        start, n = self._seq(tree)
        self.patterns.append((name, start, n, tree.state.groups - 1, pattern.pattern))

    def lines(self) -> list[str]:
        p = self.prefix
        out = [f"static const vtts_re_node {p}_RE_NODES[{max(1, len(self.nodes))}] = {{"]
        for op, flag, ln, body, a, b in self.nodes or [["0", 0, 0, 0, 0, 0]]:
            bb = b if isinstance(b, str) else f"{b}u"
            out.append(f"    {{{op}, {flag}, {ln}, {body}, {a}u, {bb}}},")
        out += ["};", f"static const vtts_re_item {p}_RE_ITEMS[{max(1, len(self.items))}] = {{"]
        out += [f"    {{{k}, 0x{lo:X}, 0x{hi:X}}}," for k, lo, hi in self.items] or ["    {0, 0, 0},"]
        out += ["};", f"static const vtts_re_alt {p}_RE_ALTS[{max(1, len(self.alts))}] = {{"]
        out += [f"    {{{s}, {n}}}," for s, n in self.alts] or ["    {0, 0},"]
        out += ["};"]
        for name, start, n, groups, pat in self.patterns:
            shown = pat.encode("ascii", "backslashreplace").decode().replace("*/", "* /")
            decl = (f"static const vtts_re {p}_RE_{name} = {{{p}_RE_NODES, {p}_RE_ITEMS, {p}_RE_ALTS, "
                    f"{start}, {n}, {groups}}};")
            out += [f"/* {shown} */", decl]
        return out + [""]


def str_list(name: str, items) -> list[str]:
    items = list(items)
    out = [f"static const char *const {name}[{max(1, len(items))}] = {{"]
    out += ["    " + ", ".join(c_str(s) for s in items[i:i + 6]) + "," for i in range(0, len(items), 6)]
    if not items:
        out.append('    "",')
    return out + ["};", f"#define {name.replace('VTTS_', 'VTTS_N_', 1)} {len(items)}", ""]


def pairs(name: str, items) -> list[str]:
    items = list(items)
    out = [f"static const char *const {name}[{len(items)}][2] = {{"]
    out += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in items]
    return out + ["};", f"#define {name.replace('VTTS_', 'VTTS_N_', 1)} {len(items)}", ""]


def forms_table(name: str, table: dict) -> list[str]:
    """key -> (gender, one, few, many) as {key, gender, one, few, many}, in the dict's order."""
    out = [f"static const char *const {name}[{len(table)}][5] = {{"]
    out += [f"    {{{c_str(k)}, {', '.join(c_str(x) for x in v)}}}," for k, v in table.items()]
    return out + ["};", f"#define {name.replace('VTTS_', 'VTTS_N_', 1)} {len(table)}", ""]


# Words the Russian code writes directly (asserted to occur in the Python sources).
RU_LITERALS = {"MINUS": "минус", "ZERO": "ноль", "ZERO_GEN": "ноля", "TYSYACHA_GEN": "тысячи",
               "TYSYACHN": "тысячн", "MILLIONN": "миллионн", "CELAYA": "целая", "CELYKH": "целых",
               "ZAPYATAYA": "запятая", "PLUS": "плюс", "OT": "от", "DO": "до", "GODA": "года",
               "GODU": "году", "GODAKH": "годах", "GODY": "годы", "VEK": "век", "VEKOV": "веков",
               "I": "и", "SEKUNDA": "секунда", "SEKUNDY": "секунды", "SEKUND": "секунд",
               "PROCENT": "процент", "PROCENTA": "процента", "PROCENTOV": "процентов", "ODNA": "одна",
               "ODNO": "одно", "DVE": "две", "ODNOGO": "одного", "ODNOY": "одной"}


def russian_tables() -> list[str]:
    from vtts.frontend import latin_norm
    from vtts.frontend.phoneme_set import RU_PAIRED, TOKENS_RUEN
    from vtts.frontend.ru import g2p_ru as g
    from vtts.frontend.ru import normalize_ru as nr

    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_slavic_tables.py -- do not edit */",
           "/* Russian front-end tables (token set ru-en): src/vtts/frontend/ru and lexicons/ru (the stress",
           " * tables are in the RLEX blob, scripts/frontend/build_ru_blob.py). */",
           "#ifndef VTTS_TEXT_RU_TABLES_H", "#define VTTS_TEXT_RU_TABLES_H", "#include <stdint.h>", "",
           '#include "vtts_re.h"', ""]
    block = [t[3:] for t in TOKENS_RUEN[107:]]
    out += ["/* phonemes of the ru-en block: token id = 107 + index */"]
    out += str_list("VTTS_RU_PHONEMES", block)
    out += [f"#define VTTS_RU_FIRST_ID {len(TOKENS_RUEN) - len(block)}", ""]
    out += str_list("VTTS_RU_PAIRED", RU_PAIRED)
    out += pairs("VTTS_RU_VOICED", g.VOICED.items())
    out += str_list("VTTS_RU_OBSTRUENTS", sorted(g.OBSTRUENTS))
    out += pairs("VTTS_RU_CONSONANT", g.CONSONANT.items())
    out += pairs("VTTS_RU_VOWEL_OF", g.VOWEL_OF.items())
    # per code point: what fold() makes of one character (after lower() and compose())
    fold = []
    for cp in range(0x110000):
        if 0xD800 <= cp < 0xE000:
            continue
        ch = chr(cp)
        if ch in g.LETTERS or ch in "-+":
            continue
        low = ch.lower()
        if len(low) != 1 or low != ch:
            continue
        f = g.fold(ch)
        if f:
            fold.append((cp, f))
    out += ["/* fold() of one lower-case character other than а-я ё - +: Cyrillic letters of other",
            " * languages and letters whose NFD base letter is Russian (sorted by code point) */",
            f"static const struct {{ uint32_t cp; const char *to; }} VTTS_RU_FOLD[{len(fold)}] = {{"]
    out += [f"    {{0x{cp:04X}, {c_str(f)}}}," for cp, f in fold]
    out += ["};", f"#define VTTS_RU_N_FOLD {len(fold)}", ""]
    out += pairs("VTTS_RU_COMPOSE", g.COMPOSE.items())
    out += str_list("VTTS_RU_UNSTRESSED", sorted(g.UNSTRESSED))
    out += str_list("VTTS_RU_CHN_SH", g.CHN_SH)
    out += str_list("VTTS_RU_GO_KEEP", sorted(g.GO_KEEP))
    out += pairs("VTTS_RU_LETTER_NAMES", nr.LETTER_NAMES.items())
    out += pairs("VTTS_RU_LATIN_LETTERS", nr.LATIN_LETTERS.items())
    # normalizer data
    out += str_list("VTTS_RU_ONES", nr.ONES) + str_list("VTTS_RU_TENS", nr.TENS)
    out += str_list("VTTS_RU_HUNDREDS", nr.HUNDREDS) + str_list("VTTS_RU_ONES_GEN", nr.ONES_GEN)
    out += str_list("VTTS_RU_TENS_GEN", nr.TENS_GEN) + str_list("VTTS_RU_HUNDREDS_GEN", nr.HUNDREDS_GEN)
    exps = {10 ** 12: 12, 10 ** 9: 9, 10 ** 6: 6, 1000: 3}
    out += ["/* SCALES: power of ten, gender, one, few, many */",
            f"static const struct {{ int exp; char gender; const char *one, *few, *many; }} VTTS_RU_SCALES[{len(nr.SCALES)}] = {{"]
    out += [f"    {{{exps[v]}, '{gd}', {c_str(a)}, {c_str(b)}, {c_str(c)}}}," for v, gd, a, b, c in nr.SCALES]
    out += ["};", f"#define VTTS_RU_N_SCALES {len(nr.SCALES)}", ""]
    out += pairs("VTTS_RU_ORD_ONES", nr.ORD_ONES)
    out += str_list("VTTS_RU_ORD_TENS", nr.ORD_TENS) + str_list("VTTS_RU_ORD_TENS_CLASS", nr.ORD_TENS_CLASS)
    out += str_list("VTTS_RU_ORD_HUNDREDS", nr.ORD_HUNDREDS) + str_list("VTTS_RU_ORD_THOUSANDS", nr.ORD_THOUSANDS)
    out += str_list("VTTS_RU_CASES", nr.CASES)
    out += [f"static const char *const VTTS_RU_ENDINGS[3][{len(nr.CASES)}] = {{  /* classes h, s, t */"]
    out += ["    {" + ", ".join(c_str(e) for e in nr.ENDINGS[k]) + "}," for k in "hst"]
    out += ["};", ""]
    out += pairs("VTTS_RU_SUFFIX_CASE", nr.SUFFIX_CASE.items())
    out += str_list("VTTS_RU_MONTHS", nr.MONTHS)
    out += pairs("VTTS_RU_YEAR_NOUN", nr.YEAR_NOUN.items())
    out += pairs("VTTS_RU_CENTURY_NOUN", nr.CENTURY_NOUN.items())
    out += str_list("VTTS_RU_GEN_PREPOSITIONS", sorted(nr.GEN_PREPOSITIONS))
    out += str_list("VTTS_RU_GEN_COUNT", sorted(nr.GEN_COUNT))
    out += str_list("VTTS_RU_ACRONYM_WORDS", sorted(nr.ACRONYM_WORDS))
    out += str_list("VTTS_RU_SPELLED", sorted(nr.SPELLED))
    abbr = sorted(nr.ABBREVIATIONS, key=len, reverse=True)
    out += pairs("VTTS_RU_ABBREVIATIONS", [(k, nr.ABBREVIATIONS[k]) for k in abbr])
    out += forms_table("VTTS_RU_UNITS", nr.UNITS) + forms_table("VTTS_RU_CURRENCY", nr.CURRENCY)
    out += forms_table("VTTS_RU_SUBUNIT", nr.SUBUNIT)
    out += ["/* SCALE_ABBR: key, power of ten */",
            f"static const struct {{ const char *key; int exp; }} VTTS_RU_SCALE_ABBR[{len(nr.SCALE_ABBR)}] = {{"]
    out += [f"    {{{c_str(k)}, {len(str(v)) - 1}}}," for k, v in nr.SCALE_ABBR.items()]
    out += ["};", f"#define VTTS_RU_N_SCALE_ABBR {len(nr.SCALE_ABBR)}", ""]
    out += str_list("VTTS_RU_LATIN_WORDS", sorted(nr.LATIN_WORDS))
    out += pairs("VTTS_RU_SYMBOLS", nr.SYMBOLS.items())
    out += str_list("VTTS_RU_FRACTION", nr.FRACTION) + str_list("VTTS_RU_FRACTION_PL", nr.FRACTION_PL)
    out += pairs("VTTS_RU_COMPOUND_PREFIX", [(str(k), v) for k, v in nr.COMPOUND_PREFIX.items()])
    out += [f"#define VTTS_RU_DROP {c_str(latin_norm.DROP)}", ""]
    assert nr.CLITICS == frozenset(("в", "к", "с")) and nr.MARKS == ",.?!;:"
    src = Path(nr.__file__).read_text(encoding="utf-8")
    assert all(v in src for v in RU_LITERALS.values())
    out += [f"#define VTTS_RU_L_{k} {c_str(v)}" for k, v in RU_LITERALS.items()] + [""]
    lfold = []
    for cp in range(0xC0, 0x250):
        f = "".join(c for c in unicodedata.normalize("NFKD", chr(cp)) if c.isascii())
        assert len(f) <= 2
        lfold.append(c_str(f))
    out += ["/* ASCII letters of the NFKD form of U+00C0..U+024F (the LATIN pass) */",
            f"static const char VTTS_RU_LATIN_FOLD[{len(lfold)}][3] = {{"]
    out += ["    " + ", ".join(lfold[i:i + 12]) + "," for i in range(0, len(lfold), 12)] + ["};", ""]
    # regexes
    rt = ReTables("VTTS_RU")
    for k, (pat, rep) in enumerate(g.RULES):
        rt.add(f"RULE{k}", pat)
    rt.add("GO", r"г(\+?о)$")
    rt.add("DOUBLE", r"([бвгджзклмнпрстфхцчшщ])\1")
    for name in ("PHONE", "DATE_ISO", "DATE_DMY", "YEAR", "CENTURY", "DAY_MONTH", "REGNAL", "TIME",
                 "SCALED", "MONEY_BEFORE", "MONEY_AFTER", "PERCENT", "UNIT", "ORDINAL", "COMPOUND",
                 "RANGE", "NUMBER", "ACRONYM", "LATIN", "WORD"):
        rt.add(name, getattr(nr, name))
    rt.add("PAUSE", latin_norm.PAUSE)
    # latin_norm.parse_number: re.fullmatch of its two thousands patterns (\Z ends the match)
    rt.add("THOUSANDS_DOT", r"\d{1,3}(\.\d{3})+(,\d+)?\Z")
    rt.add("THOUSANDS_COMMA", r"\d{1,3}(,\d{3})+(\.\d+)?\Z")
    rt.add("PRODUCT_CODE", latin_norm.PRODUCT_CODE)
    for k, key in enumerate(abbr):
        rt.add(f"ABBR{k}", r"(?<![\w])" + re.escape(key) + ("" if key.endswith(".") else r"(?![\w])"))
    out += [f"static const char *const VTTS_RU_RULE_REP[{len(g.RULES)}] = {{"]
    out += ["    " + ", ".join(c_str(rep) for _, rep in g.RULES) + ",", "};", f"#define VTTS_RU_N_RULES {len(g.RULES)}", ""]
    out += rt.lines()
    out += [f"static const vtts_re *const VTTS_RU_RULES_RE[{len(g.RULES)}] = {{"]
    out += ["    " + ", ".join(f"&VTTS_RU_RE_RULE{k}" for k in range(len(g.RULES))) + ",", "};"]
    out += [f"static const vtts_re *const VTTS_RU_ABBR_RE[{len(abbr)}] = {{"]
    out += ["    " + ", ".join(f"&VTTS_RU_RE_ABBR{k}" for k in range(i, min(i + 6, len(abbr)))) + ","
            for i in range(0, len(abbr), 6)]
    out += ["};", "", "#endif", ""]
    return out


# Words the Polish code writes directly (asserted to occur in the Python sources).
PL_LITERALS = {"MINUS": "minus", "ZERO": "zero", "ZERA": "zera", "JEDNA": "jedna", "JEDNO": "jedno",
               "DWIE": "dwie", "I": "i", "PRZECINEK": "przecinek", "PLUS": "plus", "OD": "od", "DO": "do",
               "ROKU": "roku", "WIEK": "wiek", "WIEKU": "wieku", "SEKUNDA": "sekunda",
               "SEKUNDY": "sekundy", "SEKUND": "sekund", "PROCENT": "procent", "TYSIECZN": "tysięczn"}


def polish_tables() -> list[str]:
    from vtts.frontend import latin, latin_norm
    from vtts.frontend.lexicons import load_words
    from vtts.frontend.phoneme_set import TOKENS_PLEN
    from vtts.frontend.pl import g2p_pl as g
    from vtts.frontend.pl import normalize_pl as npl

    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_slavic_tables.py -- do not edit */",
           "/* Polish front-end tables (token set pl-en): src/vtts/frontend/pl and lexicons/pl. */",
           "#ifndef VTTS_TEXT_PL_TABLES_H", "#define VTTS_TEXT_PL_TABLES_H", "#include <stdint.h>", "",
           '#include "vtts_re.h"', ""]
    block = [t[3:] for t in TOKENS_PLEN[107:]]
    out += ["/* phonemes of the pl-en block: token id = 107 + index */"]
    out += str_list("VTTS_PL_PHONEMES", block)
    out += [f"#define VTTS_PL_FIRST_ID {len(TOKENS_PLEN) - len(block)}", ""]
    out += pairs("VTTS_PL_SIMPLE", g.SIMPLE.items()) + pairs("VTTS_PL_VOWEL_OF", g.VOWEL_OF.items())
    out += pairs("VTTS_PL_SOFTENABLE", g.SOFTENABLE.items()) + pairs("VTTS_PL_VOICED", g.VOICED.items())
    out += pairs("VTTS_PL_NASAL_BEFORE", g.NASAL_BEFORE.items())
    out += str_list("VTTS_PL_NO_DIPHTHONG", g.NO_DIPHTHONG)
    out += str_list("VTTS_PL_UNSTRESSED", sorted(g.UNSTRESSED))
    out += pairs("VTTS_PL_OVERRIDES", sorted(g.override_table().items()))
    out += str_list("VTTS_PL_ANTEPENULT", sorted(g.antepenult_words()))
    assert g.VOWELS == "aeiouyąęó" and "".join(sorted(g.LETTERS)) == "".join(sorted("aąbcćdeęfghijklłmnńoóprsśtuwyzźżqvx"))
    fold = []
    for cp in range(0x110000):
        if 0xD800 <= cp < 0xE000:
            continue
        ch = chr(cp)
        if ch in g.LETTERS or ch in "+-" or ch.lower() != ch:
            continue
        f = g.fold(ch)
        if f:
            fold.append((cp, f))
    out += ["/* fold() of one lower-case character other than the Polish letters and + -: the base letter",
            " * (FOLD, NFKD), sorted by code point */",
            f"static const struct {{ uint32_t cp; const char *to; }} VTTS_PL_FOLD[{len(fold)}] = {{"]
    out += [f"    {{0x{cp:04X}, {c_str(f)}}}," for cp, f in fold]
    out += ["};", f"#define VTTS_PL_N_FOLD {len(fold)}", ""]
    # tagging (latin.latin_word_lang for "pl")
    out += [f"#define VTTS_PL_OWN {c_str(latin.LATIN_PAIRS['pl'])}"]
    out += str_list("VTTS_PL_NATIVE", sorted(load_words("pl", "native")))
    out += str_list("VTTS_PL_TABLE_KEYS", sorted(latin._table_keys("pl")))
    out += str_list("VTTS_PL_FOREIGN", g.FOREIGN)
    # normalizer data
    out += str_list("VTTS_PL_ONES", npl.ONES) + str_list("VTTS_PL_TENS", npl.TENS)
    out += str_list("VTTS_PL_HUNDREDS", npl.HUNDREDS) + str_list("VTTS_PL_ONES_GEN", npl.ONES_GEN)
    out += str_list("VTTS_PL_TENS_GEN", npl.TENS_GEN) + str_list("VTTS_PL_HUNDREDS_GEN", npl.HUNDREDS_GEN)
    exps = {10 ** 12: 12, 10 ** 9: 9, 10 ** 6: 6, 1000: 3}
    out += ["/* SCALES: power of ten, one, few, many, genitive one, genitive many */",
            f"static const struct {{ int exp; const char *one, *few, *many, *gen_one, *gen_many; }} VTTS_PL_SCALES[{len(npl.SCALES)}] = {{"]
    out += [f"    {{{exps[v]}, {c_str(a)}, {c_str(b)}, {c_str(c)}, {c_str(npl.SCALES_GEN[v][0])}, {c_str(npl.SCALES_GEN[v][1])}}},"
            for v, a, b, c in npl.SCALES]
    out += ["};", f"#define VTTS_PL_N_SCALES {len(npl.SCALES)}", ""]
    out += pairs("VTTS_PL_ORD_ONES", npl.ORD_ONES)
    out += str_list("VTTS_PL_ORD_TENS", npl.ORD_TENS) + str_list("VTTS_PL_ORD_HUNDREDS", npl.ORD_HUNDREDS)
    out += str_list("VTTS_PL_CASES", npl.CASES)
    out += [f"static const char *const VTTS_PL_ENDINGS[3][{len(npl.CASES)}] = {{  /* classes h, k, c */"]
    out += ["    {" + ", ".join(c_str(e) for e in npl.ENDINGS[k]) + "}," for k in "hkc"]
    out += ["};", ""]
    src = Path(npl.__file__).read_text(encoding="utf-8")
    prefixes = {1: "", 2: "dwu", 3: "trzy", 4: "cztero", 5: "pięcio", 10: "dziesięcio"}
    assert all(f'{k}: "{v}"' in src for k, v in prefixes.items())
    out += pairs("VTTS_PL_THOUSAND_PREFIX", [(str(k), v) for k, v in prefixes.items()])
    out += str_list("VTTS_PL_MONTHS", npl.MONTHS)
    out += pairs("VTTS_PL_YEAR_NOUN", npl.YEAR_NOUN.items()) + pairs("VTTS_PL_CENTURY_NOUN", npl.CENTURY_NOUN.items())
    out += str_list("VTTS_PL_TIME_OBLIQUE", sorted(npl.TIME_OBLIQUE))
    out += str_list("VTTS_PL_LOC_PREPOSITIONS", sorted(npl.LOC_PREPOSITIONS))
    out += str_list("VTTS_PL_GEN_COUNT", sorted(npl.GEN_COUNT))
    out += pairs("VTTS_PL_LETTERS", npl.LETTERS.items())
    out += str_list("VTTS_PL_ACRONYM_WORDS", sorted(npl.ACRONYM_WORDS)) + str_list("VTTS_PL_SPELLED", sorted(npl.SPELLED))
    table = {**{k[0].upper() + k[1:]: v for k, v in npl.ABBREVIATIONS.items()}, **npl.ABBREVIATIONS}
    abbr = sorted(table, key=len, reverse=True)
    out += pairs("VTTS_PL_ABBREVIATIONS", [(k, table[k]) for k in abbr])
    out += forms_table("VTTS_PL_UNITS", npl.UNITS) + forms_table("VTTS_PL_CURRENCY", npl.CURRENCY)
    out += forms_table("VTTS_PL_SUBUNIT", npl.SUBUNIT)
    out += pairs("VTTS_PL_GEN_SG", npl.GEN_SG.items())
    out += ["/* SCALE_ABBR: key, power of ten */",
            f"static const struct {{ const char *key; int exp; }} VTTS_PL_SCALE_ABBR[{len(npl.SCALE_ABBR)}] = {{"]
    out += [f"    {{{c_str(k)}, {len(str(v)) - 1}}}," for k, v in npl.SCALE_ABBR.items()]
    out += ["};", f"#define VTTS_PL_N_SCALE_ABBR {len(npl.SCALE_ABBR)}", ""]
    out += pairs("VTTS_PL_SYMBOLS", npl.SYMBOLS.items())
    out += ["static const char *const VTTS_PL_FRACTION[4][3] = {"]
    out += ["    {" + ", ".join(c_str(x) for x in f) + "}," for f in npl.FRACTION] + ["};", ""]
    out += [f"#define VTTS_PL_DROP {c_str(latin_norm.DROP)}", ""]
    assert npl.CLITICS == frozenset(("w", "z")) and npl.MARKS == ",.?!;:"
    assert all(v in src for v in PL_LITERALS.values())
    out += [f"#define VTTS_PL_L_{k} {c_str(v)}" for k, v in PL_LITERALS.items()] + [""]
    rt = ReTables("VTTS_PL")
    for name in ("PHONE", "DATE_ISO", "DATE_DMY", "YEAR", "CENTURY", "DAY_MONTH", "TIME", "SCALED",
                 "MONEY_BEFORE", "MONEY_AFTER", "PERCENT", "UNIT", "RANGE", "NUMBER", "ACRONYM"):
        rt.add(name, getattr(npl, name))
    rt.add("PAUSE", latin_norm.PAUSE)
    rt.add("PRODUCT_CODE", latin_norm.PRODUCT_CODE)
    rt.add("WORD", latin_norm.WORD)
    rt.add("THOUSANDS_DOT", r"\d{1,3}(\.\d{3})+(,\d+)?\Z")
    rt.add("THOUSANDS_COMMA", r"\d{1,3}(,\d{3})+(\.\d+)?\Z")
    for k, key in enumerate(abbr):
        rt.add(f"ABBR{k}", r"(?<![\w])" + re.escape(key) + ("" if key.endswith(".") else r"(?![\w])"))
    out += rt.lines()
    out += [f"static const vtts_re *const VTTS_PL_ABBR_RE[{len(abbr)}] = {{"]
    out += ["    " + ", ".join(f"&VTTS_PL_RE_ABBR{k}" for k in range(i, min(i + 6, len(abbr)))) + ","
            for i in range(0, len(abbr), 6)]
    out += ["};", "", "#endif", ""]
    return out


PL_OUT = SRC / "vtts_text_pl_tables.h"


def main() -> None:
    RU_OUT.write_text("\n".join(russian_tables()), encoding="utf-8")
    print(f"wrote {RU_OUT}")
    PL_OUT.write_text("\n".join(polish_tables()), encoding="utf-8")
    print(f"wrote {PL_OUT}")


if __name__ == "__main__":
    main()
