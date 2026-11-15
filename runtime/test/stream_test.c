/* SPDX-License-Identifier: Apache-2.0 */
/* stream_test.c -- chunked synthesis must equal whole-utterance synthesis.
 * usage: stream_test MODEL.vtts GOLDEN.bin   (uses the ids of every golden case) */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts.h"

typedef struct { float *buf; long n, cap; } sink_t;

static int collect(const float *pcm, long n, void *user) {
    sink_t *s = user;
    if (s->n + n > s->cap) return -1;
    memcpy(s->buf + s->n, pcm, sizeof(float) * (size_t)n);
    s->n += n;
    return 0;
}

static void *slurp(const char *path, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *n = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    void *p = malloc(*n);
    if (fread(p, 1, *n, f) != *n) { free(p); p = NULL; }
    fclose(f);
    return p;
}

int main(int argc, char **argv) {
    if (argc < 3) return 2;
    size_t mb_n, gb_n;
    uint8_t *mb = slurp(argv[1], &mb_n), *gb = slurp(argv[2], &gb_n);
    vtts_model m;
    if (!mb || !gb || vtts_init(&m, mb, mb_n)) { puts("FAIL: inputs"); return 2; }
    uint32_t n_cases; memcpy(&n_cases, gb + 4, 4);
    const uint8_t *p = gb + 8;
    int fails = 0;
    for (uint32_t c = 0; c < n_cases; c++) {
        int32_t n; memcpy(&n, p, 4); p += 4;
        const int32_t *ids = (const int32_t *)p; p += 12 * (size_t)n;
        int32_t T, L; memcpy(&T, p, 4); memcpy(&L, p + 4, 4); p += 8 + (size_t)4 * L * T;
        int32_t S; memcpy(&S, p, 4); p += 4 + (size_t)4 * S;

        size_t whole_ab = vtts_arena_bytes(&m, n, T);
        void *wa = malloc(whole_ab);
        float *ref = malloc(sizeof(float) * (size_t)S);
        long sr = vtts_synthesize(&m, ids, n, 1.0f, ref, S, wa, whole_ab);
        int chunks[] = {1, 7, 64, 64}, firsts[] = {1, 7, 64, 5};
        for (int k = 0; k < 4; k++) {
            size_t ab = vtts_stream_arena_bytes(&m, n, chunks[k]);
            void *sa = malloc(ab);
            sink_t sink = {malloc(sizeof(float) * (size_t)S), 0, S};
            long got = vtts_synthesize_stream_ex(&m, ids, n, 1.0f, firsts[k], chunks[k], collect, &sink, sa, ab);
            if (m.decoder != VTTS_DEC_VOCOS) {
                int ok = got == VTTS_ERR_ARGS;
                printf("case %u chunk %d: non-vocos decoder -> %ld %s\n", c, chunks[k], got, ok ? "PASS" : "FAIL");
                fails += !ok;
            } else {
                double md = 0;
                for (long i = 0; i < sink.n && i < sr; i++) md = fmax(md, fabs(sink.buf[i] - ref[i]));
                int ok = got == sr && sink.n == sr && md <= 1e-6 && (T < 200 || ab < whole_ab / 2);
                printf("case %u chunk %d: samples %ld/%ld max|diff|=%.2e arena %zu vs whole %zu %s\n",
                       c, chunks[k], sink.n, sr, md, ab, whole_ab, ok ? "PASS" : "FAIL");
                fails += !ok;
            }
            free(sa); free(sink.buf);
        }
        free(wa); free(ref);
    }
    if (m.decoder == VTTS_DEC_VOCOS && argc > 3) {
        size_t cap = (size_t)atol(argv[3]);
        size_t worst = vtts_stream_arena_bytes(&m, 320, 32);
        int ok = worst <= cap;
        printf("stream arena (320 ids, chunk 32): %zu bytes, limit %zu %s\n", worst, cap, ok ? "PASS" : "FAIL");
        fails += !ok;
    }
    printf("%s (%d failures)\n", fails ? "FAILED" : "ALL PASS", fails);
    return fails ? 1 : 0;
}
