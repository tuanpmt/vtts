/* SPDX-License-Identifier: Apache-2.0 */
/* say_parity.c -- the firmware's text -> PCM path must equal the host render of the whole text.
 *
 * Reference ("host"): the text front-end's chunks, each through vtts_synthesize, joined with
 * VTTS_CHUNK_GAP_MS of silence between chunks (tools/vtts_say, the Python renderers).
 * Firmware path ("fw"): the same chunks through vtts_synthesize_stream_ex with the firmware's
 * schedule (a small first chunk for the first sentence only, then the chunk cap) and the same
 * silence between chunks (firmware/esp32/main/synth.c on_ids).
 * Both are compared as int16 (the firmware's lrintf rounding), sample by sample.
 *
 * usage: say_parity MODEL.vtts LEX.bin TEXTS.txt [--first N] [--chunk N] [--old] [--max-diff N] [--stage BYTES]
 *   TEXTS.txt: one text per line ('#' lines skipped). --old emulates the v0.4.0 firmware (a gap
 *   after every chunk, the last one included) against the v0.4.0 vtts_say (no gap at all).
 *   --poison fills both arenas with junk (different on each side) before every synthesis.
 *   --stage runs the firmware path with the int8 output staging of the ESP32-S3 (vtts_set_out_stage).
 *   Exit 1 when a text's max |diff| exceeds --max-diff (int16 LSB, default 0). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts.h"
#include "vtts_text.h"

typedef struct { int16_t *x; long n, cap; } buf_t;
static void *g_stage; /* --stage: only the firmware path stages, so the two paths differ in it */
static size_t g_stage_n;
static int g_poison;
static void *g_fast; /* --fast: the ESP32's internal-RAM scratch (vtts_set_fast_scratch) on the firmware path */
static size_t g_fast_n; /* --poison: fill the arenas with junk before every synthesis */

static void push(buf_t *b, const float *pcm, long n) {
    if (b->n + n > b->cap) {
        b->cap = (b->n + n) * 2;
        b->x = realloc(b->x, sizeof(int16_t) * (size_t)b->cap);
    }
    for (long i = 0; i < n; i++) {
        float v = pcm[i] > 1.0f ? 1.0f : pcm[i] < -1.0f ? -1.0f : pcm[i];
        b->x[b->n++] = (int16_t)lrintf(v * 32767.0f);
    }
}

static void push_zeros(buf_t *b, long n) {
    static const float z[512];
    for (long i = 0; i < n; i += 512) push(b, z, n - i < 512 ? n - i : 512);
}

typedef struct {
    const vtts_model *m;
    int first, chunk, old, n_chunks;
    buf_t host, fw;
    void *sa;
    size_t sab;
    int err;
} ctx_t;

static int on_pcm(const float *pcm, long n, void *user) {
    push(&((ctx_t *)user)->fw, pcm, n);
    return 0;
}

static int on_ids(const int32_t *ids, int n, void *user) {
    ctx_t *c = user;
    const vtts_model *m = c->m;
    long gap = (long)(VTTS_CHUNK_GAP_MS * (long)m->sample_rate / 1000);
    /* host: whole chunk at once */
    long max_frames = (long)n * m->max_duration;
    size_t ab = vtts_arena_bytes(m, n, max_frames);
    void *arena = malloc(ab);
    if (g_poison && arena) memset(arena, 0x5a, ab); /* --poison: stale arena contents must not matter */
    float *pcm = malloc(sizeof(float) * (size_t)(max_frames * m->hop));
    if (!c->old && c->n_chunks) push_zeros(&c->host, gap);
    vtts_set_out_stage(NULL, 0);
    vtts_set_fast_scratch(NULL, 0);
    long s = vtts_synthesize(m, ids, n, 1.0f, pcm, max_frames * m->hop, arena, ab);
    if (s < 0) { c->err = (int)s; free(arena); free(pcm); return 1; }
    push(&c->host, pcm, s);
    free(arena);
    free(pcm);
    /* firmware: streaming, small first chunk only at the start of the utterance */
    int first = c->fw.n == 0 && c->first < c->chunk ? c->first : c->chunk;
    if (!c->old && c->n_chunks) push_zeros(&c->fw, gap);
    vtts_set_out_stage(g_stage, g_stage_n);
    if (g_poison) {
        for (size_t i = 0; i < c->sab; i++) ((uint8_t *)c->sa)[i] = (uint8_t)(rand() & 0xff);
        for (size_t i = 0; i < g_fast_n; i++) ((uint8_t *)g_fast)[i] = (uint8_t)(rand() & 0xff);
    }
    vtts_set_fast_scratch(g_fast, g_fast_n);
    long t = vtts_synthesize_stream_ex(m, ids, n, 1.0f, first, c->chunk, on_pcm, c, c->sa, c->sab);
    if (t < 0) { c->err = (int)t; return 1; }
    if (c->old) push_zeros(&c->fw, gap);
    c->n_chunks++;
    return 0;
}

static void *slurp(const char *path, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *n = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    void *p = malloc(*n ? *n : 1);
    if (fread(p, 1, *n, f) != *n) { free(p); p = NULL; }
    fclose(f);
    return p;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s MODEL.vtts LEX.bin TEXTS.txt [--first N] [--chunk N] [--old] [--max-diff N]\n", argv[0]);
        return 2;
    }
    int first = 12, chunk = 128, old = 0, max_ok = 0, verbose = 0;
    for (int i = 4; i < argc; i++) {
        if (!strcmp(argv[i], "--first") && i + 1 < argc) first = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--chunk") && i + 1 < argc) chunk = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--max-diff") && i + 1 < argc) max_ok = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--old")) old = 1;
        else if (!strcmp(argv[i], "--poison")) g_poison = 1;
        else if (!strcmp(argv[i], "--fast") && i + 1 < argc) {
            g_fast_n = (size_t)atol(argv[++i]);
            g_fast = malloc(g_fast_n);
        }
        else if (!strcmp(argv[i], "--stage") && i + 1 < argc) { /* stage int8 outputs in a buffer of N bytes */
            g_stage_n = (size_t)atol(argv[++i]);
            g_stage = malloc(g_stage_n);
        }
        else if (!strcmp(argv[i], "-v")) verbose = 1;
    }
    size_t mb, lb, tb;
    void *blob = slurp(argv[1], &mb), *lblob = slurp(argv[2], &lb);
    char *texts = slurp(argv[3], &tb);
    static vtts_model m;
    static vtts_lex lex;
    if (!blob || !texts || vtts_init(&m, blob, mb)) { puts("FAIL: inputs"); return 2; }
    int has_lex = lblob && vtts_lex_init(&lex, lblob, lb) == 0;
    vtts_lang lang;
    if (vtts_text_default_lang(vtts_token_set(&m), &lang)) { puts("FAIL: no text mode"); return 2; }
    texts = realloc(texts, tb + 1);
    texts[tb] = 0;
    vtts_text_ws *ws = malloc(sizeof *ws);
    ctx_t c = {.m = &m, .first = first, .chunk = chunk, .old = old};
    c.sab = vtts_stream_arena_bytes(&m, VTTS_TEXT_MAX_IDS, chunk);
    c.sa = malloc(c.sab);
    printf("model %s first %d chunk %d stream arena %zu%s\n", argv[1], first, chunk, c.sab, old ? " (v0.4.0 gaps)" : "");
    int fails = 0, k = 0;
    for (char *line = strtok(texts, "\n"); line; line = strtok(NULL, "\n")) {
        if (!*line || *line == '#') continue;
        vtts_text_opts o = {.lang = lang, .lex = has_lex ? &lex : NULL};
        c.host.n = c.fw.n = 0;
        c.n_chunks = 0;
        c.err = 0;
        int chunks = vtts_text_to_ids_ex(line, ws, &o, on_ids, &c);
        if (c.err) { printf("[%d] synth error %d\n", k, c.err); fails++; continue; }
        long n = c.host.n < c.fw.n ? c.host.n : c.fw.n;
        double sxy = 0, sxx = 0, syy = 0, sdd = 0;
        int md = 0;
        for (long i = 0; i < n; i++) {
            double x = c.host.x[i], y = c.fw.x[i], d = x - y;
            sxy += x * y; sxx += x * x; syy += y * y; sdd += d * d;
            if (fabs(d) > md) md = (int)fabs(d);
            if (verbose && fabs(d) > 8 && (i == 0 || fabs((double)c.host.x[i - 1] - c.fw.x[i - 1]) <= 8))
                printf("    diff from sample %ld (frame %ld): %d\n", i, i / m.hop, (int)d);
        }
        double corr = sxx > 0 && syy > 0 ? sxy / sqrt(sxx * syy) : 0;
        int ok = c.host.n == c.fw.n && md <= max_ok;
        printf("[%d] chunks %d host %ld fw %ld max|diff| %d rms %.2f corr %.6f %s  %.60s\n", k, chunks, c.host.n, c.fw.n,
               md, n ? sqrt(sdd / n) : 0.0, corr, ok ? "PASS" : "FAIL", line);
        fails += !ok;
        k++;
    }
    printf("%s (%d failures)\n", fails ? "FAILED" : "ALL PASS", fails);
    free(c.sa); free(ws); free(blob); free(lblob); free(texts); free(c.host.x); free(c.fw.x);
    return fails ? 1 : 0;
}
