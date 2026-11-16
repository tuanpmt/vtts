/* SPDX-License-Identifier: Apache-2.0 */
/* vtts_synth.c -- fp32 reference graph for the student (mirrors src/vtts/student/model.py).
 *
 * All buffers come from a bump arena. Every stage can run in "dry" mode, where it
 * only counts the bytes it would allocate; vtts_arena_bytes() uses that, so the
 * size estimate can never drift from the real allocations.
 */
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "vtts.h"

#ifndef M_PI /* strict C99 headers (glibc) do not define it */
#define M_PI 3.14159265358979323846
#endif

#ifndef VTTS_ACT_MAX
#define VTTS_ACT_MAX 127 /* int8 activations, one scale per frame (pcm corr >= 0.999 vs fp32) */
#endif
#ifndef VTTS_BLOCK
#define VTTS_BLOCK 16      /* frames per ConvNeXt MLP block */
#endif
#ifndef VTTS_HEAD_BLOCK
#define VTTS_HEAD_BLOCK 8  /* frames per head block */
#endif

/* ---------------- optional profiling (compile with -DVTTS_PROFILE) ---------------- */
#ifdef VTTS_PROFILE
int64_t vtts_now_us(void);
int64_t vtts_prof_us[8];
const char *const vtts_prof_names[8] = {"durations", "tokens", "acoustic", "voc_pre_dw_ln",
                                        "voc_mlp", "voc_head", "istft", "other"};
#define PROF_T0() int64_t _pt = vtts_now_us()
#define PROF_ADD(i) do { int64_t _n = vtts_now_us(); vtts_prof_us[i] += _n - _pt; _pt = _n; } while (0)
#else
#define PROF_T0() (void)0
#define PROF_ADD(i) (void)0
#endif

typedef struct {
    uint8_t *base;
    size_t cap, used, peak;
    int dry, oom;
} arena_t;

static void *alloc(arena_t *a, size_t n_floats) {
    size_t bytes = (n_floats * sizeof(float) + 15u) & ~(size_t)15u;
    void *p = NULL;
    if (!a->dry) {
        if (a->used + bytes > a->cap) { a->oom = 1; return NULL; }
        p = a->base + a->used;
    }
    a->used += bytes;
    if (a->used > a->peak) a->peak = a->used;
    return p;
}

static const float *W(const vtts_model *m, const char *fmt, ...) {
    char name[64];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(name, sizeof(name), fmt, ap);
    va_end(ap);
    const vtts_tensor *t = vtts_find(m, name);
    return (t && t->dtype == 0) ? (const float *)t->data : NULL;
}

/* ---------------- ops (channel-major [C, T]) ---------------- */

#include "vtts_port.h"

/* y[co, t] = b[co] + sum_ci,k w[co, ci, k] * x[ci, t + k*dil - pad]  (same length) */
typedef struct { const float *x, *w, *b; float *y; int ci, T, K, dil; } fconv_t;

static void conv1d_rows(int lo, int hi, void *arg) {
    const fconv_t *j = arg;
    int ci = j->ci, T = j->T, K = j->K, dil = j->dil, pad = dil * (K - 1) / 2;
    for (int o = lo; o < hi; o++) {
        float *yo = j->y + (size_t)o * T;
        for (int t = 0; t < T; t++) yo[t] = j->b ? j->b[o] : 0.0f;
        for (int i = 0; i < ci; i++) {
            const float *xi = j->x + (size_t)i * T;
            const float *wk = j->w + ((size_t)o * ci + i) * K;
            for (int k = 0; k < K; k++) {
                int sh = k * dil - pad;
                float wv = wk[k];
                int t0 = sh < 0 ? -sh : 0, t1 = sh > 0 ? T - sh : T;
                for (int t = t0; t < t1; t++) yo[t] += wv * xi[t + sh];
            }
        }
    }
}

static void conv1d(const float *x, int ci, int T, const float *w, const float *b, int co, int K,
                   int dil, float *y) {
    fconv_t j = {x, w, b, y, ci, T, K, dil};
    vtts_par_run(conv1d_rows, co, &j);
}

/* depthwise: w[c, 1, K] */
static void dwconv_rows(int lo, int hi, void *arg) {
    const fconv_t *j = arg;
    int T = j->T, K = j->K, pad = (K - 1) / 2;
    for (int c = lo; c < hi; c++) {
        const float *xc = j->x + (size_t)c * T;
        float *yc = j->y + (size_t)c * T;
        for (int t = 0; t < T; t++) {
            float s = j->b ? j->b[c] : 0.0f;
            for (int k = 0; k < K; k++) {
                int tt = t + k - pad;
                if (tt >= 0 && tt < T) s += j->w[(size_t)c * K + k] * xc[tt];
            }
            yc[t] = s;
        }
    }
}

static void dwconv1d(const float *x, int C, int T, const float *w, const float *b, int K, float *y) {
    fconv_t j = {x, w, b, y, C, T, K, 1};
    vtts_par_run(dwconv_rows, C, &j);
}

/* ConvTranspose1d: w[ci, co, K], stride s, padding p; out length T*s when K = 2s, p = s/2 */
static void convT1d(const float *x, int ci, int T, const float *w, const float *b, int co, int K,
                    int s, int p, float *y, int Tout) {
    for (int o = 0; o < co; o++)
        for (int t = 0; t < Tout; t++) y[(size_t)o * Tout + t] = b ? b[o] : 0.0f;
    for (int i = 0; i < ci; i++) {
        const float *xi = x + (size_t)i * T;
        for (int o = 0; o < co; o++) {
            const float *wk = w + ((size_t)i * co + o) * K;
            float *yo = y + (size_t)o * Tout;
            for (int t = 0; t < T; t++) {
                float xv = xi[t];
                int base = t * s - p;
                for (int k = 0; k < K; k++) {
                    int oi = base + k;
                    if (oi >= 0 && oi < Tout) yo[oi] += wk[k] * xv;
                }
            }
        }
    }
}

/* y[o, t] = b[o] + sum_i w[o, i] x[i, t] */
static void linear_cm(const float *x, int ci, int T, const float *w, const float *b, int co, float *y) {
    conv1d(x, ci, T, w, b, co, 1, 1, y);
}

/* LayerNorm over channels for each time step, in place */
typedef struct { float *x; const float *g, *b; int C, T; } ln_t;

static void layernorm_cols(int lo, int hi, void *arg) {
    const ln_t *j = arg;
    float *x = j->x;
    int C = j->C, T = j->T;
    for (int t = lo; t < hi; t++) {
        float mean = 0.0f, var = 0.0f;
        for (int c = 0; c < C; c++) mean += x[(size_t)c * T + t];
        mean /= (float)C;
        for (int c = 0; c < C; c++) {
            float d = x[(size_t)c * T + t] - mean;
            var += d * d;
        }
        var /= (float)C;
        float inv = 1.0f / sqrtf(var + 1e-5f);
        for (int c = 0; c < C; c++) {
            float *v = &x[(size_t)c * T + t];
            *v = (*v - mean) * inv * j->g[c] + j->b[c];
        }
    }
}

static void layernorm_cm(float *x, int C, int T, const float *g, const float *b) {
    ln_t j = {x, g, b, C, T};
    vtts_par_run(layernorm_cols, T, &j);
}

static void lrelu(float *x, size_t n, float slope) {
    for (size_t i = 0; i < n; i++) if (x[i] < 0.0f) x[i] *= slope;
}



/* ---------------- weight-generic layers (fp32 or int8 per-channel) ---------------- */

typedef struct {
    const float *w;    /* fp32 weights in PyTorch layout, or NULL */
    const int8_t *q;   /* int8 weights [co][K][ci], or NULL */
    const float *qs;   /* per-co scales */
    const float *b;
} layer_t;

static layer_t L(const vtts_model *m, const char *fmt, ...) {
    char base[64], name[80];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(base, sizeof(base), fmt, ap);
    va_end(ap);
    layer_t l = {0, 0, 0, 0};
    snprintf(name, sizeof(name), "%s.weight", base);
    const vtts_tensor *t = vtts_find(m, name);
    if (t && t->dtype == 0) l.w = (const float *)t->data;
    snprintf(name, sizeof(name), "%s.weight.q8", base);
    t = vtts_find(m, name);
    if (t && t->dtype == 1) { l.q = (const int8_t *)t->data; l.qs = t->scale; }
    snprintf(name, sizeof(name), "%s.bias", base);
    t = vtts_find(m, name);
    if (t && t->dtype == 0) l.b = (const float *)t->data;
    return l;
}

static int layer_ok(const layer_t *l) { return (l->w || l->q) && l->b; }

typedef struct { int8_t *x; float *s; } qbuf_t;

/* quantize x [ci, T] (channel-major) to time-major int8 [T][ci] with one scale per frame,
 * so results do not depend on how an utterance is split into chunks */
typedef struct { const float *x; qbuf_t *q; int ci, T; } qt_t;

static void quant_cols(int lo, int hi, void *arg) {
    const qt_t *j = arg;
    const float *x = j->x;
    int ci = j->ci, T = j->T;
    for (int t = lo; t < hi; t++) {
        float amax = 0.0f;
        for (int c = 0; c < ci; c++) { float v = fabsf(x[(size_t)c * T + t]); if (v > amax) amax = v; }
        j->q->s[t] = amax / (float)VTTS_ACT_MAX;
        float inv = amax > 0.0f ? (float)VTTS_ACT_MAX / amax : 0.0f;
        int8_t *row = j->q->x + (size_t)t * ci;
        for (int c = 0; c < ci; c++) row[c] = (int8_t)lrintf(x[(size_t)c * T + t] * inv);
    }
}

static void quant_tm(const float *x, int ci, int T, qbuf_t *q) {
    qt_t j = {x, q, ci, T};
    vtts_par_run(quant_cols, T, &j);
}

typedef struct {
    const layer_t *l;
    const qbuf_t *q;
    float *y;
    int ci, T, K, dil, s, p, Tout;
} qjob_t;

#define DOT_TILE 64 /* frames per call of the multi-row dot kernel */

static void lconv_rows(int lo, int hi, void *arg) {
    const qjob_t *j = arg;
    const layer_t *l = j->l;
    const qbuf_t *q = j->q;
    int ci = j->ci, T = j->T, K = j->K, dil = j->dil, pad = dil * (K - 1) / 2;
    float acc[DOT_TILE];
    int32_t dots[DOT_TILE];
    for (int o = lo; o < hi; o++) {
        for (int t0 = 0; t0 < T; t0 += DOT_TILE) {
            int nt = T - t0 < DOT_TILE ? T - t0 : DOT_TILE;
            for (int i = 0; i < nt; i++) acc[i] = 0.0f;
            for (int k = 0; k < K; k++) {
                int sh = k * dil - pad; /* input frame = output frame + sh */
                int a = t0, b = t0 + nt;
                if (a + sh < 0) a = -sh;
                if (b + sh > T) b = T - sh;
                if (a >= b) continue;
                vtts_dots_s8s8(l->q + ((size_t)o * K + k) * ci, q->x + (size_t)(a + sh) * ci, ci, b - a, ci, dots);
                for (int t = a; t < b; t++) acc[t - t0] += (float)dots[t - a] * q->s[t + sh];
            }
            for (int i = 0; i < nt; i++) j->y[(size_t)o * T + t0 + i] = l->b[o] + acc[i] * l->qs[o];
        }
    }
}

/* same-length conv (K, dil) or linear (K = 1); int8 rows may run on several cores */
static void lconv(const layer_t *l, const float *x, int ci, int T, int co, int K, int dil, float *y,
                  qbuf_t *q) {
    if (l->w) { conv1d(x, ci, T, l->w, l->b, co, K, dil, y); return; }
    quant_tm(x, ci, T, q);
    qjob_t j = {l, q, y, ci, T, K, dil, 0, 0, 0};
    vtts_par_run(lconv_rows, co, &j);
}

static void lconvT_rows(int lo, int hi, void *arg) {
    const qjob_t *jb = arg;
    const layer_t *l = jb->l;
    const qbuf_t *q = jb->q;
    float *y = jb->y;
    int ci = jb->ci, T = jb->T, K = jb->K, s = jb->s, p = jb->p, Tout = jb->Tout;
    for (int o = lo; o < hi; o++) {
        for (int oi = 0; oi < Tout; oi++) {
            float acc = 0.0f;
            for (int k = (oi + p) % s; k < K; k += s) {
                int t = (oi + p - k) / s;
                if (t >= 0 && t < T)
                    acc += (float)vtts_dot_s8s8(q->x + (size_t)t * ci, l->q + ((size_t)o * K + k) * ci, ci)
                           * q->s[t];
            }
            y[(size_t)o * Tout + oi] = l->b[o] + acc * l->qs[o];
        }
    }
}

static void lconvT(const layer_t *l, const float *x, int ci, int T, int co, int K, int s, int p,
                   float *y, int Tout, qbuf_t *q) {
    if (l->w) { convT1d(x, ci, T, l->w, l->b, co, K, s, p, y, Tout); return; }
    quant_tm(x, ci, T, q);
    qjob_t j = {l, q, y, ci, T, K, 0, s, p, Tout};
    vtts_par_run(lconvT_rows, co, &j);
}

/* int8 activations for up to n elements and per-frame scales */
static qbuf_t qalloc(arena_t *a, size_t n, size_t frames) {
    qbuf_t q;
    q.x = (int8_t *)alloc(a, (n + 3) / 4);
    q.s = (float *)alloc(a, frames);
    return q;
}

/* ---------------- fast transcendental functions for the iSTFT head ----------------
 * Range-reduced polynomials (max abs error ~2e-7 for sin/cos on any phase, ~1e-6 relative
 * for exp on [-87, 6]). The head evaluates them for every bin of every frame. */

static inline void fast_sincos(float x, float *s_out, float *c_out) {
    const float inv_half_pi = 0.63661977236758134f;
    float q = nearbyintf(x * inv_half_pi);
    /* Cody-Waite reduction with pi/2 split in three parts */
    float r = x - q * 1.5707963705062866f;
    r = r - q * -4.3711388286737929e-08f;
    int quad = (int)q & 3;
    float r2 = r * r;
    float sn = r + r * r2 * (-1.6666667163e-1f + r2 * (8.3333337680e-3f + r2 * (-1.9841270114e-4f + r2 * 2.7557314297e-6f)));
    float cs = 1.0f + r2 * (-0.5f + r2 * (4.1666667908e-2f + r2 * (-1.3888889225e-3f + r2 * 2.4801587642e-5f)));
    switch (quad) {
    case 0: *s_out = sn; *c_out = cs; break;
    case 1: *s_out = cs; *c_out = -sn; break;
    case 2: *s_out = -sn; *c_out = -cs; break;
    default: *s_out = -cs; *c_out = sn; break;
    }
}

static inline float fast_exp(float x) {
    if (x < -87.0f) return 0.0f;
    const float log2e = 1.4426950408889634f;
    float t = x * log2e, n = floorf(t), f = t - n; /* 2^t = 2^n * 2^f, f in [0,1) */
    float p = 1.0f + f * (6.9314718056e-1f + f * (2.4022650695e-1f + f * (5.5504108665e-2f +
              f * (9.6181291076e-3f + f * (1.3333558146e-3f + f * 1.5403530393e-4f)))));
    union { float f; int32_t i; } u = {p};
    u.i += (int32_t)n * (1 << 23); /* add n to the exponent field */
    return u.f;
}

/* GELU (tanh form) by linear interpolation in a table over [-GELU_R, GELU_R]; max abs error
 * ~1e-5, far below the int8 step of the next layer. Outside the range GELU is x or 0. */
#define GELU_N 2048
#define GELU_R 8.0f
static float s_gelu[GELU_N + 2];
static int s_gelu_ready;

static void gelu_init(void) {
    if (s_gelu_ready) return;
    for (int i = 0; i <= GELU_N + 1; i++) {
        double x = -GELU_R + (2.0 * GELU_R) * i / GELU_N;
        s_gelu[i] = (float)(0.5 * x * (1.0 + tanh(0.7978845608028654 * (x + 0.044715 * x * x * x))));
    }
    s_gelu_ready = 1;
}

static inline float fast_gelu(float x) {
    if (x >= GELU_R) return x;
    if (x <= -GELU_R) return 0.0f;
    float u = (x + GELU_R) * (GELU_N / (2.0f * GELU_R));
    int i = (int)u; /* u >= 0, so truncation is floor */
    float f = u - (float)i;
    return s_gelu[i] + f * (s_gelu[i + 1] - s_gelu[i]);
}

static inline float fast_tanh(float x) {
    float e = fast_exp(-2.0f * fabsf(x));
    float r = (1.0f - e) / (1.0f + e);
    return x >= 0.0f ? r : -r;
}

/* ---------------- FFT (radix-2, in place, inverse, unnormalised) ---------------- */

static void ifft(float *re, float *im, int n) {
    for (int i = 1, j = 0; i < n; i++) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            float tr = re[i]; re[i] = re[j]; re[j] = tr;
            float ti = im[i]; im[i] = im[j]; im[j] = ti;
        }
    }
    for (int len = 2; len <= n; len <<= 1) {
        double ang = 2.0 * M_PI / len;
        float wr = (float)cos(ang), wi = (float)sin(ang);
        for (int i = 0; i < n; i += len) {
            float cr = 1.0f, ci = 0.0f;
            for (int k = 0; k < len / 2; k++) {
                float ur = re[i + k], ui = im[i + k];
                float vr = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci;
                float vi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr;
                re[i + k] = ur + vr; im[i + k] = ui + vi;
                re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi;
                float nr = cr * wr - ci * wi;
                ci = cr * wi + ci * wr;
                cr = nr;
            }
        }
    }
}

/* torch.istft(center=True, hann window, normalized=False, onesided) followed by tanh.
 * mag/phase are [n_bins, F] channel-major with n_bins = n_fft/2 + 1. */
static void istft_tanh(arena_t *a, const float *mag, const float *phase, int n_fft, int hop, int F,
                       float *pcm, long n_out, long first) {
    long ola_len = (long)n_fft + (long)hop * (F - 1);
    float *ola = alloc(a, (size_t)ola_len), *env = alloc(a, (size_t)ola_len);
    float *re = alloc(a, (size_t)n_fft), *im = alloc(a, (size_t)n_fft), *win = alloc(a, (size_t)n_fft);
    if (a->dry || a->oom) return;
    int nb = n_fft / 2 + 1;
    for (int i = 0; i < n_fft; i++) win[i] = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * i / n_fft);
    memset(ola, 0, sizeof(float) * (size_t)ola_len);
    memset(env, 0, sizeof(float) * (size_t)ola_len);
    for (int f = 0; f < F; f++) {
        for (int k = 0; k < nb; k++) {
            float mg = mag[(size_t)k * F + f], ph = phase[(size_t)k * F + f];
            re[k] = mg * cosf(ph);
            im[k] = mg * sinf(ph);
        }
        for (int k = nb; k < n_fft; k++) { re[k] = re[n_fft - k]; im[k] = -im[n_fft - k]; }
        ifft(re, im, n_fft);
        float *o = ola + (long)f * hop, *e = env + (long)f * hop;
        for (int i = 0; i < n_fft; i++) {
            o[i] += re[i] / (float)n_fft * win[i];
            e[i] += win[i] * win[i];
        }
    }
    long start = n_fft / 2 + first;
    for (long i = 0; i < n_out; i++) {
        long j = start + i;
        float v = (j < ola_len && env[j] > 1e-11f) ? ola[j] / env[j] : 0.0f;
        pcm[i] = tanhf(v);
    }
}

/* ---------------- graph ---------------- */

/* x = x + LN(relu(conv(x))) ; uses tmp [C, T] */
static int conv_block(const vtts_model *m, const char *prefix, int i, float *x, int C, int T, int K,
                      float *tmp, qbuf_t *xq) {
    layer_t c = L(m, "%s.%d.conv", prefix, i);
    const float *g = W(m, "%s.%d.norm.weight", prefix, i), *be = W(m, "%s.%d.norm.bias", prefix, i);
    if (!layer_ok(&c) || !g || !be) return VTTS_ERR_MISSING;
    lconv(&c, x, C, T, C, K, 1, tmp, xq);
    for (size_t j = 0; j < (size_t)C * T; j++) if (tmp[j] < 0.0f) tmp[j] = 0.0f;
    layernorm_cm(tmp, C, T, g, be);
    for (size_t j = 0; j < (size_t)C * T; j++) x[j] += tmp[j];
    return VTTS_OK;
}

static int embed(const vtts_model *m, const char *name, const int32_t *ids, int n, int H, float *x) {
    const vtts_tensor *e = vtts_find(m, name);
    if (!e || e->dtype != 0 || e->shape[1] != H) return VTTS_ERR_MISSING;
    for (int i = 0; i < n; i++) {
        if (ids[i] < 0 || ids[i] >= e->shape[0]) return VTTS_ERR_RANGE;
        const float *row = (const float *)e->data + (size_t)ids[i] * H;
        for (int c = 0; c < H; c++) x[(size_t)c * n + i] = row[c];
    }
    return VTTS_OK;
}

static long run_durations(const vtts_model *m, arena_t *a, const int32_t *ids, int n, float ls,
                          int32_t *dur, float *log_dur) {
    int H = m->d_hidden;
    float *x = alloc(a, (size_t)H * n), *tmp = alloc(a, (size_t)H * n), *ld = alloc(a, (size_t)n);
    if (a->dry) return 1;
    if (a->oom) return VTTS_ERR_ARENA;
    int rc = embed(m, "duration.emb.weight", ids, n, H, x);
    if (rc) return rc;
    for (int i = 0; i < m->d_depth; i++)
        if ((rc = conv_block(m, "duration.blocks", i, x, H, n, m->d_kernel, tmp, NULL))) return rc;
    const float *w = W(m, "duration.out.weight"), *b = W(m, "duration.out.bias");
    if (!w || !b) return VTTS_ERR_MISSING;
    linear_cm(x, H, n, w, b, 1, ld);
    long total = 0;
    for (int i = 0; i < n; i++) {
        float d = nearbyintf(expf(ld[i]) * ls);
        if (d < 1.0f) d = 1.0f;
        if (d > (float)m->max_duration) d = (float)m->max_duration;
        dur[i] = (int32_t)d;
        if (log_dur) log_dur[i] = ld[i];
        total += dur[i];
    }
    return total;
}

static int token_stage(const vtts_model *m, arena_t *a, const int32_t *ids, int n, float *tok) {
    int H = m->a_hidden;
    float *ttmp = alloc(a, (size_t)H * n);
    if (a->dry) return VTTS_OK;
    if (a->oom) return VTTS_ERR_ARENA;
    int rc = embed(m, "acoustic.emb.weight", ids, n, H, tok);
    if (rc) return rc;
    for (int i = 0; i < m->a_token_depth; i++)
        if ((rc = conv_block(m, "acoustic.token_blocks", i, tok, H, n, m->a_kernel, ttmp, NULL))) return rc;
    return VTTS_OK;
}

/* latent for global frames [g0, g1); window edges are zero padded like utterance edges */
static long latent_window(const vtts_model *m, arena_t *a, const float *tok, const int32_t *dur,
                          int n, long g0, long g1, float *z) {
    int H = m->a_hidden;
    long Wn = g1 - g0;
    float *x = alloc(a, (size_t)H * Wn), *tmp = alloc(a, (size_t)H * Wn), *feat = alloc(a, (size_t)2 * Wn);
    float *pb = m->prosody ? alloc(a, (size_t)H * Wn) : NULL, *pp = m->prosody ? alloc(a, (size_t)2 * Wn) : NULL;
    qbuf_t qb = qalloc(a, (size_t)H * Wn, (size_t)Wn), *xq = &qb;
    if (a->dry) return Wn;
    if (a->oom) return VTTS_ERR_ARENA;
    long start = 0;
    for (int i = 0; i < n && start < g1; i++) {
        for (int k = 0; k < dur[i]; k++) {
            long f = start + k;
            if (f < g0 || f >= g1) continue;
            long t = f - g0;
            for (int c = 0; c < H; c++) x[(size_t)c * Wn + t] = tok[(size_t)c * n + i];
            feat[t] = ((float)k + 0.5f) / (float)dur[i];
            feat[Wn + t] = logf((float)dur[i]);
        }
        start += dur[i];
    }
    const float *pw = W(m, "acoustic.pos.weight"), *pbias = W(m, "acoustic.pos.bias");
    if (!pw || !pbias) return VTTS_ERR_MISSING;
    linear_cm(feat, 2, (int)Wn, pw, pbias, H, tmp);
    for (size_t j = 0; j < (size_t)H * Wn; j++) x[j] += tmp[j];
    int rc;
    if (m->prosody) { /* predict normalized log-F0 + energy, scale the pitch, condition x */
        memcpy(pb, x, sizeof(float) * (size_t)H * Wn);
        for (int i = 0; i < m->p_depth; i++)
            if ((rc = conv_block(m, "acoustic.pitch_blocks", i, pb, H, (int)Wn, m->a_kernel, tmp, xq))) return rc;
        layer_t po = L(m, "acoustic.pitch_out"), pe = L(m, "acoustic.pitch_emb");
        if (!layer_ok(&po) || !layer_ok(&pe)) return VTTS_ERR_MISSING;
        lconv(&po, pb, H, (int)Wn, 2, 1, 1, pp, xq);
        for (long t = 0; t < Wn; t++) pp[t] *= m->expressiveness;
        lconv(&pe, pp, 2, (int)Wn, H, 3, 1, tmp, xq);
        for (size_t j = 0; j < (size_t)H * Wn; j++) x[j] += tmp[j];
    }
    for (int i = 0; i < m->a_frame_depth; i++)
        if ((rc = conv_block(m, "acoustic.frame_blocks", i, x, H, (int)Wn, m->a_kernel, tmp, xq))) return rc;
    layer_t out = L(m, "acoustic.out");
    if (!layer_ok(&out)) return VTTS_ERR_MISSING;
    lconv(&out, x, H, (int)Wn, m->latent, 1, 1, z, xq);
    return Wn;
}

static long run_latent(const vtts_model *m, arena_t *a, const int32_t *ids, const int32_t *dur,
                       int n, long T, float *z) {
    float *tok = alloc(a, (size_t)m->a_hidden * n);
    long rc = token_stage(m, a, ids, n, tok);
    if (rc) return rc;
    return latent_window(m, a, tok, dur, n, 0, T, z);
}

/* vocos: z window [latent, Wz] covering global frames [z0, z0 + Wz) -> pcm for global
 * frames [s, e). The ConvNeXt MLP and the head/iSTFT run one frame at a time, and only
 * frames that overlap the output region go through the head, so memory does not grow
 * with the window and whole-utterance and streaming runs compute exactly the same sums. */
typedef struct { float *h; long n; } gelu_job_t;

static void gelu_range(int lo, int hi, void *arg) {
    const gelu_job_t *j = arg;
    long n = j->n, a = (long)lo * 64, b = (long)hi * 64 < n ? (long)hi * 64 : n;
    for (long i = a; i < b; i++) j->h[i] = fast_gelu(j->h[i]);
}

static void gelu_par(float *h, long n) {
    gelu_job_t j = {h, n};
    vtts_par_run(gelu_range, (int)((n + 63) / 64), &j);
}

/* head output [n_fft + 2, hb] -> real inverse FFT of each frame, via one complex FFT of half
 * size: with X[N/2 + k] = conj(X[N/2 - k]),
 *   E[k] = X[k] + conj(X[N/2 - k]),  O[k] = (X[k] - conj(X[N/2 - k])) e^{2 pi i k / N},
 *   z = IFFT_{N/2}(E + iO)  gives  x[2m] = Re z[m], x[2m + 1] = Im z[m].
 * Frame j uses z = buf + j * N as [Re z | Im z]; the caller windows and overlap-adds. */
typedef struct { const float *head; float *buf; int hb, n_fft; } ifr_t;

static inline void head_bin(const ifr_t *jb, int j, int k, float *xr, float *xi) {
    int nb = jb->n_fft / 2 + 1, hb = jb->hb;
    float hv = jb->head[(size_t)k * hb + j];
    float mg = fast_exp(hv > 6.0f ? 6.0f : hv), sn, cs;
    fast_sincos(jb->head[(size_t)(nb + k) * hb + j], &sn, &cs);
    *xr = mg * cs;
    *xi = mg * sn;
}

static void istft_frames(int lo, int hi, void *arg) {
    const ifr_t *jb = arg;
    int N = jb->n_fft, H = N / 2;
    for (int j = lo; j < hi; j++) {
        float *zr = jb->buf + (size_t)j * N, *zi = zr + H;
        for (int k = 0; k <= H / 2; k++) {
            float ar, ai, br, bi; /* a = X[k], b = X[H - k] */
            head_bin(jb, j, k, &ar, &ai);
            head_bin(jb, j, H - k, &br, &bi);
            if (k == 0) ai = bi = 0.0f; /* like irfft: DC and Nyquist bins are taken as real */
            float er = ar + br, ei = ai - bi, dr = ar - br, di = ai + bi, sn, cs;
            fast_sincos(6.283185307179586f * (float)k / (float)N, &sn, &cs);
            float orr = dr * cs - di * sn, oi = dr * sn + di * cs;
            zr[k] = er - oi;
            zi[k] = ei + orr;
            if (k > 0 && k < H - k) {
                zr[H - k] = er + oi;
                zi[H - k] = orr - ei;
            }
        }
        ifft(zr, zi, H);
    }
}

static long vocos_region(const vtts_model *m, arena_t *a, const float *z, long Wz, long z0, long T_all,
                         long s, long e, float *pcm) {
    int C = m->v_dim, M = m->v_mult * C, n_fft = 4 * m->hop, hop = m->hop;
    long f_lo = s - 2 > 0 ? s - 2 : 0, f_hi = e + 2 < T_all ? e + 2 : T_all;
    if (a->dry) { f_lo = 0; f_hi = e - s + 4; }
    long n_f = f_hi - f_lo;
    long ola_len = (long)n_fft + (long)hop * (n_f - 1);
    float *x = alloc(a, (size_t)C * Wz), *y = alloc(a, (size_t)C * Wz);
    /* frames are processed in small blocks so each pass over the weights serves several frames
     * (weights live in flash/PSRAM on the MCU and do not fit its cache) */
    float *col = alloc(a, (size_t)C * VTTS_BLOCK), *h = alloc(a, (size_t)M * VTTS_BLOCK);
    float *o = alloc(a, (size_t)C * VTTS_BLOCK), *head = alloc(a, (size_t)(n_fft + 2) * VTTS_HEAD_BLOCK);
    qbuf_t qb = qalloc(a, (size_t)(m->latent > M ? m->latent : M) * Wz, (size_t)Wz), *xq = &qb;
    float *ola = alloc(a, (size_t)ola_len), *env = alloc(a, (size_t)ola_len);
    /* re/im per frame of a head block, so the frames' inverse FFTs can run on several cores */
    float *fbuf = alloc(a, (size_t)n_fft * VTTS_HEAD_BLOCK), *win = alloc(a, (size_t)n_fft);
    if (a->dry) return e - s;
    if (a->oom) return VTTS_ERR_ARENA;

    PROF_T0();
    gelu_init();
    layer_t pre = L(m, "decoder.pre"), hd = L(m, "decoder.head");
    const float *g = W(m, "decoder.norm.weight"), *be = W(m, "decoder.norm.bias");
    const float *fg = W(m, "decoder.final_norm.weight"), *fb = W(m, "decoder.final_norm.bias");
    if (!layer_ok(&pre) || !layer_ok(&hd) || !g || !be || !fg || !fb) return VTTS_ERR_MISSING;
    lconv(&pre, z, m->latent, (int)Wz, C, 7, 1, x, xq);
    layernorm_cm(x, C, (int)Wz, g, be);
    for (int i = 0; i < m->v_blocks; i++) {
        const float *dw = W(m, "decoder.blocks.%d.dw.weight", i), *db = W(m, "decoder.blocks.%d.dw.bias", i);
        const float *ng = W(m, "decoder.blocks.%d.norm.weight", i), *nbb = W(m, "decoder.blocks.%d.norm.bias", i);
        layer_t p1 = L(m, "decoder.blocks.%d.pw1", i), p2 = L(m, "decoder.blocks.%d.pw2", i);
        const float *gm = W(m, "decoder.blocks.%d.gamma", i);
        if (!dw || !db || !ng || !nbb || !layer_ok(&p1) || !layer_ok(&p2) || !gm) return VTTS_ERR_MISSING;
        dwconv1d(x, C, (int)Wz, dw, db, 7, y);
        layernorm_cm(y, C, (int)Wz, ng, nbb);
        PROF_ADD(3);
        for (long t0 = 0; t0 < Wz; t0 += VTTS_BLOCK) {
            int nb_ = (int)(Wz - t0 < VTTS_BLOCK ? Wz - t0 : VTTS_BLOCK);
            for (int c = 0; c < C; c++)
                for (int j = 0; j < nb_; j++) col[(size_t)c * nb_ + j] = y[(size_t)c * Wz + t0 + j];
            lconv(&p1, col, C, nb_, M, 1, 1, h, xq);
            gelu_par(h, (long)M * nb_);
            lconv(&p2, h, M, nb_, C, 1, 1, o, xq);
            for (int c = 0; c < C; c++)
                for (int j = 0; j < nb_; j++) x[(size_t)c * Wz + t0 + j] += o[(size_t)c * nb_ + j] * gm[c];
        }
        PROF_ADD(4);
    }
    layernorm_cm(x, C, (int)Wz, fg, fb);
    PROF_ADD(3);

    for (int i = 0; i < n_fft; i++) win[i] = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * i / n_fft);
    memset(ola, 0, sizeof(float) * (size_t)ola_len);
    memset(env, 0, sizeof(float) * (size_t)ola_len);
    for (long hb0 = f_lo; hb0 < f_hi; hb0 += VTTS_HEAD_BLOCK) {
        int hb = (int)(f_hi - hb0 < VTTS_HEAD_BLOCK ? f_hi - hb0 : VTTS_HEAD_BLOCK);
        for (int c = 0; c < C; c++)
            for (int j = 0; j < hb; j++) col[(size_t)c * hb + j] = x[(size_t)c * Wz + (hb0 - z0) + j];
        PROF_ADD(6);
        lconv(&hd, col, C, hb, n_fft + 2, 1, 1, head, xq);
        PROF_ADD(5);
        ifr_t job = {head, fbuf, hb, n_fft};
        vtts_par_run(istft_frames, hb, &job);
        const float inv_n = 1.0f / (float)n_fft;
        for (int j = 0; j < hb; j++) { /* window and overlap-add in frame order */
            const float *zr = fbuf + (size_t)j * n_fft, *zi = zr + n_fft / 2;
            float *op = ola + (hb0 + j - f_lo) * hop, *ep = env + (hb0 + j - f_lo) * hop;
            for (int i = 0; i < n_fft / 2; i++) {
                op[2 * i] += zr[i] * inv_n * win[2 * i];
                op[2 * i + 1] += zi[i] * inv_n * win[2 * i + 1];
            }
            for (int i = 0; i < n_fft; i++) ep[i] += win[i] * win[i];
        }
    }
    PROF_ADD(6);
    long n_out = (e - s) * hop;
    for (long i = 0; i < n_out; i++) {
        long jj = s * hop + i + n_fft / 2 - f_lo * hop; /* index into the local OLA buffer */
        float v = (jj >= 0 && jj < ola_len && env[jj] > 1e-11f) ? ola[jj] / env[jj] : 0.0f;
        pcm[i] = fast_tanh(v);
    }
    return n_out;
}

static long run_vocos(const vtts_model *m, arena_t *a, const float *z, long T, float *pcm) {
    long rc = vocos_region(m, a, z, T, 0, T, 0, T, pcm);
    if (a->dry) return T * m->hop;
    return rc;
}

static long run_upsampler(const vtts_model *m, arena_t *a, const float *z, long T, float *pcm) {
    int ch = m->c0;
    long len = T, maxe = (long)ch * T;
    for (int s = 0; s < m->n_up; s++) {
        len *= m->up[s];
        ch /= 2;
        if ((long)ch * len > maxe) maxe = (long)ch * len;
    }
    int out_ch = m->decoder == VTTS_DEC_HIFIGAN ? 1 : m->n_fft + 2;
    if ((long)out_ch * len > maxe) maxe = (long)out_ch * len;
    float *x = alloc(a, (size_t)maxe), *y = alloc(a, (size_t)maxe), *tmp = alloc(a, (size_t)maxe);
    long qmax = maxe > (long)m->latent * T ? maxe : (long)m->latent * T;
    long fmax = len > T ? len : T;
    qbuf_t qb = qalloc(a, (size_t)qmax, (size_t)fmax), *xq = &qb;
    if (!a->dry && a->oom) return VTTS_ERR_ARENA;
    if (!a->dry) {
        layer_t pre = L(m, "decoder.pre");
        if (!layer_ok(&pre)) return VTTS_ERR_MISSING;
        ch = m->c0;
        len = T;
        lconv(&pre, z, m->latent, (int)T, ch, 7, 1, x, xq);
        for (int s = 0; s < m->n_up; s++) {
            layer_t up = L(m, "decoder.ups.%d", s);
            if (!layer_ok(&up)) return VTTS_ERR_MISSING;
            lrelu(x, (size_t)ch * len, 0.1f);
            long lo = len * m->up[s];
            lconvT(&up, x, ch, (int)len, ch / 2, m->upk[s], m->up[s], (m->upk[s] - m->up[s]) / 2, y, (int)lo, xq);
            ch /= 2;
            len = lo;
            for (int r = 0; r < m->n_res; r++) {
                layer_t rl = L(m, "decoder.res.%d.convs.%d", s, r);
                if (!layer_ok(&rl)) return VTTS_ERR_MISSING;
                memcpy(tmp, y, sizeof(float) * (size_t)ch * len);
                lrelu(tmp, (size_t)ch * len, 0.1f);
                lconv(&rl, tmp, ch, (int)len, ch, m->res_kernel, m->res_d[r], x, xq);
                for (size_t j = 0; j < (size_t)ch * len; j++) y[j] += x[j];
            }
            float *sw = x; x = y; y = sw;
        }
        layer_t post = L(m, "decoder.post");
        if (!layer_ok(&post)) return VTTS_ERR_MISSING;
        lrelu(x, (size_t)ch * len, 0.01f);
        lconv(&post, x, ch, (int)len, out_ch, 7, 1, y, xq);
        if (m->decoder == VTTS_DEC_HIFIGAN) {
            for (long i = 0; i < len; i++) pcm[i] = tanhf(y[i]);
            return len;
        }
        int nb = m->n_fft / 2 + 1;
        for (size_t j = 0; j < (size_t)nb * len; j++) y[j] = expf(y[j] > 6.0f ? 6.0f : y[j]);
        for (size_t j = (size_t)nb * len; j < (size_t)2 * nb * len; j++) y[j] = (float)M_PI * sinf(y[j]);
    }
    if (m->decoder == VTTS_DEC_HIFIGAN) return len;
    istft_tanh(a, y, a->dry ? NULL : y + (size_t)(m->n_fft / 2 + 1) * len, m->n_fft, m->istft_hop,
               (int)len, pcm, len * m->istft_hop, 0);
    if (a->oom) return VTTS_ERR_ARENA;
    return len * m->istft_hop;
}

static long run_decode(const vtts_model *m, arena_t *a, const float *z, long T, float *pcm) {
    if (m->decoder == VTTS_DEC_VOCOS) return run_vocos(m, a, z, T, pcm);
    if (m->decoder == VTTS_DEC_HIFIGAN || m->decoder == VTTS_DEC_ISTFT) return run_upsampler(m, a, z, T, pcm);
    return VTTS_ERR_FORMAT;
}

/* ---------------- public API ---------------- */

/* the arena base is rounded up to 16 bytes so every buffer is SIMD-aligned */
static arena_t mk(void *p, size_t n) {
    uintptr_t base = (uintptr_t)p, aligned = (base + 15u) & ~(uintptr_t)15u;
    size_t lost = (size_t)(aligned - base);
    arena_t a = {(uint8_t *)aligned, n > lost ? n - lost : 0, 0, 0, p == NULL, 0};
    if (p == NULL) a.base = NULL;
    return a;
}

size_t vtts_arena_bytes(const vtts_model *m, int n_ids, long max_frames) {
    if (!m || n_ids < 1 || max_frames < 1) return 0;
    arena_t a = mk(NULL, 0);
    alloc(&a, (size_t)n_ids);                      /* durations (synthesize) */
    alloc(&a, (size_t)m->latent * max_frames);     /* latent (synthesize) */
    size_t keep = a.used, worst = 0;
    run_durations(m, &a, NULL, n_ids, 1.0f, NULL, NULL);
    if (a.peak > worst) worst = a.peak;
    a.used = a.peak = keep;
    run_latent(m, &a, NULL, NULL, n_ids, max_frames, NULL);
    if (a.peak > worst) worst = a.peak;
    a.used = a.peak = keep;
    run_decode(m, &a, NULL, max_frames, NULL);
    if (a.peak > worst) worst = a.peak;
    return worst + 16; /* room to align an unaligned arena */
}

long vtts_durations(const vtts_model *m, const int32_t *ids, int n, float ls, int32_t *dur,
                    float *log_dur, void *arena, size_t bytes) {
    if (!m || !ids || !dur || n < 1 || !arena || !(ls > 0.0f)) return VTTS_ERR_ARGS;
    arena_t a = mk(arena, bytes);
    return run_durations(m, &a, ids, n, ls, dur, log_dur);
}

long vtts_latent(const vtts_model *m, const int32_t *ids, const int32_t *dur, int n, float *z,
                 void *arena, size_t bytes) {
    if (!m || !ids || !dur || !z || n < 1 || !arena) return VTTS_ERR_ARGS;
    long T = 0;
    for (int i = 0; i < n; i++) {
        if (dur[i] < 1 || dur[i] > m->max_duration) return VTTS_ERR_RANGE;
        T += dur[i];
    }
    arena_t a = mk(arena, bytes);
    return run_latent(m, &a, ids, dur, n, T, z);
}

long vtts_decode(const vtts_model *m, const float *z, long T, float *pcm, void *arena, size_t bytes) {
    if (!m || !z || !pcm || T < 1 || !arena) return VTTS_ERR_ARGS;
    arena_t a = mk(arena, bytes);
    return run_decode(m, &a, z, T, pcm);
}

long vtts_synthesize(const vtts_model *m, const int32_t *ids, int n, float ls, float *pcm,
                     long cap, void *arena, size_t bytes) {
    if (!m || !ids || !pcm || n < 1 || !arena) return VTTS_ERR_ARGS;
    arena_t a = mk(arena, bytes);
    int32_t *dur = alloc(&a, (size_t)n);
    if (a.oom) return VTTS_ERR_ARENA;
    size_t mark = a.used;
    long T = run_durations(m, &a, ids, n, ls, dur, NULL);
    if (T < 0) return T;
    if (T * m->hop > cap) return VTTS_ERR_ARENA;
    a.used = mark;
    float *z = alloc(&a, (size_t)m->latent * T);
    if (a.oom) return VTTS_ERR_ARENA;
    mark = a.used;
    long rc = run_latent(m, &a, ids, dur, n, T, z);
    if (rc < 0) return rc;
    a.used = mark;
    return run_decode(m, &a, z, T, pcm);
}

/* ---------------- streaming (vocos) ---------------- */

static int stream_radius_dec(const vtts_model *m) { return 3 * (1 + m->v_blocks) + 4; }
static int stream_radius_ac(const vtts_model *m) {
    int r = m->a_frame_depth * (m->a_kernel - 1) / 2;
    if (m->prosody) r += m->p_depth * (m->a_kernel - 1) / 2 + 1; /* pitch blocks + k3 embedding */
    return r;
}

static long stream_run(const vtts_model *m, arena_t *a, const int32_t *ids, int n, float ls,
                       int first, int chunk, vtts_pcm_cb cb, void *user, long T_dry) {
    int H = m->a_hidden, Rd = stream_radius_dec(m), Ra = stream_radius_ac(m);
    int32_t *dur = alloc(a, (size_t)n);
    float *tok = alloc(a, (size_t)H * n);
    float *pcm = alloc(a, (size_t)chunk * m->hop);
    if (!a->dry && a->oom) return VTTS_ERR_ARENA;
    size_t mark = a->used;
    PROF_T0();
    long T = a->dry ? T_dry : run_durations(m, a, ids, n, ls, dur, NULL);
    if (T < 0) return T;
    a->used = mark;
    PROF_ADD(0);
    long rc = token_stage(m, a, ids, n, tok);
    if (rc) return rc;
    a->used = mark;
    PROF_ADD(1);
    long total = 0;
    for (long s = 0, step = first; s < T; s += step, step = step * 2 < chunk ? step * 2 : chunk) {
        long e = s + step < T ? s + step : T;
        long z0 = s - Rd > 0 ? s - Rd : 0, z1 = e + Rd < T ? e + Rd : T;
        long a0 = z0 - Ra > 0 ? z0 - Ra : 0, a1 = z1 + Ra < T ? z1 + Ra : T;
        if (a->dry) { z0 = 0; z1 = chunk + 2L * Rd; a0 = 0; a1 = z1 + 2L * Ra; e = s + chunk; }
        long Wz = z1 - z0;
        float *zw = alloc(a, (size_t)m->latent * Wz);
        size_t mark2 = a->used;
        float *za = alloc(a, (size_t)m->latent * (a1 - a0));
#ifdef VTTS_PROFILE
        _pt = vtts_now_us();
#endif
        long w = latent_window(m, a, tok, dur, n, a0, a1, za);
        if (w < 0) return w;
        PROF_ADD(2);
        if (!a->dry) {
            if (a->oom) return VTTS_ERR_ARENA;
            for (int c = 0; c < m->latent; c++)
                memcpy(zw + (size_t)c * Wz, za + (size_t)c * (a1 - a0) + (z0 - a0), sizeof(float) * (size_t)Wz);
        }
        a->used = mark2; /* the acoustic window is no longer needed */
        long n_out = vocos_region(m, a, zw, Wz, z0, T, s, e, pcm);
        if (n_out < 0) return n_out;
        if (a->oom) return VTTS_ERR_ARENA;
        if (a->dry) return 1;
        if (cb && cb(pcm, n_out, user)) return VTTS_ERR_ARGS;
        total += n_out;
        a->used = mark;
    }
    return total;
}

size_t vtts_stream_arena_bytes(const vtts_model *m, int n_ids, int chunk_frames) {
    if (!m || n_ids < 1 || chunk_frames < 1) return 0;
    arena_t a = mk(NULL, 0);
    /* durations need a pass over all tokens; the chunk loop reuses the same region */
    size_t worst = 0;
    arena_t d = mk(NULL, 0);
    alloc(&d, (size_t)n_ids);
    alloc(&d, (size_t)m->a_hidden * n_ids);
    alloc(&d, (size_t)chunk_frames * m->hop);
    run_durations(m, &d, NULL, n_ids, 1.0f, NULL, NULL);
    worst = d.peak;
    stream_run(m, &a, NULL, n_ids, 1.0f, chunk_frames, chunk_frames, NULL, NULL, 1);
    a.used = 0;
    arena_t t = mk(NULL, 0);
    alloc(&t, (size_t)n_ids);
    alloc(&t, (size_t)m->a_hidden * n_ids);
    alloc(&t, (size_t)chunk_frames * m->hop);
    token_stage(m, &t, NULL, n_ids, NULL);
    if (t.peak > worst) worst = t.peak;
    return (a.peak > worst ? a.peak : worst) + 16; /* room to align an unaligned arena */
}

long vtts_synthesize_stream_ex(const vtts_model *m, const int32_t *ids, int n, float ls, int first,
                               int chunk, vtts_pcm_cb cb, void *user, void *arena, size_t bytes) {
    if (!m || !ids || n < 1 || chunk < 1 || first < 1 || first > chunk || !arena || !(ls > 0.0f))
        return VTTS_ERR_ARGS;
    if (m->decoder != VTTS_DEC_VOCOS) return VTTS_ERR_ARGS;
    arena_t a = mk(arena, bytes);
    return stream_run(m, &a, ids, n, ls, first, chunk, cb, user, 0);
}

long vtts_synthesize_stream(const vtts_model *m, const int32_t *ids, int n, float ls, int chunk,
                            vtts_pcm_cb cb, void *user, void *arena, size_t bytes) {
    return vtts_synthesize_stream_ex(m, ids, n, ls, chunk, chunk, cb, user, arena, bytes);
}
