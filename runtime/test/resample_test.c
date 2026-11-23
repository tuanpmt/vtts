/* SPDX-License-Identifier: Apache-2.0 */
/* resample_test.c -- streaming sample-rate converter (vtts_resample.h): chunked equals one-shot,
 * output length, passband gain and phase, alias rejection, noise, DC and clipping.
 * usage: resample_test [-v]   (exit status 0 when every check passes) */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vtts_resample.h"

static int fails, verbose;

static void check(int ok, const char *what, double v) {
    if (!ok || verbose) printf("%s %s: %.3f\n", ok ? "ok  " : "FAIL", what, v);
    if (!ok) fails++;
}

/* Convert all of in (n samples) in chunks of random size (1..max_chunk, or all at once with 0). */
static long run(int in_rate, int out_rate, const int16_t *in, long n, int max_chunk, int16_t *out, unsigned seed) {
    static vtts_resampler r;
    if (vtts_resample_init(&r, in_rate, out_rate)) return -1;
    long m = 0;
    for (long i = 0; i < n;) {
        seed = seed * 1664525u + 1013904223u;
        int c = max_chunk ? 1 + (int)((seed >> 8) % (unsigned)max_chunk) : (int)(n - i);
        if (c > n - i) c = (int)(n - i);
        int bound = vtts_resample_max_out(&r, c), got = vtts_resample_process(&r, in + i, c, out + m);
        if (got > bound) { printf("FAIL max_out %d < %d\n", bound, got); fails++; }
        m += got;
        i += c;
    }
    int bound = vtts_resample_max_out(&r, 0), got = vtts_resample_flush(&r, out + m);
    if (got > bound) { printf("FAIL flush max_out %d < %d\n", bound, got); fails++; }
    return m + got;
}

/* Least-squares fit of a*sin + b*cos at frequency f (Hz) over out[lo, hi): amplitude, phase, residual rms */
static void fit(const int16_t *y, long lo, long hi, double f, int rate, double *amp, double *phase, double *res) {
    double ss = 0, sc = 0, cc = 0, ys = 0, yc = 0;
    for (long j = lo; j < hi; j++) {
        double w = 2 * M_PI * f * j / rate, s = sin(w), c = cos(w);
        ss += s * s; sc += s * c; cc += c * c; ys += y[j] * s; yc += y[j] * c;
    }
    double det = ss * cc - sc * sc, a = (ys * cc - yc * sc) / det, b = (yc * ss - ys * sc) / det, e = 0;
    for (long j = lo; j < hi; j++) {
        double w = 2 * M_PI * f * j / rate, d = y[j] - a * sin(w) - b * cos(w);
        e += d * d;
    }
    *amp = sqrt(a * a + b * b);
    *phase = atan2(b, a);
    *res = sqrt(e / (double)(hi - lo));
}

static double rms(const int16_t *y, long lo, long hi) {
    double e = 0;
    for (long j = lo; j < hi; j++) e += (double)y[j] * y[j];
    return sqrt(e / (double)(hi - lo));
}

int main(int argc, char **argv) {
    verbose = argc > 1 && !strcmp(argv[1], "-v");
    enum { N = 2 * 22050, CAP = 4 * N + 64 };
    int16_t *in = malloc(sizeof(int16_t) * N), *a = malloc(sizeof(int16_t) * CAP), *b = malloc(sizeof(int16_t) * CAP);
    char what[128];
    static const int pairs[][2] = {{22050, 16000}, {16000, 22050}, {22050, 44100}, {24000, 16000}, {22050, 11025}};
    const int np = (int)(sizeof pairs / sizeof pairs[0]);

    /* chunked == one-shot, and the length is ceil(n * out / in) */
    unsigned seed = 1;
    for (long i = 0; i < N; i++) in[i] = (int16_t)((int)((seed = seed * 1103515245u + 12345u) >> 16) % 20000 - 10000);
    for (int p = 0; p < np; p++) {
        int ir = pairs[p][0], or_ = pairs[p][1];
        long ma = run(ir, or_, in, N, 0, a, 0), want = (long)(((long long)N * or_ + ir - 1) / ir);
        snprintf(what, sizeof what, "%d->%d length %ld (want %ld)", ir, or_, ma, want);
        check(ma == want, what, (double)ma);
        for (int mc = 1; mc <= 700; mc = mc * 3 + 1) {
            long mb = run(ir, or_, in, N, mc, b, (unsigned)mc);
            snprintf(what, sizeof what, "%d->%d chunks <= %d equal one-shot", ir, or_, mc);
            check(mb == ma && !memcmp(a, b, sizeof(int16_t) * (size_t)ma), what, (double)mb);
        }
    }
    vtts_resampler r;
    check(vtts_resample_init(&r, 22050, 10000) == -1, "22050->10000 refused (below 1/2)", 0);
    check(vtts_resample_init(&r, 8000, 48000) == -1, "8000->48000 refused (above 4)", 0);
    check(vtts_resample_init(&r, 22050, 22050) == 0 && vtts_resample_process(&r, in, 100, a) == 100 &&
              !memcmp(a, in, 200) && vtts_resample_flush(&r, a) == 0, "equal rates copy", 0);

    /* 22050 -> 16000: passband gain and phase (output j is the input at time j * 22050 / 16000) */
    const int IR = 22050, OR = 16000;
    static const double pass[] = {100, 440, 1000, 2000, 3000, 4000, 5000, 6000, 6500, 6800};
    for (unsigned t = 0; t < sizeof pass / sizeof pass[0]; t++) {
        for (long i = 0; i < N; i++) in[i] = (int16_t)lrint(10000.0 * sin(2 * M_PI * pass[t] * i / IR));
        long m = run(IR, OR, in, N, 300, a, 7);
        double amp, ph, res;
        fit(a, 200, m - 200, pass[t], OR, &amp, &ph, &res);
        double g = 20 * log10(amp / 10000.0);
        snprintf(what, sizeof what, "22050->16000 gain at %.0f Hz (dB)", pass[t]);
        check(fabs(g) < 0.1, what, g);
        snprintf(what, sizeof what, "22050->16000 phase at %.0f Hz (rad)", pass[t]);
        check(fabs(ph) < 1e-3, what, ph);
        if (pass[t] == 1000) {
            double snr = 20 * log10(amp / sqrt(2) / res);
            check(snr > 80, "22050->16000 1 kHz SNR (dB)", snr);
        }
    }
    /* tones above the output Nyquist frequency must not come back as aliases */
    static const double stop[] = {8600, 9000, 10000, 11000};
    for (unsigned t = 0; t < sizeof stop / sizeof stop[0]; t++) {
        for (long i = 0; i < N; i++) in[i] = (int16_t)lrint(10000.0 * sin(2 * M_PI * stop[t] * i / IR));
        long m = run(IR, OR, in, N, 300, a, 9);
        double lvl = 20 * log10(rms(a, 200, m - 200) / (10000.0 / sqrt(2)));
        snprintf(what, sizeof what, "22050->16000 alias of %.0f Hz (dB)", stop[t]);
        check(lvl < -70, what, lvl);
    }
    /* 16000 -> 22050 (upsampling): passband up to 7 kHz and the image band stays empty */
    for (long i = 0; i < N; i++) in[i] = (int16_t)lrint(10000.0 * sin(2 * M_PI * 3000.0 * i / OR));
    {
        long m = run(OR, IR, in, N, 300, a, 11);
        double amp, ph, res;
        fit(a, 300, m - 300, 3000.0, IR, &amp, &ph, &res);
        check(fabs(20 * log10(amp / 10000.0)) < 0.1, "16000->22050 gain at 3 kHz (dB)", 20 * log10(amp / 10000.0));
        check(20 * log10(amp / sqrt(2) / res) > 75, "16000->22050 3 kHz SNR (dB)", 20 * log10(amp / sqrt(2) / res));
    }
    /* DC passes unchanged; full scale clips instead of wrapping */
    for (long i = 0; i < N; i++) in[i] = 1000;
    {
        long m = run(IR, OR, in, N, 300, a, 13);
        int worst = 0;
        for (long j = 100; j < m - 100; j++) worst = abs(a[j] - 1000) > worst ? abs(a[j] - 1000) : worst;
        check(worst <= 1, "22050->16000 DC error (LSB)", worst);
    }
    /* full scale clips instead of wrapping: the middle of each half period keeps its sign */
    for (long i = 0; i < N; i++) in[i] = (i / 37) & 1 ? 32767 : -32768;
    {
        long m = run(IR, OR, in, N, 300, a, 15);
        int wrapped = 0;
        for (long h = 2; (h * 37 + 18) * OR / IR < m - 100; h++) {
            long j = (long)lrint((h * 37 + 18.0) * OR / IR);
            wrapped += (h & 1) ? a[j] < 30000 : a[j] > -30000;
        }
        check(!wrapped, "22050->16000 full-scale square: no wrap-around", wrapped);
    }
    free(in); free(a); free(b);
    printf("resample_test: %s (%d failed)\n", fails ? "FAIL" : "ok", fails);
    return fails != 0;
}
