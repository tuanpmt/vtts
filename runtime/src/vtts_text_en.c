/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_text_en.c -- English word -> token ids (set v2), mirroring src/vtts/frontend/en/g2p_en.py:
 * lexicon, hyphen split, CamelCase split, short acronyms spelled, lexicon or two-part compound,
 * inflections (-'s -s -es -ed -ing -er -ly) on a known base, learned letter-to-sound. */
#include "vtts_text_en.h"

#include <string.h>

#include "vtts_text_tables.h"

#define EN_WORD_MAX 128
#define S1 (VTTS_V2_S0 + 1)
#define S2 (VTTS_V2_S0 + 2)

static int is_lower(char c) { return c >= 'a' && c <= 'z'; }
static int is_upper(char c) { return c >= 'A' && c <= 'Z'; }
static int is_stress(uint8_t t) { return t >= VTTS_V2_S0 && t <= VTTS_V2_S0 + 2; }
static uint8_t ph(const char *name) {
    for (int i = 0; i < (int)(sizeof VTTS_ARPABET / sizeof *VTTS_ARPABET); i++)
        if (strcmp(VTTS_ARPABET[i], name) == 0) return (uint8_t)(VTTS_V2_EN0 + i);
    return 0;
}

typedef struct { uint8_t *t; int n, cap, err; } tb_t; /* token buffer */

static void tb_put(tb_t *b, uint8_t x) { if (b->n < b->cap) b->t[b->n++] = x; else b->err = 1; }
static int has_primary(const tb_t *b, int from) {
    for (int i = from; i < b->n; i++) if (b->t[i] == S1) return 1;
    return 0;
}
/* append part (already in b from `start`): demote its primaries if b had one before it */
static void join_part(tb_t *b, int start, int had_primary) {
    if (!had_primary) return;
    for (int i = start; i < b->n; i++) if (b->t[i] == S1) b->t[i] = S2;
}

static int lex_get(const vtts_lex *lx, const char *w, tb_t *b) {
    if (!lx) return 0;
    int k = vtts_lex_lookup(lx, w, b->t + b->n, b->cap - b->n);
    if (k < 0) { b->err = 1; return 0; }
    b->n += k;
    return k > 0;
}

static int in_lex(const vtts_lex *lx, const char *w) {
    uint8_t tmp[64];
    return lx && vtts_lex_lookup(lx, w, tmp, (int)sizeof tmp) != 0;
}

/* lexicon entry or two-part compound of lexicon words (each part >= 3 letters) */
static int known(const vtts_lex *lx, const char *w, tb_t *b) {
    if (lex_get(lx, w, b)) return 1;
    int n = (int)strlen(w);
    char a[EN_WORD_MAX];
    for (int i = n - 3; i > 2; i--) {
        memcpy(a, w, (size_t)i);
        a[i] = 0;
        if (in_lex(lx, a) && in_lex(lx, w + i)) {
            int s = b->n;
            lex_get(lx, a, b);
            int had = has_primary(b, s);
            int s2 = b->n;
            lex_get(lx, w + i, b);
            join_part(b, s2, had);
            return 1;
        }
    }
    return 0;
}

static int last_phone(const tb_t *b, int from) {
    for (int i = b->n - 1; i >= from; i--)
        if (!is_stress(b->t[i]) && b->t[i] >= VTTS_V2_EN0) return b->t[i];
    return 0;
}

static int ph_in(int p, const char *const *names) {
    for (; *names; names++) if (p == ph(*names)) return 1;
    return 0;
}
static const char *const SIBILANTS[] = {"S", "Z", "SH", "ZH", "CH", "JH", 0};
static const char *const VOICELESS[] = {"P", "T", "K", "F", "TH", 0};
static const char *const PAST_T[] = {"P", "T", "K", "F", "TH", "S", "SH", "CH", 0};

static void plural(tb_t *b, int from) {
    int last = last_phone(b, from);
    if (ph_in(last, SIBILANTS)) { tb_put(b, ph("IH")); tb_put(b, VTTS_V2_S0); tb_put(b, ph("Z")); }
    else tb_put(b, ph_in(last, VOICELESS) ? ph("S") : ph("Z"));
}
static void past(tb_t *b, int from) {
    int last = last_phone(b, from);
    if (last == ph("T") || last == ph("D")) { tb_put(b, ph("IH")); tb_put(b, VTTS_V2_S0); tb_put(b, ph("D")); }
    else tb_put(b, ph_in(last, PAST_T) ? ph("T") : ph("D"));
}

static int ends(const char *w, int n, const char *suf) {
    int k = (int)strlen(suf);
    return n >= k && memcmp(w + n - k, suf, (size_t)k) == 0;
}

/* known base with `cut` letters removed and `add` appended */
static int known_base(const vtts_lex *lx, const char *w, int n, int cut, const char *add, tb_t *b) {
    char base[EN_WORD_MAX];
    if (n - cut < 0 || n - cut + (int)strlen(add) >= EN_WORD_MAX) return 0;
    memcpy(base, w, (size_t)(n - cut));
    strcpy(base + n - cut, add);
    return known(lx, base, b);
}

static int inflected(const vtts_lex *lx, const char *w, tb_t *b) {
    int n = (int)strlen(w), s = b->n;
    if (ends(w, n, "'s") && known_base(lx, w, n, 2, "", b)) { plural(b, s); return 1; }
    if (ends(w, n, "es") && (ends(w, n - 2, "s") || ends(w, n - 2, "x") || ends(w, n - 2, "z") ||
                             ends(w, n - 2, "ch") || ends(w, n - 2, "sh")) && known_base(lx, w, n, 2, "", b)) {
        plural(b, s);
        return 1;
    }
    if (ends(w, n, "s") && !ends(w, n, "ss") && known_base(lx, w, n, 1, "", b)) { plural(b, s); return 1; }
    if (ends(w, n, "ed") && (known_base(lx, w, n, 2, "", b) || known_base(lx, w, n, 1, "", b))) { past(b, s); return 1; }
    if (ends(w, n, "ing") && (known_base(lx, w, n, 3, "", b) || known_base(lx, w, n, 3, "e", b))) {
        tb_put(b, ph("IH")); tb_put(b, VTTS_V2_S0); tb_put(b, ph("NG"));
        return 1;
    }
    if (ends(w, n, "er") && known_base(lx, w, n, 2, "", b)) { tb_put(b, ph("ER")); tb_put(b, VTTS_V2_S0); return 1; }
    if (ends(w, n, "ly") && known_base(lx, w, n, 2, "", b)) {
        tb_put(b, ph("L")); tb_put(b, ph("IY")); tb_put(b, VTTS_V2_S0);
        return 1;
    }
    return 0;
}

static int has_cased(const char *w) { for (; *w; w++) if (is_lower(*w) || is_upper(*w)) return 1; return 0; }

static void g2p(const vtts_lex *lx, const char *word, tb_t *b, int depth);

/* g2p of each part, joined keeping the first primary stress */
static void join_g2p(const vtts_lex *lx, const char *const *parts, int np, tb_t *b, int depth) {
    for (int i = 0; i < np; i++) {
        int had = has_primary(b, 0), s = b->n;
        g2p(lx, parts[i], b, depth + 1);
        join_part(b, s, had);
    }
}

static void g2p(const vtts_lex *lx, const char *word, tb_t *b, int depth) {
    char w[EN_WORD_MAX], low[EN_WORD_MAX];
    int n = (int)strlen(word);
    if (depth > 8 || n >= EN_WORD_MAX) return;
    int a = 0, z = n;
    while (a < z && word[a] == '\'') a++;  /* strip("'") */
    while (z > a && word[z - 1] == '\'') z--;
    if (a == z) return;
    n = z - a;
    memcpy(w, word + a, (size_t)n);
    w[n] = 0;
    for (int i = 0; i <= n; i++) low[i] = is_upper(w[i]) ? (char)(w[i] - 'A' + 'a') : w[i];
    if (lex_get(lx, low, b)) return;
    if (strchr(w, '-')) {
        char buf[EN_WORD_MAX];
        const char *parts[EN_WORD_MAX];
        int np = 0;
        strcpy(buf, w);
        for (char *p = strtok(buf, "-"); p; p = strtok(NULL, "-")) parts[np++] = p;
        join_g2p(lx, parts, np, b, depth);
        return;
    }
    { /* CamelCase: [A-Z]+(?![a-z]) | [A-Z]?[a-z]+ (findall), when the pieces cover the word */
        char pieces[EN_WORD_MAX * 2], joined[EN_WORD_MAX], noap[EN_WORD_MAX];
        const char *parts[EN_WORD_MAX];
        int np = 0, pp = 0, jn = 0, i = 0;
        while (i < n) {
            int len = 0;
            if (is_upper(w[i])) {
                int L = 0;
                while (i + L < n && is_upper(w[i + L])) L++;
                if (!(i + L < n && is_lower(w[i + L]))) len = L;
                else if (L >= 2) len = L - 1;
            }
            if (!len) {
                int j = i;
                if (is_upper(w[j]) && j + 1 < n && is_lower(w[j + 1])) j++;
                int k = j;
                while (k < n && is_lower(w[k])) k++;
                if (k > j) len = k - i;
            }
            if (!len) { i++; continue; }
            parts[np++] = pieces + pp;
            memcpy(pieces + pp, w + i, (size_t)len);
            pp += len;
            pieces[pp++] = 0;
            memcpy(joined + jn, w + i, (size_t)len);
            jn += len;
            i += len;
        }
        joined[jn] = 0;
        int m = 0;
        for (int k = 0; k < n; k++) if (w[k] != '\'') noap[m++] = w[k];
        noap[m] = 0;
        if (np > 1 && strcmp(joined, noap) == 0) { join_g2p(lx, parts, np, b, depth); return; }
    }
    { /* short all-caps acronym: isupper() and isalpha() and len <= 4 */
        int alpha = 1, lower = 0;
        for (int i = 0; i < n; i++) {
            if (!is_upper(w[i]) && !is_lower(w[i])) alpha = 0;
            if (is_lower(w[i])) lower = 1;
        }
        if (alpha && !lower && has_cased(w) && n <= 4) {
            for (int i = 0; i < n; i++) {
                const uint8_t *L = VTTS_EN_LETTERS[w[i] - 'A'];
                int had = has_primary(b, 0), s = b->n;
                for (int k = 0; k < L[0]; k++) tb_put(b, L[1 + k]);
                join_part(b, s, had);
            }
            return;
        }
    }
    if (known(lx, low, b) || inflected(lx, low, b)) return;
    if (!lx) return;
    int k = vtts_lex_predict(lx, low, b->t + b->n, b->cap - b->n);
    if (k < 0) b->err = 1; else b->n += k;
}

int vtts_en_g2p(const vtts_lex *lx, const char *word, uint8_t *out, int cap) {
    tb_t b = {out, 0, cap, 0};
    if (!word) return 0;
    g2p(lx, word, &b, 0);
    return b.err ? -1 : b.n;
}
