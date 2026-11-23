/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_resample.c -- streaming band-limited sample-rate conversion of int16 PCM (vtts_resample.h). */
#include "vtts_resample.h"

#include <limits.h>
#include <math.h>
#include <string.h>

/* Kaiser window shape and the cutoff as a fraction of the lower Nyquist frequency. 22050 -> 16000:
 * 0-6.8 kHz within 0.06 dB, aliases of 8.6 kHz and above about 79 dB down, 1 kHz SNR 86 dB, about 60
 * taps per output sample (runtime/test/resample_test.c measures these). */
#define RS_BETA 8.2
#define RS_ROLLOFF 0.95

static double bessel_i0(double x) {
    double sum = 1.0, term = 1.0, q = x * x / 4.0;
    for (int k = 1; k < 64 && term > 1e-12 * sum; k++) {
        term *= q / ((double)k * k);
        sum += term;
    }
    return sum;
}

static int gcd(int a, int b) {
    while (b) { int t = a % b; a = b; b = t; }
    return a;
}

int vtts_resample_init(vtts_resampler *r, int in_rate, int out_rate) {
    memset(r, 0, sizeof *r);
    if (in_rate <= 0 || out_rate <= 0 || 2LL * out_rate < in_rate || out_rate > 4LL * in_rate) return -1;
    int g = gcd(in_rate, out_rate);
    r->in_rate = in_rate / g;
    r->out_rate = out_rate / g;
    double ratio = (double)out_rate / in_rate;
    r->fc = (float)(RS_ROLLOFF * (ratio < 1.0 ? ratio : 1.0));
    r->step = r->fc * VTTS_RS_PHASES;
    r->half = (int)ceil(VTTS_RS_ZEROS / r->fc);
    if (r->half > VTTS_RS_MAX_HALF) return -1;
    /* k[i] = fc * sinc(u) * kaiser(u / ZEROS) at u = i / PHASES zero crossings; the fc factor keeps
     * unit gain at DC. Entries past the last zero crossing are 0 (interpolation reads one ahead). */
    const int nk = VTTS_RS_ZEROS * VTTS_RS_PHASES;
    const double i0b = bessel_i0(RS_BETA), pi = 3.14159265358979323846;
    for (int i = 0; i <= nk + 1; i++) {
        double u = (double)i / VTTS_RS_PHASES, v = u / VTTS_RS_ZEROS, s = i ? sin(pi * u) / (pi * u) : 1.0;
        r->k[i] = i < nk ? (float)(r->fc * s * bessel_i0(RS_BETA * sqrt(1.0 - v * v)) / i0b) : 0.0f;
    }
    vtts_resample_reset(r);
    return 0;
}

void vtts_resample_reset(vtts_resampler *r) {
    /* half - 1 zeros before the first sample: output 0 sits on input 0 with all its left taps present */
    r->n = r->pos = r->half > 0 ? r->half - 1 : 0;
    memset(r->x, 0, sizeof r->x);
    r->frac = 0;
    r->n_in = r->n_out = 0;
}

int vtts_resample_max_out(const vtts_resampler *r, int n_in) {
    if (r->in_rate == r->out_rate) return n_in;
    return (int)((long long)(n_in + r->half + 1) * r->out_rate / r->in_rate) + 2;
}

static inline int16_t to_s16(float v) {
    long q = lrintf(v);
    return (int16_t)(q > 32767 ? 32767 : q < -32768 ? -32768 : q);
}

/* Write the output samples whose taps are all in x (at most until n_out reaches limit). */
static int produce(vtts_resampler *r, int16_t *out, long long limit) {
    const int half = r->half, nk = VTTS_RS_ZEROS * VTTS_RS_PHASES;
    const float step = r->step, inv_out = 1.0f / (float)r->out_rate;
    const float *k = r->k;
    int m = 0;
    while (r->pos + half < r->n && r->n_out < limit) {
        const float f = (float)r->frac * inv_out; /* output time = pos + f, 0 <= f < 1 */
        const float *x = r->x + r->pos;
        float acc = 0.0f;
        /* left taps x[pos - j] at distance f + j, right taps x[pos + 1 + j] at distance 1 - f + j */
        float ul = f * step, ur = (1.0f - f) * step;
        for (int j = 0; j < half; j++, ul += step, ur += step) {
            int il = (int)ul, ir = (int)ur;
            if (il < nk) acc += x[-j] * (k[il] + (ul - (float)il) * (k[il + 1] - k[il]));
            if (ir < nk) acc += x[1 + j] * (k[ir] + (ur - (float)ir) * (k[ir + 1] - k[ir]));
        }
        out[m++] = to_s16(acc);
        r->n_out++;
        r->frac += r->in_rate;
        while (r->frac >= r->out_rate) { r->frac -= r->out_rate; r->pos++; }
    }
    return m;
}

/* Drop the history no future output needs (everything left of its leftmost tap). */
static void discard(vtts_resampler *r) {
    int drop = r->pos - r->half + 1;
    if (drop <= 0) return;
    if (drop > r->n) drop = r->n;
    memmove(r->x, r->x + drop, sizeof(float) * (size_t)(r->n - drop));
    r->n -= drop;
    r->pos -= drop;
}

int vtts_resample_process(vtts_resampler *r, const int16_t *in, int n_in, int16_t *out) {
    if (r->in_rate == r->out_rate) {
        if (n_in > 0) memcpy(out, in, sizeof(int16_t) * (size_t)n_in);
        return n_in > 0 ? n_in : 0;
    }
    int m = 0;
    while (n_in > 0) {
        int take = VTTS_RS_BUF - r->n;
        if (take > n_in) take = n_in;
        for (int i = 0; i < take; i++) r->x[r->n + i] = (float)in[i];
        r->n += take;
        r->n_in += take;
        in += take;
        n_in -= take;
        m += produce(r, out + m, LLONG_MAX);
        discard(r);
    }
    return m;
}

int vtts_resample_flush(vtts_resampler *r, int16_t *out) {
    if (r->in_rate == r->out_rate) return 0;
    const long long target = (r->n_in * r->out_rate + r->in_rate - 1) / r->in_rate;
    int m = 0;
    while (r->n_out < target) {
        int add = VTTS_RS_BUF - r->n;
        if (add > r->half + 1) add = r->half + 1;
        memset(r->x + r->n, 0, sizeof(float) * (size_t)add);
        r->n += add;
        m += produce(r, out + m, target);
        discard(r);
    }
    return m;
}
