/* SPDX-License-Identifier: Apache-2.0 */
/* text_test.c -- device front-end must produce exactly the Python ids.
 * usage: text_test text_parity.tsv                          (text \t ids;ids...; phoneme set v1)
 *        text_test --lex LEX [--zh ZLEX] text_parity_v2.tsv (mode \t text \t ids...; mode vi|en|auto|zh|ko)
 *        text_test --fuzz [--lex LEX] [--zh ZLEX]           (v1; v2 and ko modes with --lex; zh mode with --zh) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts_text.h"

typedef struct { char buf[65536]; size_t n; } out_t;

static int collect(const int32_t *ids, int n, void *user) {
    out_t *o = user;
    if (o->n) o->buf[o->n++] = ';';
    for (int i = 0; i < n; i++) o->n += (size_t)snprintf(o->buf + o->n, sizeof(o->buf) - o->n, i ? " %d" : "%d", ids[i]);
    o->buf[o->n] = 0;
    return 0;
}

/* fuzz: every chunk holds BOS ... EOS, at most VTTS_TEXT_MAX_IDS ids, all inside the token set */
static int check_ids(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 171) *bad = 1;
    return 0;
}

static vtts_lex s_lex;
static vtts_zlex s_zh;
static int s_has_lex, s_has_zh;

static int run(const char *text, int mode, vtts_text_ws *ws, vtts_ids_cb cb, void *user) {
    vtts_text_opts o = {(vtts_lang)mode, s_has_lex ? &s_lex : NULL, s_has_zh ? &s_zh : NULL};
    return vtts_text_to_ids_ex(text, ws, &o, cb, user);
}

static uint8_t *load_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    rewind(f);
    uint8_t *b = n > 0 ? malloc((size_t)n) : NULL;
    if (!b || fread(b, 1, (size_t)n, f) != (size_t)n) { fclose(f); free(b); return NULL; }
    fclose(f);
    *size = (size_t)n;
    return b;
}

static int load_lex(const char *path) {
    size_t n;
    uint8_t *b = load_file(path, &n);
    s_has_lex = b && vtts_lex_init(&s_lex, b, n) == 0;
    return s_has_lex ? 0 : -1;
}

static int load_zh(const char *path) {
    size_t n;
    uint8_t *b = load_file(path, &n);
    s_has_zh = b && vtts_zlex_init(&s_zh, b, n) == 0;
    return s_has_zh ? 0 : -1;
}

/* mixed Han (common characters, digits-heavy), ASCII, numbers, CJK and ASCII punctuation, symbols */
static int fuzz_zh(vtts_text_ws *ws) {
    static char buf[20000];
    static const char *const parts[] = {
        "中", "国", "银行", "行", "长", "了", "的", "一", "不", "重", "年", "月", "日", "点", "，", "。", "！", "？",
        "；", "：", "、", "“", "”", "（", "）", "《", "》", "…", "—", "·", "　", "％", "￥", "℃", "°", "１", "Ａ",
        "a", "Z", "e", "S", "P", "x", "'", "-", "~", "/", ".", ",", ":", "%", "$", "€", "£", "¥", "+", "&", "@",
        "0", "1", "2", "3", "5", "9", " ", " ", "\t", "ESP32", "Wi-Fi", "iPhone", "2026-11-18", "9:30", "12:00:05",
        "1,234", "3.14", "-5", "99%", "$5", "2024年", "3~5", "10:2", "\xe4\xb8", "\xff", "\x80", "é", "ạ", "한"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4242;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_ZH, ws, check_ids, &bad);
        if (rc < 0 || bad) { printf("fuzz zh: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_ZH, ws, NULL, NULL) != 0 || run("。。，", VTTS_LANG_ZH, ws, NULL, NULL) != 0) {
        puts("fuzz zh: empty input must give 0 chunks");
        return 1;
    }
    return 0;
}

/* Hangul words (rule-heavy syllables, exception entries), jamo, ASCII, numbers with counters, dates,
 * times, units, money, CJK and ASCII punctuation, symbols and random bytes; chunks must stay inside
 * the ko-en set (153 ids, no Vietnamese ids) */
static int check_ko(const int32_t *ids, int n, void *user) {
    int *bad = user;
    if (n < 3 || n > VTTS_TEXT_MAX_IDS || ids[0] != 1 || ids[n - 1] != 2) *bad = 1;
    for (int i = 0; i < n; i++) if (ids[i] < 0 || ids[i] >= 153 || (ids[i] >= 10 && ids[i] <= 64)) *bad = 1;
    return 0;
}

static int fuzz_ko(vtts_text_ws *ws) {
    static char buf[20000];
    static const char *const parts[] = {
        "한국어", "학교", "국물", "같이", "좋다", "앉아", "닭", "읽고", "넓다", "신라", "희망", "가져", "물고기", "김밥",
        "솜이불", "밟다", "값을", "흙", "의", "를", "에서", "은", "ㅋ", "ㆍ", "개", "명", "번째", "시", "분", "월", "년",
        "일", "살", "개월", "，", "。", "！", "？", "；", "：", "、", "“", "”", "（", "）", "《", "》", "…", "—", "·",
        "　", "％", "￦", "₩", "℃", "°", "°C", "１", "Ａ", "a", "Z", "e", "S", "P", "x", "'", "-", "~", "/", ".", ",",
        ":", "%", "$", "€", "£", "¥", "+", "&", "@", "0", "1", "2", "3", "5", "9", " ", " ", "\t", "ESP32", "Wi-Fi",
        "iPhone", "2026-11-18", "2026. 6. 10.", "9:30", "12:00:05", "010-1234-5678", "0123", "1,234", "3.14", "-5",
        "99%", "$5", "5km", "16GB", "3~5", "10:2", "\xea\xb0", "\xff", "\x80", "é", "中", "か", "ạ"};
    const int np = (int)(sizeof parts / sizeof *parts);
    unsigned seed = 4243;
    int bad = 0;
    for (int it = 0; it < 3000; it++) {
        seed = seed * 1103515245u + 12345u;
        int target = (int)((seed >> 16) % (it % 10 == 0 ? 15000 : 400)), n = 0;
        int no_space = it % 7 == 0; /* long words: split into syllables, item and pool limits */
        while (n < target) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            if (r % 9 == 0) { buf[n++] = (char)(1 + (r >> 4) % 255); continue; } /* random byte */
            const char *p = parts[r % (unsigned)np];
            if (no_space && (p[0] == ' ' || p[0] == '\t')) continue;
            size_t l = strlen(p);
            if (n + (int)l >= (int)sizeof buf - 1) break;
            memcpy(buf + n, p, l);
            n += (int)l;
        }
        buf[n] = 0;
        int rc = run(buf, VTTS_LANG_KO, ws, check_ko, &bad);
        if (rc < 0 || bad) { printf("fuzz ko: rc %d, bad chunk %d (iteration %d)\n", rc, bad, it); return 1; }
    }
    if (run("", VTTS_LANG_KO, ws, NULL, NULL) != 0 || run("。。，", VTTS_LANG_KO, ws, NULL, NULL) != 0) {
        puts("fuzz ko: empty input must give 0 chunks");
        return 1;
    }
    return 0;
}

static int fuzz(void) {
    static vtts_text_ws ws;
    static char buf[20000];
    unsigned seed = 12345;
    for (int it = 0; it < 3000; it++) {
        int n = (int)((seed = seed * 1103515245u + 12345u) >> 16) % 19999;
        for (int i = 0; i < n; i++) {
            seed = seed * 1103515245u + 12345u;
            unsigned r = seed >> 16;
            /* mix of ASCII, digits, separators, Vietnamese UTF-8 and random high bytes */
            static const char *const parts[] = {"a", "7", ".", ",", "/", ":", "-", " ", "\xc3\xa0", "\xe1\xbb\x87", "%", "h"};
            buf[i] = (r % 5 == 0) ? (char)(r >> 3) : parts[r % 12][0];
        }
        buf[n] = 0;
        int rc = vtts_text_to_ids(buf, &ws, NULL, NULL);
        if (rc < 0) { printf("fuzz: error %d\n", rc); return 1; }
        if (s_has_lex) {
            for (int m = VTTS_LANG_VI; m <= (s_has_zh ? VTTS_LANG_ZH : VTTS_LANG_AUTO); m++) {
                rc = run(buf, m, &ws, NULL, NULL);
                if (rc < 0) { printf("fuzz v2: error %d\n", rc); return 1; }
            }
            rc = run(buf, VTTS_LANG_KO, &ws, NULL, NULL);
            if (rc < 0) { printf("fuzz ko: error %d\n", rc); return 1; }
        }
    }
    if (vtts_text_to_ids("", &ws, NULL, NULL) != 0 || vtts_text_to_ids("...", &ws, NULL, NULL) != 0) {
        puts("fuzz: empty input must give 0 chunks");
        return 1;
    }
    if (s_has_zh && fuzz_zh(&ws)) return 1;
    if (s_has_lex && fuzz_ko(&ws)) return 1;
    printf("fuzz: ok%s%s\n", s_has_lex ? " (with ko)" : "", s_has_zh ? " (with zh)" : "");
    return 0;
}

static int mode_of(const char *m) {
    if (strcmp(m, "en") == 0) return VTTS_LANG_EN;
    if (strcmp(m, "auto") == 0) return VTTS_LANG_AUTO;
    if (strcmp(m, "zh") == 0) return VTTS_LANG_ZH;
    if (strcmp(m, "ko") == 0) return VTTS_LANG_KO;
    return VTTS_LANG_VI;
}

int main(int argc, char **argv) {
    const char *file = NULL;
    int do_fuzz = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fuzz") == 0) do_fuzz = 1;
        else if (strcmp(argv[i], "--lex") == 0 && i + 1 < argc) {
            if (load_lex(argv[++i])) { puts("bad lexicon"); return 2; }
        } else if (strcmp(argv[i], "--zh") == 0 && i + 1 < argc) {
            if (load_zh(argv[++i])) { puts("bad zh blob"); return 2; }
        } else file = argv[i];
    }
    if (do_fuzz) return fuzz();
    if (!file) return 2;
    FILE *f = fopen(file, "rb");
    if (!f) return 2;
    static char line[1 << 16];
    static vtts_text_ws ws;
    static out_t out;
    int total = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        char *text = line, *want = tab + 1;
        int mode = VTTS_LANG_V1;
        if (s_has_lex) { /* v2 fixture: mode \t text \t ids */
            mode = mode_of(line);
            text = want;
            char *t2 = strchr(text, '\t');
            if (!t2) continue;
            *t2 = 0;
            want = t2 + 1;
        }
        want[strcspn(want, "\n")] = 0;
        out.n = 0; out.buf[0] = 0;
        int rc = run(text, mode, &ws, collect, &out);
        total++;
        if (rc < 0 || strcmp(out.buf, want) != 0) {
            if (bad < 15) printf("MISMATCH [%d]: %s\n  want %s\n  got  %s (rc %d)\n", mode, text, want, out.buf, rc);
            bad++;
        }
    }
    fclose(f);
    printf("%d/%d exact\n", total - bad, total);
    return bad ? 1 : 0;
}
