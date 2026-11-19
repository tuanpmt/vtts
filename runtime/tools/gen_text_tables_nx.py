"""Tables of the Dutch, Swedish and Norwegian device front-ends (runtime/src/vtts_text_nx_tables.h),
generated from the Python sources: scan_norm.py with each language's Spec (nl/normalize_nl.py,
sv/normalize_sv.py, no/normalize_no.py), the tagger's word lists (latin.py, lexicons/<lang>/),
g2p_nl.py and scand_g2p.py with the Rules of sv/g2p_sv.py and no/g2p_no.py. Each language's tables
are compiled only with VTTS_ENABLE_<L>. Called by gen_text_tables.py (main)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from vtts.frontend import phoneme_set

NX_OUT = Path(__file__).resolve().parents[1] / "src" / "vtts_text_nx_tables.h"
NX_LANGS = ("nl", "sv", "no")


def c_str(s: str) -> str:
    out = []
    for ch in s:
        if ch in '\\"':
            out.append("\\" + ch)
        elif ch == "?":
            out.append("\\?")  # no trigraphs
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def str_list(name: str, items) -> list[str]:
    items = list(items)
    if not items:
        return [f"static const char *const {name}[1] = {{0}};", ""]
    out = [f"static const char *const {name}[{len(items)}] = {{"]
    out += ["    " + ", ".join(c_str(s) for s in items[i:i + 6]) + "," for i in range(0, len(items), 6)]
    return out + ["};", ""]


def cname(p: str) -> str:
    rep = {":": "L", "@": "AT", "{": "AE", "}": "UU", "`": "R", "'": "T", ",": "SEC", "?": "Q"}
    return "".join(rep.get(ch, ch) for ch in p)


def fold_runs(fold) -> list[tuple[int, int, int, int]]:
    """fold() of every code point >= 0x80 as runs (start, count, first result, step 0/1)."""
    runs: list[list[int]] = []
    for c in range(0x80, 0x110000):
        if 0xD800 <= c < 0xE000:
            continue
        f = fold(chr(c))
        if not f:
            continue
        assert len(f) == 1, (hex(c), f)
        if runs and c == runs[-1][0] + runs[-1][1] and runs[-1][1] < 65535:
            r = runs[-1]
            if r[1] == 1 and ord(f) in (r[2], r[2] + 1):
                r[1], r[3] = 2, ord(f) - r[2]
                continue
            if r[1] > 1 and ord(f) == r[2] + r[1] * r[3]:
                r[1] += 1
                continue
        runs.append([c, 1, ord(f), 0])
    return [tuple(r) for r in runs]


def _spec_tables(code: str, up: str, nm) -> tuple[list[str], str]:
    """Normalizer and tagger tables of one language; returns (lines, spec initializer)."""
    from vtts.frontend import latin
    from vtts.frontend.lexicons import load_words

    sp = nm.spec()
    out: list[str] = []
    assert all(len(k) == 1 for k in sp.letters) and all(len(k) == 1 for k in sp.symbols)

    def pairs(name: str, items) -> list[str]:
        items = list(items)
        r = [f"static const vtts_nx_pair {name}[{max(len(items), 1)}] = {{"]
        r += [f"    {{{c_str(k)}, {c_str(v)}}}," for k, v in items] or ["    {0, 0},"]
        return r + ["};", ""]

    out += str_list(f"VTTS_{up}_DIGITS", sp.digits)
    out += pairs(f"VTTS_{up}_LETTER_NAMES", sp.letters.items())
    out += str_list(f"VTTS_{up}_ACRONYM_WORDS", sorted(sp.acronym_words))
    abbr = sp.sorted_keys("abbreviations")
    out += pairs(f"VTTS_{up}_ABBREV", [(k, sp.abbreviations[k]) for k in abbr])
    units = sp.sorted_keys("units")
    out += [f"static const vtts_nx_unit VTTS_{up}_UNITS[{len(units)}] = {{"]
    out += [f"    {{{c_str(k)}, {c_str(sp.units[k][0])}, {c_str(sp.units[k][1])}}}," for k in units] + ["};", ""]
    cur = sp.sorted_keys("currency")
    out += [f"static const vtts_nx_cur VTTS_{up}_CUR[{len(cur)}] = {{"]
    for k in cur:
        c = sp.currency[k]
        out += [f"    {{{c_str(k)}, {c_str(c.one)}, {c_str(c.many)}, {c_str(c.sub_one)}, {c_str(c.sub_many)}}},"]
    out += ["};", ""]
    before = [cur.index(k) for k in sp.currency_before]
    out += [f"static const uint8_t VTTS_{up}_CUR_BEFORE[{len(before)}] = {{{', '.join(map(str, before))}}};", ""]
    out += pairs(f"VTTS_{up}_SYMBOLS", sp.symbols.items())
    out += str_list(f"VTTS_{up}_MONTHS", sp.months)
    out += str_list(f"VTTS_{up}_ORD_SUFFIXES", sp.ordinal_suffixes)
    out += str_list(f"VTTS_{up}_TIME_AFTER", sp.time_after)
    out += str_list(f"VTTS_{up}_TIME_BEFORE", sp.time_before)
    out += str_list(f"VTTS_{up}_DASH_MONEY", sp.dash_money)
    native = sorted(load_words(code, "native"))
    english = sorted(load_words(code, "english"))
    keys = sorted(latin._table_keys(code))
    out += str_list(f"VTTS_{up}_NATIVE", native) + str_list(f"VTTS_{up}_ENGLISH", english)
    out += str_list(f"VTTS_{up}_TABLE_KEYS", keys)
    n = len
    init = (f"{{{c_str(code)}, VTTS_{up}_DIGITS, {c_str(sp.minus)}, {c_str(sp.comma)}, {c_str(sp.point)},\n"
            f"     {c_str(sp.percent)}, {c_str(sp.permille)}, {c_str(sp.range_word)}, {c_str(sp.plus)}, {c_str(sp.and_word)},\n"
            f"     VTTS_{up}_LETTER_NAMES, {n(sp.letters)}, VTTS_{up}_ACRONYM_WORDS, {n(sp.acronym_words)},\n"
            f"     VTTS_{up}_ABBREV, {n(abbr)}, VTTS_{up}_UNITS, {n(units)}, VTTS_{up}_CUR, {n(cur)},\n"
            f"     VTTS_{up}_CUR_BEFORE, {n(before)}, VTTS_{up}_SYMBOLS, {n(sp.symbols)}, VTTS_{up}_MONTHS,\n"
            f"     VTTS_{up}_ORD_SUFFIXES, {n(sp.ordinal_suffixes)}, {int(sp.ordinal_dot)}, {int(sp.month_ordinal)},\n"
            f"     {int(sp.leading_apostrophe)}, VTTS_{up}_TIME_AFTER, {n(sp.time_after)}, VTTS_{up}_TIME_BEFORE,\n"
            f"     {n(sp.time_before)}, VTTS_{up}_DASH_MONEY, {n(sp.dash_money)}, {cur.index(sp.default_currency)},\n"
            f"     {c_str(latin.LATIN_PAIRS[code])}, VTTS_{up}_NATIVE, {n(native)}, VTTS_{up}_ENGLISH, {n(english)},\n"
            f"     VTTS_{up}_TABLE_KEYS, {n(keys)}}}")
    return out, init


def _tokens(code: str) -> tuple[list[str], dict[str, int]]:
    up = code.upper()
    tset = phoneme_set.TOKEN_SETS[phoneme_set.PAIR_MODES[code]]
    tok0 = phoneme_set.VOCAB_SIZE_V2
    assert all(t.startswith(up + ":") for t in tset[tok0:])
    names = [t.split(":", 1)[1] for t in tset[tok0:]]
    return names, {p: tok0 + k for k, p in enumerate(names)}


def _token_lines(code: str, names: list[str], ids: dict[str, int]) -> list[str]:
    up = code.upper()
    out = [f"#define VTTS_{up}EN_VOCAB {phoneme_set.VOCAB_SIZE_V2 + len(names)}"]
    defs = {}
    for p in names:
        c = f"{up}_{cname(p)}"
        assert c not in defs, c
        defs[c] = ids[p]
        out.append(f"#define {c} {ids[p]}  /* {p} */")
    return out + [""]


def _ids(ph, ids: dict[str, int]) -> str:
    return "{" + ", ".join(str(ids[p]) for p in ph) + "}"


def _fold_lines(up: str, fold, letters) -> list[str]:
    for c in range(0x80):
        want = chr(c).lower() if chr(c).isalpha() else ""
        assert fold(chr(c)) == want, (up, c)
    runs = fold_runs(fold)
    out = [f"static const vtts_nx_fold VTTS_{up}_FOLD[{len(runs)}] = {{"]
    out += ["    " + " ".join(f"{{0x{a:X}, {k}, 0x{f:X}, {s}}}," for a, k, f, s in runs[i:i + 4])
            for i in range(0, len(runs), 4)]
    return out + ["};", f"#define VTTS_{up}_N_FOLD {len(runs)}", ""]


def dutch_tables() -> list[str]:
    from vtts.frontend.nl import g2p_nl as g
    from vtts.frontend.nl import normalize_nl as nm

    names, ids = _tokens("nl")
    out = ["#if VTTS_ENABLE_NL", "/* ---- Dutch (token set nl-en) ---- */"]
    out += _token_lines("nl", names, ids)
    out += str_list("VTTS_NL_TOKEN_NAMES", names)
    stressed = [ids.get(p + "1", 0) for p in names]
    out += [f"static const uint8_t VTTS_NL_STRESSED[{len(names)}] = {{  /* id - 107 -> stressed id (0: none) */"]
    out += ["    " + ", ".join(map(str, stressed[i:i + 16])) + "," for i in range(0, len(stressed), 16)] + ["};"]
    vow = [int(p in g.VOWELS or p.removesuffix("1") in g.VOWELS) for p in names]
    out += [f"static const uint8_t VTTS_NL_IS_VOWEL[{len(names)}] = {{{', '.join(map(str, vow))}}};", ""]
    lines, init = _spec_tables("nl", "NL", nm)
    out += lines + [f"static const vtts_nx_spec VTTS_NL_SPEC = {init};", ""]
    out += str_list("VTTS_NL_ONES", nm.ONES) + str_list("VTTS_NL_TENS", nm.TENS)
    assert [s for s, _ in nm.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6]
    out += str_list("VTTS_NL_SCALES", [x for _, x in nm.SCALES])
    # g2p
    out += [f"#define VTTS_NL_LETTERS {c_str(''.join(sorted(g.LETTERS)))}"]
    out += _fold_lines("NL", g.fold, g.LETTERS)
    out += ["static const struct { const char *g; uint8_t v, glide; } VTTS_NL_VGRAPH[] = {"]
    out += [f"    {{{c_str(s)}, {ids[v]}, {ids[gl] if gl else 0}}}," for s, v, gl in g.VOWEL_GRAPHEMES] + ["};"]
    out += [f"#define VTTS_NL_N_VGRAPH {len(g.VOWEL_GRAPHEMES)}", ""]
    out += [f"#define VTTS_NL_SINGLE_VOWELS {c_str(g.SINGLE_VOWELS)}",
            f"#define VTTS_NL_ACCENTED {c_str(''.join(g.ACCENTED))}",
            f"#define VTTS_NL_ACCENTED_BASE {c_str(''.join(g.ACCENTED.values()))}",
            f"#define VTTS_NL_DIAERESIS {c_str(''.join(g.DIAERESIS))}",
            f"#define VTTS_NL_DIAERESIS_BASE {c_str(''.join(g.DIAERESIS.values()))}",
            f"#define VTTS_NL_OBSTRUENTS {c_str(''.join(sorted(g.OBSTRUENTS)))}",
            f"#define VTTS_NL_LIQUIDS {c_str(''.join(sorted(g.LIQUIDS)))}",
            f"#define VTTS_NL_FRONT {c_str(''.join(sorted(g.FRONT)))}", ""]
    out += ["static const struct { const char *g; uint8_t ph[2], n; } VTTS_NL_CGRAPH[] = {"]
    out += [f"    {{{c_str(s)}, {{{', '.join(str(ids[x]) for x in ph)}{', 0' * (2 - len(ph))}}}, {len(ph)}}},"
            for s, ph in g.CONSONANT_GRAPHEMES] + ["};", f"#define VTTS_NL_N_CGRAPH {len(g.CONSONANT_GRAPHEMES)}", ""]
    out += str_list("VTTS_NL_CLOSING", sorted(g.CLOSING))
    out += ["static const struct { uint32_t c; uint8_t id; } VTTS_NL_SINGLE[] = {"]
    out += [f"    {{0x{ord(k):X}, {ids[v]}}}," for k, v in g.SINGLE.items()] + ["};", f"#define VTTS_NL_N_SINGLE {len(g.SINGLE)}"]
    out += [f"static const uint8_t VTTS_NL_VOICELESS[] = {{{', '.join(str(ids[p]) for p in sorted(g.VOICELESS))}}};",
            f"#define VTTS_NL_N_VOICELESS {len(g.VOICELESS)}"]
    out += ["static const uint8_t VTTS_NL_DEVOICE[][2] = {" + " ".join(f"{{{ids[a]}, {ids[b]}}}," for a, b in g.DEVOICE.items()) + "};",
            f"#define VTTS_NL_N_DEVOICE {len(g.DEVOICE)}"]
    assert list(g.LONG) == list(g.SHORT)
    out += [f"#define VTTS_NL_LS_LETTERS {c_str(''.join(g.LONG))}",
            f"static const uint8_t VTTS_NL_LONG[] = {{{', '.join(str(ids[v]) for v in g.LONG.values())}}};",
            f"static const uint8_t VTTS_NL_SHORT[] = {{{', '.join(str(ids[v]) for v in g.SHORT.values())}}};", ""]
    out += ["static const struct { const char *p; uint8_t ph[3], n; } VTTS_NL_PREFIXES[] = {"]
    out += [f"    {{{c_str(p)}, {{{', '.join(str(ids[x]) for x in ph)}{', 0' * (3 - len(ph))}}}, {len(ph)}}},"
            for p, ph in g.PREFIXES] + ["};", f"#define VTTS_NL_N_PREFIXES {len(g.PREFIXES)}", ""]
    out += str_list("VTTS_NL_NOT_PREFIX", g.NOT_PREFIX) + [f"#define VTTS_NL_N_NOT_PREFIX {len(g.NOT_PREFIX)}"]
    out += str_list("VTTS_NL_NOT_PREFIX_ENDINGS", g.NOT_PREFIX_ENDINGS)
    out += [f"#define VTTS_NL_N_NOT_PREFIX_ENDINGS {len(g.NOT_PREFIX_ENDINGS)}"]
    out += str_list("VTTS_NL_ONSETS", sorted(g.ONSETS)) + [f"#define VTTS_NL_N_ONSETS {len(g.ONSETS)}"]
    out += ["static const struct { const char *e; uint8_t off; } VTTS_NL_STRESSED_ENDINGS[] = {"]
    out += [f"    {{{c_str(e)}, {o}}}," for e, o in g.STRESSED_ENDINGS] + ["};"]
    out += [f"#define VTTS_NL_N_STRESSED_ENDINGS {len(g.STRESSED_ENDINGS)}"]
    for nm_, items in (("EER_FORMS", g.EER_FORMS), ("UNSTRESSED_ENT", g.UNSTRESSED_ENT),
                       ("INFLECTIONS", g.INFLECTIONS), ("PRESTRESS_ENDINGS", g.PRESTRESS_ENDINGS),
                       ("NUMBER_MORPHS", g.NUMBER_MORPHS)):
        out += str_list(f"VTTS_NL_{nm_}", items) + [f"#define VTTS_NL_N_{nm_} {len(items)}"]
    for nm_, items in (("FUNCTION_WORDS", g.FUNCTION_WORDS), ("CH_S", g.CH_S), ("SCHWA_CODAS", g.SCHWA_CODAS)):
        out += str_list(f"VTTS_NL_{nm_}", sorted(items)) + [f"#define VTTS_NL_N_{nm_} {len(items)}"]
    out += ["static const struct { const char *m; uint8_t ph[3], n; } VTTS_NL_NUMBER_READINGS[] = {"]
    out += [f"    {{{c_str(m)}, {{{', '.join(str(ids[x]) for x in ph)}{', 0' * (3 - len(ph))}}}, {len(ph)}}},"
            for m, ph in g.NUMBER_READINGS.items()] + ["};", f"#define VTTS_NL_N_NUMBER_READINGS {len(g.NUMBER_READINGS)}", ""]
    ovr = g.override_table()
    keys = sorted(ovr)
    assert max(len(v) for v in ovr.values()) <= 16
    out += ["static const vtts_nx_entry VTTS_NL_OVERRIDES[] = {  /* sorted */"]
    out += [f"    {{{c_str(k)}, {len(ovr[k])}, {_ids(ovr[k], ids)}}}," for k in keys]
    out += ["};", f"#define VTTS_NL_N_OVERRIDES {len(keys)}", ""]
    from vtts.frontend.nl import g2p_nl
    out += str_list("VTTS_NL_FOREIGN", g2p_nl.FOREIGN) + [f"#define VTTS_NL_N_FOREIGN {len(g2p_nl.FOREIGN)}"]
    out += str_list("VTTS_NL_FOREIGN_START", g2p_nl.FOREIGN_START)
    out += [f"#define VTTS_NL_N_FOREIGN_START {len(g2p_nl.FOREIGN_START)}"]
    out += str_list("VTTS_NL_FOREIGN_END", g2p_nl.FOREIGN_END) + [f"#define VTTS_NL_N_FOREIGN_END {len(g2p_nl.FOREIGN_END)}"]
    return out + ["#endif /* VTTS_ENABLE_NL */", ""]


def scand_tables(code: str) -> list[str]:
    import importlib

    g = importlib.import_module(f"vtts.frontend.{code}.g2p_{code}")
    nm = importlib.import_module(f"vtts.frontend.{code}.normalize_{code}")
    up = code.upper()
    r = g.RULES
    names, ids = _tokens(code)
    out = [f"#if VTTS_ENABLE_{up}", f"/* ---- {code} (token set {code}-en) ---- */"]
    out += _token_lines(code, names, ids)
    out += str_list(f"VTTS_{up}_TOKEN_NAMES", names)
    vow = [int(p[0] in "aeiouyAEIOUY@9}{28") for p in names]
    out += [f"static const uint8_t VTTS_{up}_IS_VOWEL[{len(names)}] = {{{', '.join(map(str, vow))}}};", ""]
    lines, init = _spec_tables(code, up, nm)
    out += lines + [f"static const vtts_nx_spec VTTS_{up}_SPEC = {init};", ""]
    out += str_list(f"VTTS_{up}_ONES", nm.ONES) + str_list(f"VTTS_{up}_TENS", nm.TENS)
    out += str_list(f"VTTS_{up}_ORD", nm.ORD)
    assert [s for s, _, _ in nm.SCALES] == [10 ** 12, 10 ** 9, 10 ** 6]
    out += [f"static const char *const VTTS_{up}_SCALES[3][2] = {{"]
    out += [f"    {{{c_str(a)}, {c_str(b)}}}," for _, a, b in nm.SCALES] + ["};", ""]
    out += [f"#define VTTS_{up}_LETTERS {c_str(''.join(sorted(g.LETTERS)))}"]
    out += _fold_lines(up, g.fold, g.LETTERS)

    def phs(ph):
        assert len(ph) <= 3
        return "{" + ", ".join(str(ids[p]) for p in ph) + ", 0" * (3 - len(ph)) + "}"

    def groups(name, items):
        res = [f"static const vtts_nx_group {name}[{max(len(items), 1)}] = {{"]
        res += [f"    {{{c_str(s)}, {phs(ph)}, {len(ph)}}}," for s, ph in items] or ["    {0, {0, 0, 0}, 0},"]
        return res + ["};", ""]

    vl = list(r.long)
    assert list(r.short) == vl
    out += [f"static const char *const VTTS_{up}_VOWELS = {c_str(r.vowels)};"]
    out += str_list(f"VTTS_{up}_FRONT", r.front)
    out += [f"static const char *const VTTS_{up}_LS_LETTERS = {c_str(''.join(vl))};",
            f"static const uint8_t VTTS_{up}_LONG[] = {{{', '.join(str(ids[r.long[v]]) for v in vl)}}};",
            f"static const uint8_t VTTS_{up}_SHORT[] = {{{', '.join(str(ids[r.short[v]]) for v in vl)}}};"]
    br = list(r.before_r)
    out += [f"static const char *const VTTS_{up}_BEFORE_R_LETTERS = {c_str(''.join(br))};",
            f"static const uint8_t VTTS_{up}_BEFORE_R[][2] = {{" + " ".join(
                f"{{{ids[r.before_r[v][0]]}, {ids[r.before_r[v][1]]}}}," for v in br) + "};"]
    ul = list(r.unstressed)
    out += [f"static const char *const VTTS_{up}_UNSTRESSED_LETTERS = {c_str(''.join(ul))};",
            f"static const uint8_t VTTS_{up}_UNSTRESSED[] = {{{', '.join(str(ids[r.unstressed[v]]) for v in ul) or '0'}}};", ""]
    out += groups(f"VTTS_{up}_DIPHTHONGS", [(s, (t,)) for s, t in r.diphthongs])
    out += groups(f"VTTS_{up}_GRAPHEMES", r.graphemes) + groups(f"VTTS_{up}_INITIAL", r.initial)
    out += groups(f"VTTS_{up}_SOFT", r.soft) + groups(f"VTTS_{up}_PREFIXES", r.prefixes)
    out += [f"static const vtts_nx_single VTTS_{up}_SINGLE[] = {{"]
    out += [f"    {{0x{ord(k):X}, {ids[v]}}}," for k, v in r.single.items()] + ["};"]
    out += str_list(f"VTTS_{up}_NOT_PREFIX", r.not_prefix) + str_list(f"VTTS_{up}_ONSETS", sorted(r.onsets))
    out += [f"static const vtts_nx_ending VTTS_{up}_STRESSED_ENDINGS[] = {{"]
    out += [f"    {{{c_str(e)}, {o}}}," for e, o in r.stressed_endings] + ["};"]
    for nm_, items in (("INFLECTIONS", r.inflections), ("PRESTRESS", r.prestress), ("ACUTE", r.acute_endings),
                       ("SECONDARY", r.secondary), ("SCHWA", r.schwa_endings), ("SILENT", r.silent)):
        out += str_list(f"VTTS_{up}_{nm_}", items)
    out += str_list(f"VTTS_{up}_FUNCTION_WORDS", sorted(r.function_words))
    morphs = list(r.number_morphs)
    mx = max(len(v) for v in r.number_morphs.values())
    assert mx <= 16
    out += [f"static const vtts_nx_entry VTTS_{up}_MORPHS[] = {{  /* in order */"]
    out += [f"    {{{c_str(m)}, {len(r.number_morphs[m])}, {_ids(r.number_morphs[m], ids)}}}," for m in morphs] + ["};"]
    ovr = g.override_table()
    keys = sorted(ovr)
    assert max(len(v) for v in ovr.values()) <= 16
    out += [f"static const vtts_nx_entry VTTS_{up}_OVERRIDES[] = {{  /* sorted */"]
    out += [f"    {{{c_str(k)}, {len(ovr[k])}, {_ids(ovr[k], ids)}}}," for k in keys] + ["};", ""]
    out += str_list(f"VTTS_{up}_FOREIGN", g.FOREIGN)
    out += str_list(f"VTTS_{up}_FOREIGN_START", g.FOREIGN_START) + [f"#define VTTS_{up}_N_FOREIGN_START {len(g.FOREIGN_START)}"]
    out += str_list(f"VTTS_{up}_FOREIGN_END", g.FOREIGN_END) + [f"#define VTTS_{up}_N_FOREIGN_END {len(g.FOREIGN_END)}"]
    n = len
    out += [f"static const vtts_nx_rules VTTS_{up}_RULES = {{",
            f"    VTTS_{up}_VOWELS, VTTS_{up}_FRONT, {n(r.front)}, {c_str(r.front_c)}, VTTS_{up}_LS_LETTERS,",
            f"    VTTS_{up}_LONG, VTTS_{up}_SHORT, VTTS_{up}_BEFORE_R_LETTERS, VTTS_{up}_BEFORE_R, {c_str(r.before_r_coda)},",
            f"    VTTS_{up}_UNSTRESSED_LETTERS, VTTS_{up}_UNSTRESSED, VTTS_{up}_DIPHTHONGS, {n(r.diphthongs)},",
            f"    VTTS_{up}_GRAPHEMES, {n(r.graphemes)}, VTTS_{up}_INITIAL, {n(r.initial)}, VTTS_{up}_SOFT, {n(r.soft)},",
            f"    VTTS_{up}_PREFIXES, {n(r.prefixes)}, VTTS_{up}_NOT_PREFIX, {n(r.not_prefix)}, VTTS_{up}_ONSETS,",
            f"    {n(r.onsets)}, VTTS_{up}_INFLECTIONS, {n(r.inflections)}, VTTS_{up}_PRESTRESS, {n(r.prestress)},",
            f"    VTTS_{up}_ACUTE, {n(r.acute_endings)}, VTTS_{up}_SECONDARY, {n(r.secondary)}, VTTS_{up}_SCHWA,",
            f"    {n(r.schwa_endings)}, VTTS_{up}_FUNCTION_WORDS, {n(r.function_words)}, VTTS_{up}_SILENT, {n(r.silent)},",
            f"    {int(r.final_g_j)}, VTTS_{up}_STRESSED_ENDINGS, {n(r.stressed_endings)}, VTTS_{up}_MORPHS, {n(morphs)},",
            f"    VTTS_{up}_OVERRIDES, {n(keys)}, VTTS_{up}_SINGLE, {n(r.single)}, VTTS_{up}_FOREIGN, {n(g.FOREIGN)},",
            f"    {up}_T1, {up}_T2, {up}_SEC, {up}_AT, {up}_r, VTTS_{up}_IS_VOWEL}};", ""]
    retro = {p: ids[p + "`"] for p in "tdnsl"}
    out += [f"static const uint8_t VTTS_{up}_RETRO[][2] = {{" + " ".join(f"{{{ids[p]}, {v}}}," for p, v in retro.items()) + "};", ""]
    return out + [f"#endif /* VTTS_ENABLE_{up} */", ""]


def nx_tables() -> list[str]:
    out = ["/* SPDX-License-Identifier: Apache-2.0 */",
           "/* generated by runtime/tools/gen_text_tables.py (gen_text_tables_nx.py) -- do not edit */",
           "/* Dutch, Swedish and Norwegian front-end tables: src/vtts/frontend/scan_norm.py, nl/, sv/, no/,",
           " * scand_g2p.py and lexicons/nl, sv, no. Each language only with VTTS_ENABLE_<L>. */",
           "#ifndef VTTS_TEXT_NX_TABLES_H", "#define VTTS_TEXT_NX_TABLES_H", "#include <stdint.h>",
           '#include "vtts_text_nx_int.h"', "",
           "typedef struct { const char *key, *val; } vtts_nx_pair;",
           "typedef struct { const char *key, *one, *many; } vtts_nx_unit;",
           "typedef struct { const char *key, *one, *many, *sub_one, *sub_many; } vtts_nx_cur;",
           "typedef struct { uint32_t start; uint16_t count; uint32_t first; uint8_t step; } vtts_nx_fold;",
           "typedef struct { const char *g; uint8_t ph[3], n; } vtts_nx_group;",
           "typedef struct { const char *e; uint8_t off; } vtts_nx_ending;",
           "typedef struct { const char *w; uint8_t n, ph[16]; } vtts_nx_entry;",
           "typedef struct { uint32_t c; uint8_t id; } vtts_nx_single;",
           "typedef struct {",
           "    const char *code;",
           "    const char *const *digits;",
           "    const char *minus, *comma, *point, *percent, *permille, *range, *plus, *and_w;",
           "    const vtts_nx_pair *letters; int n_letters;",
           "    const char *const *acronym_words; int n_acronym_words;   /* sorted */",
           "    const vtts_nx_pair *abbrev; int n_abbrev;                /* longest first */",
           "    const vtts_nx_unit *units; int n_units;                  /* longest first */",
           "    const vtts_nx_cur *cur; int n_cur;                       /* longest first */",
           "    const uint8_t *cur_before; int n_cur_before;             /* indices into cur, in order */",
           "    const vtts_nx_pair *symbols; int n_symbols;",
           "    const char *const *months;",
           "    const char *const *ord_suffixes; int n_ord_suffixes;",
           "    int ordinal_dot, month_ordinal, leading_apostrophe;",
           "    const char *const *time_after; int n_time_after;",
           "    const char *const *time_before; int n_time_before;",
           "    const char *const *dash_money; int n_dash_money;",
           "    int default_cur;",
           "    const char *own;                                         /* LATIN_PAIRS letters */",
           "    const char *const *native; int n_native;                 /* sorted */",
           "    const char *const *english; int n_english;               /* sorted */",
           "    const char *const *table_keys; int n_table_keys;         /* sorted */",
           "} vtts_nx_spec;",
           "typedef struct {",
           "    const char *vowels; const char *const *front; int n_front; const char *front_c;",
           "    const char *ls_letters; const uint8_t *long_v, *short_v;",
           "    const char *before_r_letters; const uint8_t (*before_r)[2]; const char *before_r_coda;",
           "    const char *unstressed_letters; const uint8_t *unstressed;",
           "    const vtts_nx_group *diphthongs; int n_diphthongs;",
           "    const vtts_nx_group *graphemes; int n_graphemes;",
           "    const vtts_nx_group *initial; int n_initial;",
           "    const vtts_nx_group *soft; int n_soft;",
           "    const vtts_nx_group *prefixes; int n_prefixes;",
           "    const char *const *not_prefix; int n_not_prefix;",
           "    const char *const *onsets; int n_onsets;",
           "    const char *const *inflections; int n_inflections;",
           "    const char *const *prestress; int n_prestress;",
           "    const char *const *acute; int n_acute;",
           "    const char *const *secondary; int n_secondary;",
           "    const char *const *schwa; int n_schwa;",
           "    const char *const *function_words; int n_function_words;",
           "    const char *const *silent; int n_silent;",
           "    int final_g_j;",
           "    const vtts_nx_ending *stressed_endings; int n_stressed_endings;",
           "    const vtts_nx_entry *morphs; int n_morphs;",
           "    const vtts_nx_entry *overrides; int n_overrides;          /* sorted */",
           "    const vtts_nx_single *single; int n_single;",
           "    const char *const *foreign; int n_foreign;",
           "    uint8_t tone1, tone2, sec, schwa_id, r_id; const uint8_t *is_vowel;",
           "} vtts_nx_rules;", ""]
    out += dutch_tables()
    for code in ("sv", "no"):
        if code in NX_LANGS and code in phoneme_set.PAIR_MODES:
            out += scand_tables(code)
    out += ["#endif", ""]
    return out


def write() -> None:
    NX_OUT.write_text("\n".join(nx_tables()), encoding="utf-8")
    print(f"wrote {NX_OUT}")


if __name__ == "__main__":
    write()
    _ = unicodedata
