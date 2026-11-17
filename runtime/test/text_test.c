/* SPDX-License-Identifier: Apache-2.0 */
/* text_test.c -- device front-end must produce exactly the Python ids.
 * usage: text_test text_parity.tsv                 (text \t ids;ids...; phoneme set v1)
 *        text_test --lex LEX text_parity_v2.tsv    (mode \t text \t ids...; mode vi|en|auto)
 *        text_test --fuzz [--lex LEX]              (v1, and v2 auto mode when --lex is given) */
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

static vtts_lex s_lex;
static int s_has_lex;

static int run(const char *text, int mode, vtts_text_ws *ws, vtts_ids_cb cb, void *user) {
    vtts_text_opts o = {(vtts_lang)mode, s_has_lex ? &s_lex : NULL};
    return vtts_text_to_ids_ex(text, ws, &o, cb, user);
}

static int load_lex(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    rewind(f);
    uint8_t *b = malloc((size_t)n);
    if (!b || fread(b, 1, (size_t)n, f) != (size_t)n) return -1;
    fclose(f);
    s_has_lex = vtts_lex_init(&s_lex, b, (size_t)n) == 0;
    return s_has_lex ? 0 : -1;
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
            for (int m = VTTS_LANG_VI; m <= VTTS_LANG_AUTO; m++) {
                rc = run(buf, m, &ws, NULL, NULL);
                if (rc < 0) { printf("fuzz v2: error %d\n", rc); return 1; }
            }
        }
    }
    if (vtts_text_to_ids("", &ws, NULL, NULL) != 0 || vtts_text_to_ids("...", &ws, NULL, NULL) != 0) {
        puts("fuzz: empty input must give 0 chunks");
        return 1;
    }
    puts("fuzz: ok");
    return 0;
}

int main(int argc, char **argv) {
    const char *file = NULL;
    int do_fuzz = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fuzz") == 0) do_fuzz = 1;
        else if (strcmp(argv[i], "--lex") == 0 && i + 1 < argc) {
            if (load_lex(argv[++i])) { puts("bad lexicon"); return 2; }
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
            mode = strcmp(line, "en") == 0 ? VTTS_LANG_EN : strcmp(line, "auto") == 0 ? VTTS_LANG_AUTO : VTTS_LANG_VI;
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
    printf("%d/%d exact\n", total - bad, total);
    return bad ? 1 : 0;
}
