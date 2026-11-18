/* SPDX-License-Identifier: Apache-2.0 */
/* golden_test.c -- compare the C runtime against PyTorch golden fixtures.
 * usage: golden_test MODEL.vtts GOLDEN.bin [min_corr]
 * Exit 0 only if every gate passes. Test code may use malloc. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts.h"

static void *slurp(const char *path, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    *n = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    void *p = malloc(*n);
    if (fread(p, 1, *n, f) != *n) { free(p); p = NULL; }
    fclose(f);
    return p;
}

static double corr(const float *a, const float *b, long n, double *rms_ratio) {
    double sa = 0, sb = 0, saa = 0, sbb = 0, sab = 0;
    for (long i = 0; i < n; i++) {
        sa += a[i]; sb += b[i]; saa += (double)a[i] * a[i]; sbb += (double)b[i] * b[i];
        sab += (double)a[i] * b[i];
    }
    double ma = sa / n, mb = sb / n;
    double va = saa / n - ma * ma, vb = sbb / n - mb * mb, cov = sab / n - ma * mb;
    if (rms_ratio) *rms_ratio = sqrt(saa / n) / (sqrt(sbb / n) + 1e-12);
    if (va <= 1e-20 || vb <= 1e-20) return (va <= 1e-20 && vb <= 1e-20) ? 1.0 : 0.0;
    return cov / sqrt(va * vb);
}

static int corrupt_checks(const uint8_t *blob, size_t n) {
    vtts_model m;
    uint8_t *bad = malloc(n);
    int fails = 0;
    memcpy(bad, blob, n); bad[0] = 'X';
    if (vtts_init(&m, bad, n) >= 0) { puts("FAIL: bad magic accepted"); fails++; }
    memcpy(bad, blob, n); bad[4] = 2;
    if (vtts_init(&m, bad, n) >= 0) { puts("FAIL: bad version accepted"); fails++; }
    if (vtts_init(&m, blob, n / 2) >= 0) { puts("FAIL: truncated file accepted"); fails++; }
    if (vtts_init(&m, blob, 10) >= 0) { puts("FAIL: tiny file accepted"); fails++; }
    free(bad);
    return fails;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s model golden [min_corr]\n", argv[0]); return 2; }
    double min_corr = argc > 3 ? atof(argv[3]) : 0.9999;
    size_t mb_n, gb_n;
    uint8_t *mb = slurp(argv[1], &mb_n), *gb = slurp(argv[2], &gb_n);
    if (!mb || !gb) { puts("FAIL: cannot read inputs"); return 2; }
    vtts_model m;
    int rc = vtts_init(&m, mb, mb_n);
    if (rc) { printf("FAIL: init %d\n", rc); return 1; }
    int fails = corrupt_checks(mb, mb_n);
    if (memcmp(gb, "VGLD", 4)) { puts("FAIL: golden magic"); return 2; }
    uint32_t n_cases;
    memcpy(&n_cases, gb + 4, 4);
    const uint8_t *p = gb + 8;
    for (uint32_t c = 0; c < n_cases; c++) {
        int32_t n; memcpy(&n, p, 4); p += 4;
        const int32_t *ids = (const int32_t *)p; p += 4 * n;
        const float *g_ld = (const float *)p; p += 4 * n;
        const int32_t *g_dur = (const int32_t *)p; p += 4 * n;
        int32_t T, L; memcpy(&T, p, 4); memcpy(&L, p + 4, 4); p += 8;
        const float *g_z = (const float *)p; p += (size_t)4 * L * T;
        int32_t S; memcpy(&S, p, 4); p += 4;
        const float *g_pcm = (const float *)p; p += (size_t)4 * S;

        size_t ab = vtts_arena_bytes(&m, n, T);
        void *arena = malloc(ab);
        int32_t *dur = malloc(4 * (size_t)n);
        float *ld = malloc(4 * (size_t)n), *z = malloc((size_t)4 * L * T), *pcm = malloc((size_t)4 * S);
        long tot = vtts_durations(&m, ids, n, 1.0f, dur, ld, arena, ab);
        int dur_mismatch = 0;
        double ld_err = 0;
        for (int i = 0; i < n; i++) {
            dur_mismatch += dur[i] != g_dur[i];
            ld_err = fmax(ld_err, fabs(ld[i] - g_ld[i]));
        }
        long Tz = vtts_latent(&m, ids, g_dur, n, z, arena, ab);
        double zc = Tz == T ? corr(z, g_z, (long)L * T, NULL) : 0;
        long Sp = vtts_decode(&m, g_z, T, pcm, arena, ab);
        double rr = 0, pc = Sp == S ? corr(pcm, g_pcm, S, &rr) : 0;
        long Se = vtts_synthesize(&m, ids, n, 1.0f, pcm, S, arena, ab);
        int ok = tot == T && dur_mismatch == 0 && zc >= min_corr && pc >= min_corr && Se == S &&
                 rr > 0.8 && rr < 1.25;
        printf("case %u: n=%d T=%d dur_mismatch=%d max|dlogdur|=%.2e z_corr=%.6f pcm_corr=%.6f rms=%.4f arena=%zu %s\n",
               c, n, T, dur_mismatch, ld_err, zc, pc, rr, ab, ok ? "PASS" : "FAIL");
        fails += !ok;
        free(arena); free(dur); free(ld); free(z); free(pcm);
    }
    free(mb); free(gb);
    printf("%s (%d failures)\n", fails ? "FAILED" : "ALL PASS", fails);
    return fails ? 1 : 0;
}
