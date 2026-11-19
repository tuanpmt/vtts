/* SPDX-License-Identifier: Apache-2.0 */
/* selftest.c -- SIMD kernels against plain C: random dots, multi-row dots, weights read from the
 * embedded model, both cores at once (internal RAM and PSRAM), and throughput lines. On the
 * ESP32-S3, fusetest also checks the fused ld.ip kernel (memory x cores x interrupts); memtest runs
 * an int8 layer on both cores with weights and outputs in PSRAM. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "vtts_port.h"

/* selftest: both cores run SIMD dots at once, 200 times per row; every repeat must match */
static struct { const int8_t *w, *x; int len; int32_t *out; volatile int bad; int irq_off; } s_pt;
static void partest_rows(int lo, int hi, void *ctx) {
    (void)ctx;
    for (int rep = 0; rep < 200; rep++)
        for (int r = lo; r < hi; r++) {
            int32_t got;
            if (s_pt.irq_off) portDISABLE_INTERRUPTS();
            vtts_dots_s8s8(s_pt.w + (size_t)r * s_pt.len, s_pt.x, s_pt.len, 1, s_pt.len, &got);
            if (s_pt.irq_off) portENABLE_INTERRUPTS();
            if (rep == 0) s_pt.out[r] = got;
            else if (got != s_pt.out[r]) s_pt.bad++;
        }
}

int selftest_run(void) {
    static int8_t va[512] __attribute__((aligned(16))), vb[512] __attribute__((aligned(16)));
    int bad = 0;
    uint32_t r = esp_random();
    printf("selftest: one dot of 16 -> %ld\n", (long)vtts_dot_s8s8(va, vb, 16));
    for (int it = 0; it < 200; it++) {
        int n = 16 * (1 + (int)((r = r * 1664525u + 1013904223u) >> 27));
        for (int i = 0; i < n; i++) {
            va[i] = (int8_t)((r = r * 1664525u + 1013904223u) >> 24);
            vb[i] = (int8_t)((r = r * 1664525u + 1013904223u) >> 24);
            if (va[i] == -128) va[i] = -127;
            if (vb[i] == -128) vb[i] = -127;
        }
        int32_t ref = 0;
        for (int i = 0; i < n; i++) ref += va[i] * vb[i];
        if (vtts_dot_s8s8(va, vb, n) != ref) bad++;
    }
    printf("selftest: %d mismatches in 200 random dots\n", bad);
    for (int it = 0; it < 200; it++) { /* multi-row kernel: odd and even block counts */
        int len = 16 * (1 + (int)((r = r * 1664525u + 1013904223u) >> 27) % 30);
        int rows = 512 / len < 4 ? 512 / len : 4;
        int32_t got[4];
        vtts_dots_s8s8(va, vb, len, rows, len, got);
        for (int t = 0; t < rows; t++) {
            int32_t ref = 0;
            for (int i = 0; i < len; i++) ref += va[i] * vb[t * len + i];
            if (got[t] != ref) bad++;
        }
    }
    printf("selftest: %d mismatches after multi-row dots\n", bad);
    {
        static int8_t xa[32 * 480] __attribute__((aligned(16)));
        static int32_t o32[32];
        int lens2[2] = {160, 480};
        for (int li = 0; li < 2; li++) {
            int64_t t0 = esp_timer_get_time();
            for (int it = 0; it < 500; it++) vtts_dots_s8s8(va, xa, lens2[li], 32, lens2[li], o32);
            int64_t us = esp_timer_get_time() - t0;
            printf("SELFTEST dots%d x32 %.1f MMAC/s\n", lens2[li], 500.0 * 32 * lens2[li] / us);
        }
    }
    { /* the same kernels with weights read straight from the embedded model (flash or PSRAM) */
        const int8_t *wf = (const int8_t *)(((uintptr_t)model_s_start + 15) & ~(uintptr_t)15);
        static int8_t xa2[32 * 480] __attribute__((aligned(16)));
        static int32_t o2[32];
        int bad2 = 0;
        for (int off = 0; off < (int)(model_s_end - model_s_start) - 512; off += 4096 * 3 + 16) {
            vtts_dots_s8s8(wf + off, xa2, 480, 32, 480, o2);
            for (int t = 0; t < 32; t++) {
                int32_t ref = 0;
                for (int i = 0; i < 480; i++) ref += wf[off + i] * xa2[t * 480 + i];
                if (o2[t] != ref) bad2++;
            }
        }
        printf("selftest: %d mismatches with weights in the model blob\n", bad2);
        bad += bad2;
    }
    for (int where = 0; where < 2; where++) { /* both cores at once; internal RAM, then PSRAM */
        static int8_t wi[64 * 480] __attribute__((aligned(16))), xi[480] __attribute__((aligned(16)));
        static int32_t out[64];
        int8_t *w = wi, *x = xi;
        if (where) {
            w = heap_caps_aligned_alloc(16, 64 * 480, MALLOC_CAP_SPIRAM);
            x = heap_caps_aligned_alloc(16, 480, MALLOC_CAP_SPIRAM);
            if (!w || !x) { free(w); free(x); continue; }
        }
        for (int i = 0; i < 64 * 480; i++) w[i] = (int8_t)(((r = r * 1664525u + 1013904223u) >> 24) % 255 - 127);
        for (int i = 0; i < 480; i++) x[i] = (int8_t)(((r = r * 1664525u + 1013904223u) >> 24) % 255 - 127);
        s_pt.w = w; s_pt.x = x; s_pt.len = 480; s_pt.out = out; s_pt.bad = 0;
        vtts_par_run(partest_rows, 64, NULL);
        int wrong = 0;
        for (int t = 0; t < 64; t++) {
            int32_t ref = 0;
            for (int i = 0; i < 480; i++) ref += w[t * 480 + i] * x[i];
            if (out[t] != ref) wrong++;
        }
        printf("selftest: two cores (%s): %d wrong, %d unstable\n", where ? "psram" : "sram", wrong, s_pt.bad);
        bad += wrong + s_pt.bad;
        if (where) { free(w); free(x); }
    }
    int lens[4] = {64, 112, 192, 336};
    for (int li = 0; li < 4; li++) {
        int64_t t0 = esp_timer_get_time();
        volatile int32_t sink = 0;
        for (int it = 0; it < 20000; it++) sink += vtts_dot_s8s8(va, vb, lens[li]);
        int64_t us = esp_timer_get_time() - t0;
        printf("SELFTEST dot%d %.1f MMAC/s\n", lens[li], 20000.0 * lens[li] / us);
    }
    printf("SELFTEST mismatches=%d\n", bad);
    return bad;
}

int fusetest_run(void) {
#if CONFIG_IDF_TARGET_ESP32S3
    extern int vtts_s3_kernel;
    uint32_t r = esp_random();
    int8_t *ws = heap_caps_aligned_alloc(16, 64 * 480, MALLOC_CAP_INTERNAL), *xs = heap_caps_aligned_alloc(16, 480, MALLOC_CAP_INTERNAL);
    int8_t *wp = heap_caps_aligned_alloc(16, 64 * 480, MALLOC_CAP_SPIRAM), *xp = heap_caps_aligned_alloc(16, 480, MALLOC_CAP_SPIRAM);
    static int32_t out[64], ref[64];
    if (!ws || !xs || !wp || !xp) { printf("fusetest: out of memory\n"); return 1; }
    for (int i = 0; i < 64 * 480; i++) ws[i] = wp[i] = (int8_t)(((r = r * 1664525u + 1013904223u) >> 24) % 255 - 127);
    for (int i = 0; i < 480; i++) xs[i] = xp[i] = (int8_t)(((r = r * 1664525u + 1013904223u) >> 24) % 255 - 127);
    for (int t = 0; t < 64; t++) { ref[t] = 0; for (int i = 0; i < 480; i++) ref[t] += ws[t * 480 + i] * xs[i]; }
    for (int k = 0; k < 2; k++)
        for (int mem = 0; mem < 2; mem++)
            for (int cores = 1; cores <= 2; cores++)
                for (int irq = 0; irq < 2; irq++) {
                    vtts_s3_kernel = k;
                    s_pt.w = mem ? wp : ws; s_pt.x = mem ? xp : xs; s_pt.len = 480; s_pt.out = out;
                    s_pt.bad = 0; s_pt.irq_off = irq;
                    int64_t t0 = esp_timer_get_time();
                    if (cores == 2) vtts_par_run(partest_rows, 64, NULL); else partest_rows(0, 64, NULL);
                    int64_t us = esp_timer_get_time() - t0;
                    int wrong = 0;
                    for (int t = 0; t < 64; t++) wrong += out[t] != ref[t];
                    printf("FUSETEST kernel=%s mem=%s cores=%d irq=%s wrong=%d unstable=%d %.0f MMAC/s\n",
                           k ? "fused" : "plain", mem ? "psram" : "sram", cores, irq ? "off" : "on", wrong, s_pt.bad,
                           200.0 * 64 * 480 / us);
                }
    vtts_s3_kernel = 0; s_pt.irq_off = 0;
    free(ws); free(xs); free(wp); free(xp);
    return 0;
#else
    printf("fusetest: ESP32-S3 only\n");
    return 0;
#endif
}


/* memtest: an int8 linear layer split over output channels on both cores, as in synthesis: SIMD
 * dots with weights over ~1.8 MB of PSRAM (cache misses on both cores) and the results stored
 * time-major (y[t][o]) by both cores at once, into PSRAM and then into internal RAM; every value
 * is checked. On the ESP32-S3 the PSRAM case now and then loses a value (about one in 10^6), which
 * is why synthesis stages these outputs in internal RAM there (vtts_set_out_stage); only the
 * internal-RAM case counts as a failure. */
#define MX_L 8
#define MX_C 480
#define MX_T 16
#define MX_PASSES 60
static struct { const int8_t *w, *x; float *y; } s_mx;
static void memtest_rows(int lo, int hi, void *ctx) {
    (void)ctx;
    int32_t got[MX_T];
    for (int o = lo; o < hi; o++) {
        vtts_dots_s8s8(s_mx.w + (size_t)o * MX_C, s_mx.x, MX_C, MX_T, MX_C, got);
        for (int t = 0; t < MX_T; t++) s_mx.y[(size_t)t * MX_C + o] = (float)got[t] * 0.5f;
    }
}

int memtest_run(void) {
    uint32_t r = esp_random();
    int8_t *w = heap_caps_aligned_alloc(16, (size_t)MX_L * MX_C * MX_C, MALLOC_CAP_SPIRAM);
    int8_t *x = heap_caps_aligned_alloc(16, MX_T * MX_C, MALLOC_CAP_SPIRAM);
    int32_t *ref = heap_caps_malloc(sizeof(int32_t) * MX_L * MX_T * MX_C, MALLOC_CAP_SPIRAM);
    float *yp = heap_caps_aligned_alloc(16, sizeof(float) * MX_T * MX_C, MALLOC_CAP_SPIRAM);
    float *ys = heap_caps_aligned_alloc(16, sizeof(float) * MX_T * MX_C, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    int total = 0;
    if (!w || !x || !ref || !yp || !ys) { printf("memtest: out of memory\n"); total = 1; goto done; }
    for (size_t i = 0; i < (size_t)MX_L * MX_C * MX_C; i++) w[i] = (int8_t)(((r = r * 1664525u + 1013904223u) >> 24) % 255 - 127);
    for (int i = 0; i < MX_T * MX_C; i++) x[i] = (int8_t)(((r = r * 1664525u + 1013904223u) >> 24) % 255 - 127);
    for (int l = 0; l < MX_L; l++)
        for (int o = 0; o < MX_C; o++)
            for (int t = 0; t < MX_T; t++) {
                int32_t s = 0;
                const int8_t *wr = w + ((size_t)l * MX_C + o) * MX_C;
                for (int i = 0; i < MX_C; i++) s += wr[i] * x[t * MX_C + i];
                ref[((size_t)l * MX_T + t) * MX_C + o] = s;
            }
    s_mx.x = x;
    for (int mem = 0; mem < 2; mem++) {
        int bad = 0;
        s_mx.y = mem ? ys : yp;
        int64_t t0 = esp_timer_get_time();
        for (int pass = 0; pass < MX_PASSES; pass++)
            for (int l = 0; l < MX_L; l++) {
                s_mx.w = w + (size_t)l * MX_C * MX_C;
                vtts_par_run(memtest_rows, MX_C, NULL);
                for (int i = 0; i < MX_T * MX_C; i++)
                    if (s_mx.y[i] != (float)ref[(size_t)l * MX_T * MX_C + i] * 0.5f) bad++;
            }
        printf("MEMTEST weights=psram y=%s cores=2 wrong=%d of %d (%.1f s)\n", mem ? "sram" : "psram", bad,
               MX_PASSES * MX_L * MX_T * MX_C, (esp_timer_get_time() - t0) / 1e6);
        if (mem) total += bad;
    }
done:
    free(w); free(x); free(ref); free(yp); free(ys);
    return total;
}
