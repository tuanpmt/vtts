/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_text.c -- device front-end (see vtts_text.h). Mirrors src/vtts/frontend (Python). */
#include "vtts_text.h"

#include <string.h>

#include "vtts_text_tables.h"

#define MAX_SYL 40
#define WORD_CAP 64 /* letters per word */

/* ---------------- letters ---------------- */

typedef struct {
    char code[WORD_CAP]; /* internal codes: a..z, 1=ă 2=â 3=ê 4=ô 5=ơ 6=ư 7=đ */
    int n, tone, valid, foreign;
} letters_t;

static const vtts_letter *find_letter(uint32_t cp) {
    int lo = 0, hi = VTTS_N_LETTERS - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (VTTS_LETTERS[mid].cp == cp) return &VTTS_LETTERS[mid];
        if (VTTS_LETTERS[mid].cp < cp) lo = mid + 1; else hi = mid - 1;
    }
    return NULL;
}

static int tone_mark(uint32_t cp) {
    switch (cp) {
    case 0x0300: return 2;
    case 0x0301: return 3;
    case 0x0309: return 4;
    case 0x0303: return 5;
    case 0x0323: return 6;
    default: return 0;
    }
}

static int quality_mark(uint32_t cp) { return cp == 0x0302 || cp == 0x0306 || cp == 0x031B; }

/* Latin letters outside Vietnamese, folded to their ASCII base (spelled, never a syllable) */
static char fold_foreign(uint32_t cp) {
    static const char *const map[] = {
        /* 0xC0 */ "AAAAAAACEEEEIIII", "DNOOOOO*OUUUUYTs", "aaaaaaaceeeeiiii", "dnooooo/ouuuuyty"};
    if (cp >= 0xC0 && cp <= 0xFF) {
        char c = map[(cp - 0xC0) / 16][(cp - 0xC0) % 16];
        if (c == '*' || c == '/') return 0;
        return (char)(c >= 'A' && c <= 'Z' ? c + 32 : c);
    }
    return 0;
}

static int is_combining(uint32_t cp) { return cp >= 0x0300 && cp <= 0x036F; }

/* non-Latin alphabets: join words but produce nothing (Python drops them when spelling) */
static int is_other_alpha(uint32_t cp) {
    return (cp >= 0x0370 && cp <= 0x052F) || (cp >= 0x3040 && cp <= 0x30FF) ||
           (cp >= 0x3400 && cp <= 0x9FFF) || (cp >= 0xAC00 && cp <= 0xD7AF) ||
           (cp >= 0x0100 && cp <= 0x024F);
}

static int is_letter_cp(uint32_t cp) {
    if ((cp >= 'a' && cp <= 'z') || (cp >= 'A' && cp <= 'Z')) return 1;
    if (cp < 0x80) return 0;
    return find_letter(cp) || fold_foreign(cp) || is_other_alpha(cp);
}

static int is_digit_cp(uint32_t cp) { return cp >= '0' && cp <= '9'; }
static int is_space_cp(uint32_t cp) {
    return cp == ' ' || (cp >= 0x09 && cp <= 0x0D) || cp == 0xA0 || cp == 0x1680 ||
           (cp >= 0x2000 && cp <= 0x200A) || cp == 0x2028 || cp == 0x2029 || cp == 0x202F ||
           cp == 0x205F || cp == 0x3000;
}
static int is_word_cp(uint32_t cp) { return is_letter_cp(cp) || is_digit_cp(cp) || cp == '_'; }
int vtts_cp_is_word(uint32_t cp) { return is_word_cp(cp); } /* Python \w, for vtts_text_en.c */
int vtts_cp_is_space(uint32_t cp) { return is_space_cp(cp); }

/* ---------------- UTF-8 ---------------- */

static int utf8_decode(const char *s, uint32_t *out, int cap) {
    const unsigned char *p = (const unsigned char *)s;
    int n = 0;
    while (*p && n < cap) {
        uint32_t c = *p;
        int extra = c < 0x80 ? 0 : (c >> 5) == 6 ? 1 : (c >> 4) == 14 ? 2 : (c >> 3) == 30 ? 3 : -1;
        if (extra < 0) { p++; continue; }
        if (extra) c &= (uint32_t)(0x3F >> extra);
        p++;
        int ok = 1;
        for (int k = 0; k < extra; k++) {
            if ((*p & 0xC0) != 0x80) { ok = 0; break; }
            c = (c << 6) | (*p++ & 0x3F);
        }
        if (ok) out[n++] = c;
    }
    return n;
}

static int utf8_encode(uint32_t c, char *o) {
    if (c < 0x80) { o[0] = (char)c; return 1; }
    if (c < 0x800) { o[0] = (char)(0xC0 | (c >> 6)); o[1] = (char)(0x80 | (c & 0x3F)); return 2; }
    if (c < 0x10000) {
        o[0] = (char)(0xE0 | (c >> 12)); o[1] = (char)(0x80 | ((c >> 6) & 0x3F));
        o[2] = (char)(0x80 | (c & 0x3F)); return 3;
    }
    o[0] = (char)(0xF0 | (c >> 18)); o[1] = (char)(0x80 | ((c >> 12) & 0x3F));
    o[2] = (char)(0x80 | ((c >> 6) & 0x3F)); o[3] = (char)(0x80 | (c & 0x3F)); return 4;
}

/* code points of one word -> letters (tone separated, quality marks merged) */
static void to_letters(const uint32_t *cp, int n, letters_t *L) {
    memset(L, 0, sizeof(*L));
    L->tone = 1;
    L->valid = 1;
    for (int i = 0; i < n; i++) {
        uint32_t c = cp[i];
        int t = tone_mark(c);
        if (t) {
            if (L->tone != 1) L->valid = 0;
            L->tone = t;
            continue;
        }
        if (quality_mark(c)) {
            char *last = L->n ? &L->code[L->n - 1] : NULL;
            if (!last) { L->valid = 0; continue; }
            if (c == 0x0302 && *last == 'a') *last = '2';
            else if (c == 0x0306 && *last == 'a') *last = '1';
            else if (c == 0x0302 && *last == 'e') *last = '3';
            else if (c == 0x0302 && *last == 'o') *last = '4';
            else if (c == 0x031B && *last == 'o') *last = '5';
            else if (c == 0x031B && *last == 'u') *last = '6';
            else L->valid = 0;
            continue;
        }
        if (is_combining(c)) { L->valid = 0; continue; }
        const vtts_letter *v = find_letter(c);
        char code;
        int tone = 1;
        if (v) { code = v->code; tone = v->tone; }
        else if (c < 0x80 && ((c | 32) >= 'a' && (c | 32) <= 'z')) code = (char)(c | 32);
        else if ((code = fold_foreign(c)) != 0) L->foreign = 1;
        else { L->foreign = 1; L->valid = 0; continue; } /* non-Latin letter: dropped */
        if (tone != 1) {
            if (L->tone != 1) L->valid = 0;
            L->tone = tone;
        }
        if (L->n < WORD_CAP) L->code[L->n++] = code;
    }
    if (L->foreign) L->valid = 0;
}

/* ---------------- syllable parse (mirrors syllable.py) ---------------- */

typedef struct { const char *onset; int glide; const char *nucleus; const char *coda; int tone; } syl_t;

static int is_vowel(char c) { return c && strchr("a12e3io45u6y", c) != NULL; }

static const char *const ONSET_KEYS[][2] = {
    {"ngh", "ng"}, {"ng", "ng"}, {"gh", "g"}, {"gi", "gi"}, {"ch", "ch"}, {"tr", "tr"}, {"th", "th"},
    {"ph", "ph"}, {"kh", "kh"}, {"nh", "nh"}, {"b", "b"}, {"c", "k"}, {"k", "k"}, {"d", "d"},
    {"7", "đ"}, {"g", "g"}, {"h", "h"}, {"l", "l"}, {"m", "m"}, {"n", "n"}, {"p", "p"}, {"r", "r"},
    {"s", "s"}, {"t", "t"}, {"v", "v"}, {"x", "x"}, {"f", "ph"}, {"w", "v"}, {"z", "d"}, {"j", "gi"}};

static const char *onset_of(const char *head, size_t len) {
    for (size_t k = 0; k < sizeof(ONSET_KEYS) / sizeof(ONSET_KEYS[0]); k++)
        if (strlen(ONSET_KEYS[k][0]) == len && memcmp(ONSET_KEYS[k][0], head, len) == 0) return ONSET_KEYS[k][1];
    return NULL;
}

typedef struct { const char *key, *nucleus, *off; int open_only; } cluster_t;

static const cluster_t CLUSTERS[] = {
    {"a", "a", 0, 0}, {"1", "ă", 0, 0}, {"2", "â", 0, 0}, {"e", "e", 0, 0}, {"3", "ê", 0, 0},
    {"i", "i", 0, 0}, {"y", "i", 0, 0}, {"o", "o", 0, 0}, {"4", "ô", 0, 0}, {"5", "ơ", 0, 0},
    {"u", "u", 0, 0}, {"6", "ư", 0, 0}, {"oo", "oo", 0, 0}, {"44", "ô", 0, 0},
    {"i3", "iê", 0, 0}, {"y3", "iê", 0, 0}, {"ia", "iê", 0, 1}, {"ya", "iê", 0, 1},
    {"u4", "uô", 0, 0}, {"ua", "uô", 0, 1}, {"65", "ươ", 0, 0}, {"6a", "ươ", 0, 1},
    {"ai", "a", "j", 1}, {"ay", "ă", "j", 1}, {"2y", "â", "j", 1}, {"ao", "a", "w", 1},
    {"au", "ă", "w", 1}, {"2u", "â", "w", 1}, {"eo", "e", "w", 1}, {"3u", "ê", "w", 1},
    {"iu", "i", "w", 1}, {"yu", "i", "w", 1}, {"oi", "o", "j", 1}, {"4i", "ô", "j", 1},
    {"5i", "ơ", "j", 1}, {"ui", "u", "j", 1}, {"6i", "ư", "j", 1}, {"6u", "ư", "w", 1},
    {"i3u", "iê", "w", 1}, {"y3u", "iê", "w", 1}, {"65i", "ươ", "j", 1}, {"65u", "ươ", "w", 1},
    {"u4i", "uô", "j", 1}};

static int parse_syl(const letters_t *L, syl_t *s) {
    if (!L->valid || L->n == 0) return 0;
    char base[WORD_CAP + 2];
    memcpy(base, L->code, (size_t)L->n);
    base[L->n] = 0;
    int n = L->n;
    const char *onset = NULL;
    int glide = 0;
    char rest[WORD_CAP + 2];
    if (n > 2 && base[0] == 'q' && base[1] == 'u') {
        onset = "k"; glide = 1; strcpy(rest, base + 2);
    } else {
        strcpy(rest, base);
        for (int size = 3; size >= 1; size--) {
            if (size > n) continue;
            const char *o = onset_of(base, (size_t)size);
            int gi_alone = size == 2 && memcmp(base, "gi", 2) == 0 && n == 2;
            if (!o || !(n > size || gi_alone)) continue;
            char r[WORD_CAP + 2];
            strcpy(r, base + size);
            if (size == 2 && memcmp(base, "gi", 2) == 0) {
                int any_vowel = 0;
                for (const char *c = r; *c; c++) any_vowel |= is_vowel(*c);
                if (!any_vowel || r[0] == '3') { memmove(r + 1, r, strlen(r) + 1); r[0] = 'i'; }
            }
            if (is_vowel(r[0])) { onset = o; strcpy(rest, r); break; }
        }
        size_t rl = strlen(rest);
        if (rl >= 2 && ((rest[0] == 'o' && strchr("a1e", rest[1])) || (rest[0] == 'u' && strchr("3y25", rest[1])))) {
            glide = 1;
            memmove(rest, rest + 1, rl);
        }
    }
    static const char *const CODAS[][2] = {{"ng", "ng"}, {"nh", "nh"}, {"ch", "ch"}, {"c", "c"},
                                           {"m", "m"}, {"n", "n"}, {"p", "p"}, {"t", "t"}};
    const char *coda = NULL;
    size_t rl = strlen(rest);
    for (size_t k = 0; k < 8; k++) {
        size_t cl = strlen(CODAS[k][0]);
        if (rl > cl && memcmp(rest + rl - cl, CODAS[k][0], cl) == 0) {
            coda = CODAS[k][1];
            rest[rl - cl] = 0;
            break;
        }
    }
    const cluster_t *cl = NULL;
    for (size_t k = 0; k < sizeof(CLUSTERS) / sizeof(CLUSTERS[0]); k++)
        if (strcmp(CLUSTERS[k].key, rest) == 0) { cl = &CLUSTERS[k]; break; }
    if (!cl) return 0;
    if (cl->off || cl->open_only) {
        if (coda) return 0;
        if (cl->off) coda = cl->off;
    }
    s->onset = onset; s->glide = glide; s->nucleus = cl->nucleus; s->coda = coda; s->tone = L->tone;
    return 1;
}

/* ---------------- tokens ---------------- */

static int token_id(const char *prefix, const char *name) {
    char buf[16];
    size_t pl = strlen(prefix), nl = strlen(name);
    if (pl + nl >= sizeof buf) return -1;
    memcpy(buf, prefix, pl);
    memcpy(buf + pl, name, nl + 1);
    for (int i = 0; i < VTTS_N_TOKENS; i++) if (strcmp(VTTS_TOKENS[i], buf) == 0) return i;
    return -1;
}

static int is_punct_word(const char *w) {
    return w[1] == 0 && strchr(",.?!;:", w[0]) != NULL;
}

/* ---------------- normalized word buffer ---------------- */

typedef struct {
    vtts_text_ws *ws;
    vtts_ids_cb cb;
    void *user;
    int chunks, stop;
    int collect; /* v2: only collect normalized words (the caller assembles chunks) */
} ctx_t;

static void emit_sentence(ctx_t *c);

static const char *last_word(vtts_text_ws *ws) {
    return ws->n_words ? ws->words + ws->word_off[ws->n_words - 1] : NULL;
}

static void push_raw(ctx_t *c, const char *w) {
    vtts_text_ws *ws = c->ws;
    size_t len = strlen(w);
    if (ws->n_words >= VTTS_TEXT_MAX_WORDS || ws->words_used + (int)len + 1 > VTTS_TEXT_WORD_BYTES) {
        if (c->collect) return; /* v2: drop the rest of an oversized run (pathological input) */
        emit_sentence(c); /* overflow: flush early (only for pathological input) */
    }
    ws->word_off[ws->n_words++] = ws->words_used;
    memcpy(ws->words + ws->words_used, w, len + 1);
    ws->words_used += (int)len + 1;
}

/* append a normalized item: punctuation dedup like normalize(), terminators end a sentence */
static void push_word(ctx_t *c, const char *w) {
    if (is_punct_word(w)) {
        const char *lw = last_word(c->ws);
        if (!lw || is_punct_word(lw)) {
            /* leading or repeated punctuation is dropped; but a terminator after a flushed
             * sentence also lands here and is correctly dropped */
            return;
        }
        push_raw(c, w);
        if (!c->collect && strchr(".!?;", w[0])) emit_sentence(c);
        return;
    }
    push_raw(c, w);
}

/* push a space-separated phrase of words */
static void push_phrase(ctx_t *c, const char *p) {
    char w[96];
    while (*p) {
        while (*p == ' ') p++;
        size_t n = strcspn(p, " ");
        if (!n) break;
        if (n >= sizeof w) n = sizeof w - 1;
        memcpy(w, p, n);
        w[n] = 0;
        push_word(c, w);
        p += n;
    }
}

/* ---------------- numbers (mirrors numbers.py) ---------------- */

static const char *const DIGITS[10] = {"không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"};

static void read_digits(ctx_t *c, const char *d, size_t n) {
    for (size_t i = 0; i < n; i++) push_word(c, DIGITS[d[i] - '0']);
}

static void read_group(ctx_t *c, int v, int leading, int *said) {
    int h = v / 100, t = v / 10 % 10, u = v % 10;
    int words = 0;
    if (h || !leading) { push_word(c, DIGITS[h]); push_word(c, "trăm"); words = 1; }
    if (t == 0) {
        if (u) { if (words) push_word(c, "linh"); push_word(c, DIGITS[u]); }
    } else if (t == 1) {
        push_word(c, "mười");
        if (u) push_word(c, u == 5 ? "lăm" : DIGITS[u]);
    } else {
        push_word(c, DIGITS[t]);
        push_word(c, "mươi");
        if (u) push_word(c, u == 1 ? "mốt" : u == 4 ? "tư" : u == 5 ? "lăm" : DIGITS[u]);
    }
    *said = 1;
}

/* integer given as a digit string without leading zeros (or "0") */
static void read_int_str(ctx_t *c, const char *d, size_t n) {
    static const char *const SCALES[5] = {"", "nghìn", "triệu", "tỷ", "nghìn tỷ"};
    while (n > 1 && *d == '0') { d++; n--; }
    if (n > 15) { read_digits(c, d, n); return; }
    if (n == 1 && d[0] == '0') { push_word(c, DIGITS[0]); return; }
    int groups = (int)((n + 2) / 3), said = 0;
    size_t first = n - (size_t)(groups - 1) * 3;
    size_t pos = 0;
    for (int gi = groups - 1; gi >= 0; gi--) {
        size_t len = gi == groups - 1 ? first : 3;
        int v = 0;
        for (size_t k = 0; k < len; k++) v = v * 10 + (d[pos + k] - '0');
        pos += len;
        if (v == 0) continue;
        read_group(c, v, !said, &said);
        if (SCALES[gi][0]) push_phrase(c, SCALES[gi]);
    }
}

static void read_unsigned(ctx_t *c, const char *s, size_t n);

static void read_fraction(ctx_t *c, const char *s, size_t n) {
    int all_digits = 1;
    for (size_t i = 0; i < n; i++) all_digits &= is_digit_cp((unsigned char)s[i]);
    if (!all_digits) { read_unsigned(c, s, n); return; }
    if (s[0] == '0') read_digits(c, s, n); else read_int_str(c, s, n);
}

static int is_thousands(const char *s, size_t n) {
    size_t i = 0, run = 0;
    while (i < n && is_digit_cp((unsigned char)s[i])) { i++; run++; }
    if (run < 1 || run > 3 || i == n) return 0;
    while (i < n) {
        if (s[i] != '.') return 0;
        i++;
        size_t r = 0;
        while (i < n && is_digit_cp((unsigned char)s[i])) { i++; r++; }
        if (r != 3) return 0;
    }
    return 1;
}

static void read_unsigned(ctx_t *c, const char *s, size_t n) {
    const char *comma = memchr(s, ',', n);
    if (comma) {
        read_unsigned(c, s, (size_t)(comma - s));
        push_word(c, "phẩy");
        read_fraction(c, comma + 1, n - (size_t)(comma - s) - 1);
        return;
    }
    if (is_thousands(s, n)) {
        char buf[64];
        size_t k = 0;
        for (size_t i = 0; i < n && k < sizeof buf - 1; i++) if (s[i] != '.') buf[k++] = s[i];
        read_int_str(c, buf, k);
        return;
    }
    const char *dot = memchr(s, '.', n);
    if (dot) {
        read_unsigned(c, s, (size_t)(dot - s));
        push_word(c, "chấm");
        read_fraction(c, dot + 1, n - (size_t)(dot - s) - 1);
        return;
    }
    if (n > 1 && s[0] == '0') { read_digits(c, s, n); return; }
    read_int_str(c, s, n);
}

static void read_number_token(ctx_t *c, const char *s, size_t n) {
    if (n && s[0] == '-') { push_word(c, "âm"); read_unsigned(c, s + 1, n - 1); return; }
    read_unsigned(c, s, n);
}

static void read_int_v(ctx_t *c, long v) {
    char b[24];
    int k = 0;
    if (v == 0) b[k++] = '0';
    char t[24];
    int m = 0;
    while (v > 0 && m < 23) { t[m++] = (char)('0' + v % 10); v /= 10; }
    while (m) b[k++] = t[--m];
    read_int_str(c, b, (size_t)k);
}

/* ---------------- words ---------------- */

static void letters_to_utf8(const letters_t *L, char *out, size_t cap);

static void spell(ctx_t *c, const letters_t *L) {
    for (int i = 0; i < L->n; i++) {
        char code = L->code[i];
        char key[4] = {0};
        if (L->tone != 1 && !L->foreign) {
            /* a toned quality letter is not in the table: Python falls back to its NFD base */
        }
        switch (code) {
        case '1': strcpy(key, "ă"); break;
        case '2': strcpy(key, "â"); break;
        case '3': strcpy(key, "ê"); break;
        case '4': strcpy(key, "ô"); break;
        case '5': strcpy(key, "ơ"); break;
        case '6': strcpy(key, "ư"); break;
        case '7': strcpy(key, "đ"); break;
        default: key[0] = code;
        }
        for (int k = 0; k < VTTS_N_LETTER_NAMES; k++)
            if (strcmp(VTTS_LETTER_NAMES[k][0], key) == 0) { push_phrase(c, VTTS_LETTER_NAMES[k][1]); break; }
    }
}

static int letters_equal_key(const letters_t *L, const char *key_utf8) {
    uint32_t cp[WORD_CAP];
    int n = utf8_decode(key_utf8, cp, WORD_CAP);
    letters_t K;
    to_letters(cp, n, &K);
    return K.n == L->n && K.tone == L->tone && memcmp(K.code, L->code, (size_t)L->n) == 0;
}

/* lowercase canonical UTF-8 of a valid syllable (tone placement does not matter for ids,
 * because ids are produced from the parsed syllable, not from this string) */
static void letters_to_utf8(const letters_t *L, char *out, size_t cap) {
    size_t k = 0;
    for (int i = 0; i < L->n && k + 8 < cap; i++) {
        uint32_t c;
        switch (L->code[i]) {
        case '1': c = 0x103; break;
        case '2': c = 0xE2; break;
        case '3': c = 0xEA; break;
        case '4': c = 0xF4; break;
        case '5': c = 0x1A1; break;
        case '6': c = 0x1B0; break;
        case '7': c = 0x111; break;
        default: c = (unsigned char)L->code[i];
        }
        k += (size_t)utf8_encode(c, out + k);
    }
    if (L->tone != 1 && k + 3 < cap) {
        static const uint32_t marks[7] = {0, 0, 0x300, 0x301, 0x309, 0x303, 0x323};
        k += (size_t)utf8_encode(marks[L->tone], out + k);
    }
    out[k] = 0;
}

/* one letter run: syllable, loanword or spelled letters */
static void push_letters(ctx_t *c, const uint32_t *cp, int n) {
    letters_t L;
    to_letters(cp, n, &L);
    if (L.n == 0) return;
    syl_t s;
    if (parse_syl(&L, &s)) {
        char w[WORD_CAP * 4 + 8];
        letters_to_utf8(&L, w, sizeof w);
        push_word(c, w);
        return;
    }
    if (!L.foreign && L.tone == 1)
        for (int k = 0; k < VTTS_N_LOANWORDS; k++)
            if (letters_equal_key(&L, VTTS_LOANWORDS[k][0])) { push_phrase(c, VTTS_LOANWORDS[k][1]); return; }
    if (L.tone != 1) {
        /* Python spells toned quality letters by their NFD base */
        letters_t B = L;
        for (int i = 0; i < B.n; i++) {
            char *x = &B.code[i];
            if (*x == '1' || *x == '2') *x = 'a';
            else if (*x == '3') *x = 'e';
            else if (*x == '4' || *x == '5') *x = 'o';
            else if (*x == '6') *x = 'u';
        }
        /* only the letter that carried the tone loses its quality mark in Python; approximate
         * by folding all quality letters when the word is toned */
        spell(c, &B);
        return;
    }
    spell(c, &L);
}

/* ---------------- sentence -> chunks -> ids ---------------- */

static int count_syl(vtts_text_ws *ws, int a, int b) {
    int n = 0;
    for (int i = a; i < b; i++) n += !is_punct_word(ws->words + ws->word_off[i]);
    return n;
}

static void emit_chunk(ctx_t *c, int a, int b) {
    vtts_text_ws *ws = c->ws;
    if (c->stop || count_syl(ws, a, b) == 0) return;
    int n = 0, last_space = 0, last_punct = 0;
    int bos = token_id("", "<bos>"), eos = token_id("", "<eos>"), space = token_id("", " ");
    ws->ids[n++] = bos;
    for (int i = a; i < b && n < VTTS_TEXT_MAX_IDS - 8; i++) {
        const char *w = ws->words + ws->word_off[i];
        if (is_punct_word(w)) {
            if (last_space) { n--; last_space = 0; }
            if (n > 1) { ws->ids[n++] = token_id("", w); last_punct = 1; }
            continue;
        }
        uint32_t cp[WORD_CAP];
        int m = utf8_decode(w, cp, WORD_CAP);
        letters_t L;
        to_letters(cp, m, &L);
        syl_t s;
        if (!parse_syl(&L, &s)) continue;
        if (n > 1 && !last_punct) ws->ids[n++] = space;
        if (s.onset) ws->ids[n++] = token_id("O:", s.onset);
        if (s.glide) ws->ids[n++] = token_id("", "G:w");
        ws->ids[n++] = token_id("N:", s.nucleus);
        if (s.coda) ws->ids[n++] = token_id("C:", s.coda);
        char t[4] = {'T', (char)('0' + s.tone), 0};
        ws->ids[n++] = token_id("", t);
        last_space = 0;
        last_punct = 0;
    }
    ws->ids[n++] = eos;
    c->chunks++;
    if (c->cb && c->cb(ws->ids, n, c->user)) c->stop = 1;
}

/* mirrors text._pack: split after soft breaks, pack pieces up to MAX_SYL, hard-cut long pieces */
static void emit_sentence(ctx_t *c) {
    vtts_text_ws *ws = c->ws;
    int N = ws->n_words;
    int cur_a = -1, cur_b = -1, cur_n = 0;
    int i = 0;
    while (i < N) {
        int p0 = i;
        while (i < N) {
            const char *w = ws->words + ws->word_off[i];
            i++;
            if (is_punct_word(w) && (w[0] == ',' || w[0] == ':')) break;
        }
        int p1 = i, pn = count_syl(ws, p0, p1);
        if (pn > MAX_SYL) {
            if (cur_a >= 0) { emit_chunk(c, cur_a, cur_b); cur_a = -1; cur_n = 0; }
            int b0 = p0, bn = 0;
            for (int k = p0; k < p1; k++) {
                const char *w = ws->words + ws->word_off[k];
                if (!is_punct_word(w) && bn == MAX_SYL) { emit_chunk(c, b0, k); b0 = k; bn = 0; }
                bn += !is_punct_word(w);
            }
            cur_a = b0; cur_b = p1; cur_n = bn;
        } else if (cur_n + pn > MAX_SYL) {
            if (cur_a >= 0) emit_chunk(c, cur_a, cur_b);
            cur_a = p0; cur_b = p1; cur_n = pn;
        } else {
            if (cur_a < 0) cur_a = p0;
            cur_b = p1;
            cur_n += pn;
        }
    }
    if (cur_a >= 0) emit_chunk(c, cur_a, cur_b);
    ws->n_words = 0;
    ws->words_used = 0;
}

/* ---------------- scanner (mirrors normalize._expand order) ---------------- */

static int match_ascii(const uint32_t *cp, int n, int i, const char *s) {
    for (int k = 0; s[k]; k++) if (i + k >= n || cp[i + k] != (unsigned char)s[k]) return 0;
    return 1;
}

static int digits_at(const uint32_t *cp, int n, int i) {
    int k = 0;
    while (i + k < n && is_digit_cp(cp[i + k])) k++;
    return k;
}

static long num_at(const uint32_t *cp, int i, int len) {
    long v = 0;
    for (int k = 0; k < len; k++) v = v * 10 + (long)(cp[i + k] - '0');
    return v;
}

static int prev_is(const uint32_t *cp, int i, int (*pred)(uint32_t)) { return i > 0 && pred(cp[i - 1]); }

static int is_code_cp(uint32_t c) { return (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'); }
static int is_word_or_dotcomma(uint32_t c) { return is_word_cp(c) || c == '.' || c == ','; }
static int is_digit_or_slash(uint32_t c) { return is_digit_cp(c) || c == '/'; }

/* absorb a preceding "ngày" (as in "ngày 2/9") */
static int same_word(const char *a, const char *b) {
    uint32_t ca[WORD_CAP], cb[WORD_CAP];
    letters_t la, lb;
    to_letters(ca, utf8_decode(a, ca, WORD_CAP), &la);
    to_letters(cb, utf8_decode(b, cb, WORD_CAP), &lb);
    return la.n == lb.n && la.tone == lb.tone && memcmp(la.code, lb.code, (size_t)la.n) == 0;
}

static int pop_ngay(ctx_t *c) {
    const char *lw = last_word(c->ws);
    if (lw && same_word(lw, "ngày")) {
        c->ws->n_words--;
        c->ws->words_used = c->ws->word_off[c->ws->n_words];
        return 1;
    }
    return 0;
}

static void read_date(ctx_t *c, long d, long mo, long y, int had_ngay) {
    if (d >= 1 && d <= 31 && mo >= 1 && mo <= 12) {
        push_word(c, "ngày"); read_int_v(c, d); push_word(c, "tháng"); read_int_v(c, mo);
        if (y >= 0) { push_word(c, "năm"); read_int_v(c, y); }
        return;
    }
    if (had_ngay) push_word(c, "ngày");
    read_int_v(c, d); push_word(c, "trên"); read_int_v(c, mo);
    if (y >= 0) read_int_v(c, y);
}

/* normalize() of n code points (modified in place: ellipsis and dashes mapped first, like
 * normalize()); fl is a flag array of n bytes (dates, product codes). Pushes words into ctx. */
static void scan_vi(ctx_t *c, uint32_t *cpm, uint8_t *fl, int n) {
    vtts_text_ws *ws = c->ws;
    (void)ws;
    for (int k = 0; k < n; k++) {
        if (cpm[k] == 0x2026) cpm[k] = '.';
        else if (cpm[k] == 0x2013 || cpm[k] == 0x2014) cpm[k] = ',';
    }
    const uint32_t *cp = cpm;
    int i = 0;
    for (int q = 0; q < n; q++) {
        fl[q] = 0;
        int dl = digits_at(cp, n, q);
        if (dl < 1 || dl > 2 || prev_is(cp, q, is_digit_cp) || q + dl >= n || cp[q + dl] != '/') continue;
        int m0 = q + dl + 1, ml = digits_at(cp, n, m0);
        if (ml < 1 || ml > 2) continue;
        int yl = (m0 + ml < n && cp[m0 + ml] == '/') ? digits_at(cp, n, m0 + ml + 1) : 0;
        int y_end = m0 + ml + 1 + 4;
        if (yl == 4 && !(y_end < n && is_digit_cp(cp[y_end]))) fl[q] = 1;
        else if (!prev_is(cp, q, is_digit_or_slash) && !(m0 + ml < n && is_digit_or_slash(cp[m0 + ml])))
            fl[q] = 1;
    }
    /* product codes (normalize.PRODUCT_CODE): a standalone run of A-Z and 0-9 with at least one
     * of each, e.g. ESP32, S3, RTX3060. Bit 1 marks its digits, which are read one by one. */
    for (int q = 0; q < n;) {
        if (prev_is(cp, q, is_word_cp) || !is_code_cp(cp[q])) { q++; continue; }
        int j = q, up = 0, dg = 0;
        while (j < n && is_code_cp(cp[j])) { up |= cp[j] >= 'A' && cp[j] <= 'Z'; dg |= is_digit_cp(cp[j]); j++; }
        if (up && dg && !(j < n && is_word_cp(cp[j])))
            for (int k = q; k < j; k++) if (is_digit_cp(cp[k])) fl[k] |= 2;
        q = j;
    }
    while (i < n && !c->stop) {
        uint32_t ch = cp[i];
        /* abbreviations (case-sensitive, not preceded by a word character) */
        if (!prev_is(cp, i, is_word_cp)) {
            int hit = 0;
            for (int k = 0; k < VTTS_N_ABBREVIATIONS && !hit; k++) {
                const char *key = VTTS_ABBREVIATIONS[k][0];
                size_t kl = strlen(key);
                if (!match_ascii(cp, n, i, key)) continue;
                if (key[kl - 1] != '.' && i + (int)kl < n && is_word_cp(cp[i + kl])) continue;
                push_phrase(c, VTTS_ABBREVIATIONS[k][1]);
                i += (int)kl;
                hit = 1;
            }
            if (hit) continue;
        }
        if (is_digit_cp(ch) && (fl[i] & 2)) { /* digits of a product code */
            int j = i;
            char d[64];
            int k = 0;
            while (j < n && (fl[j] & 2) && k < 63) d[k++] = (char)cp[j++];
            read_digits(c, d, (size_t)k);
            i = j;
            continue;
        }
        if (is_digit_cp(ch) || (ch == '-' && i + 1 < n && is_digit_cp(cp[i + 1]) && !prev_is(cp, i, is_word_or_dotcomma))) {
            int start = i, neg = ch == '-';
            int d0 = neg ? i + 1 : i;
            int dl = digits_at(cp, n, d0);
            /* dates */
            if (!neg && dl <= 2 && !prev_is(cp, d0, is_digit_cp) && d0 + dl < n && cp[d0 + dl] == '/') {
                int m0 = d0 + dl + 1, ml = digits_at(cp, n, m0);
                if (ml >= 1 && ml <= 2) {
                    int y0 = m0 + ml + 1, yl = (m0 + ml < n && cp[m0 + ml] == '/') ? digits_at(cp, n, y0) : 0;
                    if (yl == 4 && !(y0 + 4 < n && is_digit_cp(cp[y0 + 4]))) {
                        int had = pop_ngay(c);
                        read_date(c, num_at(cp, d0, dl), num_at(cp, m0, ml), num_at(cp, y0, 4), had);
                        i = y0 + 4;
                        continue;
                    }
                    if (!prev_is(cp, d0, is_digit_or_slash) && !(m0 + ml < n && is_digit_or_slash(cp[m0 + ml]))) {
                        int had = pop_ngay(c);
                        read_date(c, num_at(cp, d0, dl), num_at(cp, m0, ml), -1, had);
                        i = m0 + ml;
                        continue;
                    }
                }
            }
            /* times: 8:30, 8h30, 8h */
            if (!neg && dl <= 2 && !prev_is(cp, d0, is_digit_cp) && d0 + dl < n && (cp[d0 + dl] == ':' || cp[d0 + dl] == 'h')) {
                int m0 = d0 + dl + 1, ml = digits_at(cp, n, m0);
                if (ml == 2 && !(m0 + 2 < n && is_digit_cp(cp[m0 + 2]))) {
                    long h = num_at(cp, d0, dl), mi = num_at(cp, m0, 2);
                    read_int_v(c, h);
                    if (h <= 24 && mi < 60) { push_word(c, "giờ"); read_int_v(c, mi); push_word(c, "phút"); }
                    else read_int_v(c, mi);
                    i = m0 + 2;
                    continue;
                }
                if (cp[d0 + dl] == 'h' && !(m0 < n && is_word_cp(cp[m0]))) {
                    read_int_v(c, num_at(cp, d0, dl));
                    push_word(c, "giờ");
                    i = m0;
                    continue;
                }
            }
            /* number token -?\d+([.,]\d+)* */
            int j = d0 + dl;
            while (j + 1 < n && (cp[j] == '.' || cp[j] == ',') && is_digit_cp(cp[j + 1]) && !(fl[j + 1] & 1))
                j += 1 + digits_at(cp, n, j + 1);
            char buf[128];
            int k = 0;
            for (int q = start; q < j && k < 127; q++) buf[k++] = (char)cp[q];
            buf[k] = 0;
            int lookbehind_ok = !prev_is(cp, start, is_word_or_dotcomma);
            /* percent */
            int pj = j;
            if (pj < n && is_space_cp(cp[pj])) pj++;
            if (lookbehind_ok && pj < n && cp[pj] == '%') {
                read_number_token(c, buf, (size_t)k);
                push_phrase(c, "phần trăm");
                i = pj + 1;
                continue;
            }
            /* degrees: 25°C, 30° */
            if (lookbehind_ok && pj < n && cp[pj] == 0xB0) {
                read_number_token(c, buf, (size_t)k);
                if (pj + 1 < n && cp[pj + 1] == 'C' && !(pj + 2 < n && is_word_cp(cp[pj + 2]))) {
                    push_phrase(c, "độ xê");
                    i = pj + 2;
                    continue;
                    continue;
                }
                if (!(pj + 1 < n && is_word_cp(cp[pj + 1]))) {
                    push_word(c, "độ");
                    i = pj + 1;
                    continue;
                }
                i = j; /* "40°bắc": the sign is dropped later, like Python */
                continue;
            }
            if (lookbehind_ok) {
                read_number_token(c, buf, (size_t)k);
                i = j;
                continue;
            }
            /* preceded by '.', ',' or a word character: Python leaves the run untouched and later
             * reads each digit group on its own, with '.'/',' as punctuation */
            for (int q = d0; q < j;) {
                if (cp[q] == '.' || cp[q] == ',') {
                    char w[2] = {(char)cp[q], 0};
                    push_word(c, w);
                    q++;
                    continue;
                }
                int ql = digits_at(cp, n, q);
                char g[64];
                int gk = 0;
                for (int r = 0; r < ql && gk < 63; r++) g[gk++] = (char)cp[q + r];
                read_number_token(c, g, (size_t)gk);
                q += ql;
            }
            i = j;
            continue;
        }
        if (is_letter_cp(ch)) {
            int j = i;
            while (j < n && (is_letter_cp(cp[j]) || is_combining(cp[j]))) j++;
            push_letters(c, cp + i, j - i);
            i = j;
            continue;
        }
        switch (ch) {
        case ',': case '.': case '?': case '!': case ';': case ':': {
            char w[2] = {(char)ch, 0};
            push_word(c, w);
            break;
        }
        case 0x2026: push_word(c, "."); break;          /* … */
        case 0x2013: case 0x2014: push_word(c, ","); break; /* – — */
        case '+': push_word(c, "cộng"); break;
        case '=': push_word(c, "bằng"); break;
        case '&': push_word(c, "và"); break;
        case '@': push_phrase(c, "a còng"); break;
        default: break; /* separators, quotes, brackets, symbols, emoji */
        }
        i++;
    }
}

int vtts_text_to_ids(const char *utf8, vtts_text_ws *ws, vtts_ids_cb cb, void *user) {
    if (!utf8 || !ws) return -1;
    ctx_t ctx = {ws, cb, user, 0, 0, 0}, *c = &ctx;
    ws->n_cp = utf8_decode(utf8, ws->cp, VTTS_TEXT_MAX_CP);
    ws->n_words = ws->words_used = 0;
    scan_vi(c, ws->cp, ws->date_start, ws->n_cp);
    if (!c->stop && ws->n_words) emit_sentence(c);
    return c->chunks;
}

/* =================== bilingual front-end (phoneme set v2), mirrors text.py =================== */

#include "vtts_text_en.h"

#define V2_MAX_WORDS 40
#define V2_MAX_TOKENS 318

/* lang.py: EDGE characters stripped from a chunk before tagging */
static int is_edge(uint32_t c) {
    static const uint32_t E[] = {'.', ',', ';', ':', '!', '?', '"', '\'', '(', ')', '[', ']', '{', '}',
                                 0x2026, 0x201C, 0x201D, 0x2018, 0x2019, 0x00AB, 0x00BB, 0x2013, 0x2014};
    for (size_t i = 0; i < sizeof E / sizeof *E; i++) if (E[i] == c) return 1;
    return 0;
}

static int ascii_alpha(uint32_t c) { return (c | 32) >= 'a' && (c | 32) <= 'z'; }

/* _has_vietnamese_letters: a non-ASCII letter after NFC (a combining mark on a Latin letter composes) */
static int has_vi_letters(const uint32_t *w, int n) {
    for (int i = 0; i < n; i++) {
        if (w[i] >= 0x80 && is_letter_cp(w[i])) return 1;
        if (is_combining(w[i]) && i > 0 && ascii_alpha(w[i - 1])) return 1;
    }
    return 0;
}

static int any_alpha(const uint32_t *w, int n) {
    for (int i = 0; i < n; i++) if (is_letter_cp(w[i])) return 1;
    return 0;
}

static int plain_latin(const uint32_t *w, int n) {
    int alpha = 0;
    for (int i = 0; i < n; i++) {
        if (w[i] >= 0x80 || !(ascii_alpha(w[i]) || w[i] == '-' || w[i] == '\'')) return 0;
        alpha |= ascii_alpha(w[i]);
    }
    return n > 0 && alpha;
}

static int ascii_syllable(const uint32_t *w, int n) { /* parse_syllable(p.lower()) is not None */
    uint32_t low[WORD_CAP];
    if (n <= 0 || n > WORD_CAP) return 0;
    for (int i = 0; i < n; i++) low[i] = w[i] | 32;
    letters_t L;
    to_letters(low, n, &L);
    syl_t s;
    return parse_syl(&L, &s);
}

enum { TAG_NEUTRAL = 0, TAG_VI = 1, TAG_EN = 2 };

static int key_eq(const uint32_t *w, int n, const char *k, int lower) {
    int i = 0;
    for (; k[i]; i++) if (i >= n || (lower ? (w[i] | 32) : w[i]) != (unsigned char)k[i]) return 0;
    return i == n;
}

/* word_lang(core, mode) */
static int word_tag(const uint32_t *w, int n, int sent_en) {
    if (n == 0) return TAG_NEUTRAL;
    if (has_vi_letters(w, n)) return TAG_VI;
    if (!plain_latin(w, n)) return TAG_NEUTRAL;
    if (sent_en) return TAG_EN;
    int all_syl = 1, all_caps = 1, parts = 0;
    for (int a = 0; a < n;) {
        int b = a;
        while (b < n && w[b] != '-' && w[b] != '\'') b++;
        if (b > a) {
            parts++;
            all_syl &= ascii_syllable(w + a, b - a);
            int up = b - a <= 5;
            for (int k = a; k < b; k++) up &= w[k] >= 'A' && w[k] <= 'Z';
            all_caps &= up;
        }
        a = b + 1;
    }
    if (parts && all_syl) return TAG_VI;
    for (int k = 0; k < VTTS_N_LOANWORDS; k++) if (key_eq(w, n, VTTS_LOANWORDS[k][0], 1)) return TAG_VI;
    for (int k = 0; k < VTTS_N_ABBREVIATIONS; k++) if (key_eq(w, n, VTTS_ABBREVIATIONS[k][0], 0)) return TAG_VI;
    if (parts && all_caps) return TAG_VI;
    return TAG_EN;
}

/* syllable tokens of a normalized Vietnamese word into out; 0 if not a syllable */
static int syl_ids(const char *word, uint8_t *out) {
    uint32_t cp[WORD_CAP];
    int m = utf8_decode(word, cp, WORD_CAP), n = 0;
    letters_t L;
    to_letters(cp, m, &L);
    syl_t s;
    if (!parse_syl(&L, &s)) return 0;
    if (s.onset) out[n++] = (uint8_t)token_id("O:", s.onset);
    if (s.glide) out[n++] = (uint8_t)token_id("", "G:w");
    out[n++] = (uint8_t)token_id("N:", s.nucleus);
    if (s.coda) out[n++] = (uint8_t)token_id("C:", s.coda);
    char t[4] = {'T', (char)('0' + s.tone), 0};
    out[n++] = (uint8_t)token_id("", t);
    return n;
}

static void add_item(vtts_text_ws *ws, const uint8_t *ids, int n, int punct) {
    if (ws->n_items >= VTTS_TEXT_MAX_ITEMS || ws->pool_used + n > VTTS_TEXT_POOL) return;
    ws->item_off[ws->n_items] = (uint16_t)ws->pool_used;
    ws->item_len[ws->n_items] = (uint8_t)n;
    ws->item_punct[ws->n_items] = (uint8_t)(punct ? ids[0] : 0);
    memcpy(ws->pool + ws->pool_used, ids, (size_t)n);
    ws->pool_used += n;
    ws->n_items++;
}

static int last_is_word(const vtts_text_ws *ws) { return ws->n_items && !ws->item_punct[ws->n_items - 1]; }

static void add_word_or_mark(vtts_text_ws *ws, const char *w, int en, const vtts_lex *lex) {
    uint8_t ids[256];
    if (is_punct_word(w)) {
        if (last_is_word(ws)) { ids[0] = (uint8_t)token_id("", w); add_item(ws, ids, 1, 1); }
        return;
    }
    int n = en ? vtts_en_g2p(lex, w, ids, (int)sizeof ids) : syl_ids(w, ids);
    if (n > 0) add_item(ws, ids, n, 0);
}

/* _assemble size of items [a, b): (tokens, words) */
static void part_size(const vtts_text_ws *ws, int a, int b, int *tok, int *words) {
    int t = 0, w = 0, last_punct = 0;
    for (int i = a; i < b; i++) {
        if (ws->item_punct[i]) { if (t) { t++; last_punct = 1; } continue; }
        if (t && !last_punct) t++;
        t += ws->item_len[i];
        last_punct = 0;
        w++;
    }
    *tok = t;
    *words = w;
}

static void emit_part(ctx_t *c, int a, int b) {
    vtts_text_ws *ws = c->ws;
    int n = 0, last_punct = 0, words = 0;
    if (c->stop) return;
    ws->ids[n++] = VTTS_V2_BOS;
    for (int i = a; i < b && n < VTTS_TEXT_MAX_IDS - 1; i++) {
        const uint8_t *t = ws->pool + ws->item_off[i];
        if (ws->item_punct[i]) {
            if (n > 1) { ws->ids[n++] = t[0]; last_punct = 1; }
            continue;
        }
        if (n > 1 && !last_punct) ws->ids[n++] = VTTS_V2_SPACE;
        for (int k = 0; k < ws->item_len[i] && n < VTTS_TEXT_MAX_IDS - 1; k++) ws->ids[n++] = t[k];
        last_punct = 0;
        words++;
    }
    if (!words) return; /* only punctuation */
    ws->ids[n++] = VTTS_V2_EOS;
    c->chunks++;
    if (c->cb && c->cb(ws->ids, n, c->user)) c->stop = 1;
}

static int fits(const vtts_text_ws *ws, int a, int b) {
    int t, w;
    part_size(ws, a, b, &t, &w);
    return t <= V2_MAX_TOKENS && w <= V2_MAX_WORDS;
}

/* _pack_items: pieces end after ',' or ':'; pack whole pieces, hard-cut a piece that is too long */
static void pack_items(ctx_t *c) {
    vtts_text_ws *ws = c->ws;
    int N = ws->n_items, ca = -1, cb = -1, i = 0;
    int comma = token_id("", ","), colon = token_id("", ":");
    while (i < N && !c->stop) {
        int p0 = i;
        while (i < N) {
            int pm = ws->item_punct[i++];
            if (pm && (pm == comma || pm == colon)) break;
        }
        int p1 = i;
        if (fits(ws, ca < 0 ? p0 : ca, p1)) { if (ca < 0) ca = p0; cb = p1; continue; }
        if (ca >= 0) { emit_part(c, ca, cb); ca = -1; }
        for (int k = p0; k < p1; k++) {
            if (ca >= 0 && !fits(ws, ca, k + 1)) { emit_part(c, ca, cb); ca = -1; }
            if (ca < 0) ca = k;
            cb = k + 1;
        }
    }
    if (ca >= 0) emit_part(c, ca, cb);
}

/* one sentence (code points [s, e) of ws->cp): tags, runs, normalization, items, chunks */
static void v2_sentence(ctx_t *c, int s, int e, int mode, const vtts_lex *lex) {
    vtts_text_ws *ws = c->ws;
    const uint32_t *cp = ws->cp;
    enum { MAXCH = 1024 };
    static int cs[MAXCH], ce[MAXCH], tag[MAXCH];
    int nc = 0;
    for (int i = s; i < e && nc < MAXCH;) { /* sentence.split() */
        while (i < e && is_space_cp(cp[i])) i++;
        if (i >= e) break;
        int j = i;
        while (j < e && !is_space_cp(cp[j])) j++;
        cs[nc] = i; ce[nc] = j; nc++;
        i = j;
    }
    if (!nc) return;
    int sent_en = mode == VTTS_LANG_EN;
    if (mode == VTTS_LANG_AUTO) { /* share of words with Vietnamese letters >= 0.2 -> vi */
        int words = 0, vi = 0;
        for (int k = 0; k < nc; k++) {
            int a = cs[k], b = ce[k];
            while (a < b && is_edge(cp[a])) a++;
            while (b > a && is_edge(cp[b - 1])) b--;
            if (!any_alpha(cp + a, b - a)) continue;
            words++;
            vi += has_vi_letters(cp + a, b - a);
        }
        sent_en = words && !((double)vi / words >= 0.2);
    }
    for (int k = 0; k < nc; k++) {
        int a = cs[k], b = ce[k];
        while (a < b && is_edge(cp[a])) a++;
        while (b > a && is_edge(cp[b - 1])) b--;
        int t = word_tag(cp + a, b - a, sent_en);
        tag[k] = t == TAG_NEUTRAL ? (sent_en ? TAG_EN : TAG_VI) : t;
    }
    ws->n_items = ws->pool_used = 0;
    for (int k = 0; k < nc && !c->stop;) { /* runs of one language, chunks joined by single spaces */
        int k1 = k, len = 0;
        while (k1 < nc && tag[k1] == tag[k]) {
            if (k1 > k && len < VTTS_TEXT_MAX_CP) ws->run[len++] = ' ';
            for (int q = cs[k1]; q < ce[k1] && len < VTTS_TEXT_MAX_CP; q++) ws->run[len++] = cp[q];
            k1++;
        }
        if (tag[k] == TAG_VI) {
            ws->n_words = ws->words_used = 0;
            c->collect = 1;
            scan_vi(c, ws->run, ws->date_start, len);
            c->collect = 0;
            for (int w = 0; w < ws->n_words; w++) add_word_or_mark(ws, ws->words + ws->word_off[w], 0, lex);
            ws->n_words = ws->words_used = 0;
        } else if (vtts_en_normalize(ws->run, len, ws->en_a, ws->en_b, VTTS_TEXT_EN_CAP, ws->en_out,
                                     (int)sizeof ws->en_out) >= 0) {
            for (char *w = ws->en_out; *w;) { /* split on single spaces */
                char *sp = strchr(w, ' ');
                if (sp) *sp = 0;
                if (*w) add_word_or_mark(ws, w, 1, lex);
                if (!sp) break;
                w = sp + 1;
            }
        }
        k = k1;
    }
    pack_items(c);
}

int vtts_text_to_ids_ex(const char *utf8, vtts_text_ws *ws, const vtts_text_opts *o, vtts_ids_cb cb, void *user) {
    if (!o || o->lang == VTTS_LANG_V1) return vtts_text_to_ids(utf8, ws, cb, user);
    if (!utf8 || !ws) return -1;
    ctx_t ctx = {ws, cb, user, 0, 0, 0}, *c = &ctx;
    int n = ws->n_cp = utf8_decode(utf8, ws->cp, VTTS_TEXT_MAX_CP);
    int a = 0, z = n;
    while (a < z && is_space_cp(ws->cp[a])) a++; /* text.strip() */
    while (z > a && is_space_cp(ws->cp[z - 1])) z--;
    int s = a;
    for (int i = a; i < z && !c->stop; i++) { /* split at whitespace after . ! ? ; */
        uint32_t pc = i > s ? ws->cp[i - 1] : 0;
        if (is_space_cp(ws->cp[i]) && (pc == '.' || pc == '!' || pc == '?' || pc == ';')) {
            v2_sentence(c, s, i, o->lang, o->lex);
            while (i < z && is_space_cp(ws->cp[i])) i++;
            s = i;
            i--;
        }
    }
    if (s < z && !c->stop) v2_sentence(c, s, z, o->lang, o->lex);
    return c->chunks;
}
