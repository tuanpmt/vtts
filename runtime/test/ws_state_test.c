/* SPDX-License-Identifier: Apache-2.0 */
/* ws_state_test.c -- the text front-end's ids must not depend on what the workspace held before.
 * usage: ws_state_test MODEL.vtts LEX.bin TEXTS.txt
 * For every text: ids from a zeroed workspace, from one filled with junk, and after each other text
 * (the firmware reuses one workspace for every sentence) must be identical. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts.h"
#include "vtts_text.h"

typedef struct { int32_t ids[64][VTTS_TEXT_MAX_IDS]; int n[64]; int chunks; } out_t;

static int on_ids(const int32_t *ids, int n, void *user) {
    out_t *o = user;
    if (o->chunks < 64) { memcpy(o->ids[o->chunks], ids, sizeof(int32_t) * (size_t)n); o->n[o->chunks] = n; }
    o->chunks++;
    return 0;
}

static void *slurp(const char *path, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *n = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    char *p = malloc(*n + 1);
    if (fread(p, 1, *n, f) != *n) { free(p); p = NULL; } else p[*n] = 0;
    fclose(f);
    return p;
}

static int same(const out_t *a, const out_t *b) {
    if (a->chunks != b->chunks) return 0;
    for (int c = 0; c < a->chunks && c < 64; c++)
        if (a->n[c] != b->n[c] || memcmp(a->ids[c], b->ids[c], sizeof(int32_t) * (size_t)a->n[c])) return 0;
    return 1;
}

int main(int argc, char **argv) {
    if (argc < 4) return 2;
    size_t mb, lb, tb;
    void *blob = slurp(argv[1], &mb), *lblob = slurp(argv[2], &lb);
    char *texts = slurp(argv[3], &tb);
    static vtts_model m;
    static vtts_lex lex;
    if (!blob || !texts || vtts_init(&m, blob, mb)) return 2;
    int has_lex = lblob && vtts_lex_init(&lex, lblob, lb) == 0;
    vtts_lang lang;
    if (vtts_text_default_lang(vtts_token_set(&m), &lang)) return 2;
    char *lines[256];
    int nl = 0;
    for (char *l = strtok(texts, "\n"); l && nl < 256; l = strtok(NULL, "\n")) if (*l && *l != '#') lines[nl++] = l;
    vtts_text_ws *ws = malloc(sizeof *ws);
    vtts_text_opts o = {.lang = lang, .lex = has_lex ? &lex : NULL};
    static out_t ref, got;
    int fails = 0;
    for (int i = 0; i < nl; i++) {
        memset(ws, 0, sizeof *ws);
        memset(&ref, 0, sizeof ref);
        vtts_text_to_ids_ex(lines[i], ws, &o, on_ids, &ref);
        for (int pat = 0; pat < 3; pat++) { /* junk patterns */
            memset(ws, pat == 0 ? 0xa5 : pat == 1 ? 0xff : 0x01, sizeof *ws);
            memset(&got, 0, sizeof got);
            vtts_text_to_ids_ex(lines[i], ws, &o, on_ids, &got);
            if (!same(&ref, &got)) { printf("FAIL junk %d: %.60s\n", pat, lines[i]); fails++; }
        }
        for (int j = 0; j < nl; j++) { /* after every other text */
            memset(ws, 0, sizeof *ws);
            memset(&got, 0, sizeof got);
            vtts_text_to_ids_ex(lines[j], ws, &o, on_ids, &got);
            memset(&got, 0, sizeof got);
            vtts_text_to_ids_ex(lines[i], ws, &o, on_ids, &got);
            if (!same(&ref, &got)) { printf("FAIL after [%d] %.40s: %.60s\n", j, lines[j], lines[i]); fails++; }
        }
    }
    printf("%s (%d failures, %d texts)\n", fails ? "FAILED" : "ALL PASS", fails, nl);
    return fails ? 1 : 0;
}
