/* SPDX-License-Identifier: Apache-2.0 */
/* main.c -- Vietnamese TTS on ESP32-P4 and ESP32-S3 boards: type a sentence on the serial console
 * and the board speaks it. Everything runs on the chip: text -> ids (vtts_text) -> int8 student
 * (vtts runtime) -> speaker (board_audio).
 *
 * Console commands (one per line):
 *   bench        speed report on four fixed sentences (no audio), one REPORT line each
 *   model s|m    choose the small (S-vocos) or medium (M-vocos) model
 *   vol N        speaker volume 0..100
 *   <text>       synthesize and speak; prints a SAID line with timings
 */
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "board_audio.h"
#include "driver/uart.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/stream_buffer.h"
#include "freertos/task.h"
#include "esp_random.h"
#include "vtts.h"
#include "vtts_port.h"
#include "vtts_text.h"

#ifndef FAST_SCRATCH_MAX
#define FAST_SCRATCH_MAX 0 /* bytes of internal SRAM for hot synthesis buffers; 0 keeps everything in PSRAM (SRAM stays free for DMA). About 2% faster with 96 KB on the P4. */
#endif

static const char *TAG = "vtts";

extern const uint8_t model_s_start[] asm("_binary_model_s_vtts_start");
extern const uint8_t model_s_end[] asm("_binary_model_s_vtts_end");
extern const uint8_t model_m_start[] asm("_binary_model_m_vtts_start");
extern const uint8_t model_m_end[] asm("_binary_model_m_vtts_end");

#define MAX_CHUNK 256
#define MAX_SECONDS 120
#define OUT_RATE_TRY 22050
#define OUT_RATE_FALLBACK 16000

static const char *const BENCH[] = {
    "Xin chào, tôi là trợ lý giọng nói của bạn.",
    "Nhiệt độ trong phòng hiện là 26 độ, độ ẩm 65%.",
    "Báo thức lúc 6:30 sáng mai đã được đặt.",
    "Hôm nay là thứ Bảy, ngày 14/11/2026.",
};

#if CONFIG_IDF_TARGET_ESP32S3
#define RTF_INIT_S 0.30f
#define RTF_INIT_M 0.53f
#else
#define RTF_INIT_S 0.18f
#define RTF_INIT_M 0.29f
#endif
static struct {
    vtts_model models[2];
    int cur; /* 0 = S, 1 = M */
    void *arena;
    size_t arena_bytes;
    const char *arena_where;
    float *pcm;      /* MAX_SECONDS of audio, PSRAM */
    long pcm_cap, n; /* samples */
    int64_t synth_us;
    int spk; /* speaker available */
    int out_rate, vol, chunk;
    StreamBufferHandle_t sb; /* int16 PCM at the model rate, synthesized ahead of playback */
    int streaming;           /* 1 while a SAID command feeds the speaker */
    int64_t t_start, t_first, t_play;
    volatile int synth_done;  /* lets the speaker start before the prebuffer fills */
    volatile int underruns;
    SemaphoreHandle_t utt_start, utt_end; /* one utterance at a time between console and speaker */
    int first;
    float gain; /* digital gain before the codec (linear), with a soft limiter */
    float speed; /* length_scale: > 1 reads slower */
    int64_t blocked_us; /* time the synthesizer waited on a full playback buffer */
    float rtf[2];       /* measured RTF per model (synthesis only), sets the prebuffer */
} g = {.vol = BOARD_DEFAULT_VOL, .chunk = 128, .first = 12, .gain = 1.0f, .speed = 1.0f, .rtf = {RTF_INIT_S, RTF_INIT_M}};

/* gain + soft limiter: linear below 0.7, smoothly saturating to 1.0 above */
static inline float shape(float v) {
    v *= g.gain;
    float a = fabsf(v);
    if (a <= 0.7f) return v;
    float over = (a - 0.7f) / 0.3f;
    float y = 0.7f + 0.3f * (over / (1.0f + over));
    return v < 0 ? -y : y;
}

int64_t vtts_now_us(void) { return esp_timer_get_time(); }
extern int64_t vtts_prof_us[];
extern const int vtts_prof_n;
extern const char *const vtts_prof_names[];

void vtts_par_enable(int on);
static vtts_text_ws s_ws; /* ~40 KB, kept off the task stack */

static void stream_out(const float *pcm, long n) {
    static int16_t buf[1024];
    if (!g.t_first) g.t_first = esp_timer_get_time();
    for (long i = 0; i < n;) {
        int k = 0;
        for (; k < 1024 && i < n; k++, i++) {
            buf[k] = (int16_t)lrintf(shape(pcm[i]) * 32767.0f);
        }
        int64_t tb = esp_timer_get_time();
        xStreamBufferSend(g.sb, buf, sizeof(int16_t) * (size_t)k, portMAX_DELAY);
        g.blocked_us += esp_timer_get_time() - tb;
    }
}

static int chunk_cap(void);

static int on_pcm(const float *pcm, long n, void *user) {
    (void)user;
    if (g.streaming && g.sb) stream_out(pcm, n);
    long keep = g.n + n > g.pcm_cap ? g.pcm_cap - g.n : n;
    memcpy(g.pcm + g.n, pcm, sizeof(float) * (size_t)keep);
    g.n += keep;
    return !g.streaming && g.n >= g.pcm_cap; /* streaming never stops on the stats buffer */
}

static int on_ids(const int32_t *ids, int n, void *user) {
    (void)user;
    const vtts_model *m = &g.models[g.cur];
    int64_t t0 = esp_timer_get_time();
    /* only the first sentence needs a small first chunk; later ones play from a full buffer */
    int cap = chunk_cap(), first = (g.n == 0 && g.first < cap) ? g.first : cap;
    long s = vtts_synthesize_stream_ex(m, ids, n, g.speed, first, cap, on_pcm, NULL, g.arena, g.arena_bytes);
    g.synth_us += esp_timer_get_time() - t0;
    if (s < 0) { printf("ERROR synth %ld\n", s); return 1; }
    /* 150 ms pause between chunks, like the host renderer */
    long gap = (long)(0.15f * m->sample_rate);
    static const float zeros[512];
    for (long i = 0; i < gap; i += 512) on_pcm(zeros, gap - i < 512 ? gap - i : 512, NULL);
    return 0;
}

/* "ids 1 34 57 ...;1 20 ...": token ids from a front-end on the host (e.g. bilingual text before
 * the device has an English front-end); chunks are separated by ';' */
static int synth_ids(const char *s) {
    static int32_t ids[VTTS_TEXT_MAX_IDS];
    int chunks = 0;
    while (*s) {
        int n = 0;
        while (*s && *s != ';') {
            char *end;
            long v = strtol(s, &end, 10);
            if (end == s) { s++; continue; }
            if (n < VTTS_TEXT_MAX_IDS) ids[n++] = (int32_t)v;
            s = end;
        }
        if (*s == ';') s++;
        if (n) {
            if (on_ids(ids, n, NULL)) break;
            chunks++;
        }
    }
    return chunks;
}

/* text (or "ids ...") -> g.pcm; returns chunks; fills timing */
static int synthesize(const char *text, int64_t *total_us) {
    g.n = 0;
    g.synth_us = 0;
    int64_t t0 = esp_timer_get_time();
    int chunks = strncmp(text, "ids ", 4) == 0 ? synth_ids(text + 4) : vtts_text_to_ids(text, &s_ws, on_ids, NULL);
    *total_us = esp_timer_get_time() - t0;
    return chunks;
}

static void speaker_init(void) {
    const int rates[2] = {OUT_RATE_TRY, OUT_RATE_FALLBACK};
    g.out_rate = board_speaker_open(rates, 2);
    if (!g.out_rate) { ESP_LOGE(TAG, "speaker init failed"); return; }
    g.spk = 1;
    board_speaker_set_vol(g.vol);
    printf("speaker: %d Hz\n", g.out_rate);
}

static void play(void) {
    if (!g.spk || g.n == 0) return;
    const int sr = g.models[g.cur].sample_rate;
    static int16_t block[512];
    double step = (double)sr / g.out_rate, pos = 0.0;
    while (pos < g.n - 1) {
        int k = 0;
        for (; k < 512 && pos < g.n - 1; k++, pos += step) {
            long i = (long)pos;
            float f = (float)(pos - i), v = g.pcm[i] * (1.0f - f) + g.pcm[i + 1] * f; /* linear resample */
            block[k] = (int16_t)lrintf(shape(v) * 32767.0f);
        }
        board_speaker_write(block, k);
    }
}

/* speaker task: plays whatever the synthesizer streams (requires the model rate) */
/* Prebuffer before playback starts: the smallest amount of audio, at a chunk boundary, after which
 * every later chunk is ready before playback reaches it. Simulated over the chunk schedule (first
 * chunk, then doubling up to g.chunk) with the measured RTF of the current model plus a margin. */
#define RTF_MARGIN 1.25f
#define PREBUF_SLACK_S 0.05f
static float prebuffer_sec(int cap) {
    const vtts_model *m = &g.models[g.cur];
    float fr = (float)m->hop / (float)m->sample_rate, r = g.rtf[g.cur] * RTF_MARGIN, A[64];
    int nk = 0, c = g.first < cap ? g.first : cap;
    for (float acc = 0.0f; nk < 64 && acc < 8.0f; c = 2 * c < cap ? 2 * c : cap) A[nk++] = acc += c * fr;
    for (int j = 0; j < nk; j++) {
        int ok = 1;
        for (int k = j + 1; k < nk && ok; k++) ok = r * A[k] + PREBUF_SLACK_S <= r * A[j] + A[k - 1];
        if (ok) return A[j];
    }
    return A[nk - 1];
}

/* Largest chunk (<= g.chunk) that still gives the smallest prebuffer: smaller chunks let a slow
 * model start sooner, larger ones are a little cheaper to synthesize. */
static int chunk_cap(void) {
    static const int caps[] = {128, 96, 64, 48, 32};
    int best = caps[sizeof caps / sizeof caps[0] - 1] < g.chunk ? caps[sizeof caps / sizeof caps[0] - 1] : g.chunk;
    float best_s = prebuffer_sec(best);
    for (size_t i = 0; i < sizeof caps / sizeof caps[0]; i++) {
        if (caps[i] > g.chunk) continue;
        float s = prebuffer_sec(caps[i]);
        if (s < best_s - 1e-3f || (s < best_s + 1e-3f && caps[i] > best)) { best = caps[i]; best_s = s; }
    }
    return best;
}

static size_t prebuffer_bytes(void) {
    return (size_t)(prebuffer_sec(chunk_cap()) * (float)g.models[g.cur].sample_rate) * sizeof(int16_t);
}

static void speaker_task(void *arg) {
    (void)arg;
    static int16_t block[512];
    for (;;) {
        xSemaphoreTake(g.utt_start, portMAX_DELAY);
        /* buffer enough of the new utterance (or all of it) before starting */
        while (xStreamBufferBytesAvailable(g.sb) < prebuffer_bytes() && !g.synth_done) vTaskDelay(pdMS_TO_TICKS(5));
        g.t_play = esp_timer_get_time();
        for (;;) {
            size_t got = xStreamBufferReceive(g.sb, block, sizeof block, pdMS_TO_TICKS(2));
            if (got) {
                if (g.spk) board_speaker_write(block, (int)(got / sizeof(int16_t)));
                continue;
            }
            if (g.synth_done) break;  /* utterance finished */
            g.underruns++;           /* synthesis fell behind playback */
            while (!xStreamBufferBytesAvailable(g.sb) && !g.synth_done) vTaskDelay(pdMS_TO_TICKS(1));
        }
        xSemaphoreGive(g.utt_end);
    }
}

static void report(const char *tag, int idx, int chunks, int64_t total_us) {
    double audio = (double)g.n / g.models[g.cur].sample_rate;
    double rms = 0;
    for (long i = 0; i < g.n; i++) rms += (double)g.pcm[i] * g.pcm[i];
    rms = g.n ? sqrt(rms / g.n) : 0;
    printf("%s model=%c chunk=%d idx=%d chunks=%d audio=%.2fs synth=%.3fs total=%.3fs RTF=%.3f rms=%.4f arena=%u(%s)\n",
           tag, g.cur ? 'M' : 'S', g.chunk, idx, chunks, audio, g.synth_us / 1e6, total_us / 1e6,
           audio > 0 ? (total_us / 1e6) / audio : 0.0, rms, (unsigned)g.arena_bytes, g.arena_where);
}

/* CPU load per core over an interval, from the FreeRTOS idle tasks' run-time counters */
typedef struct { int64_t t; configRUN_TIME_COUNTER_TYPE idle[2]; } cpu_snap_t;

static cpu_snap_t cpu_snap(void) {
    cpu_snap_t s = {esp_timer_get_time(), {0, 0}};
    for (int c = 0; c < 2; c++) s.idle[c] = ulTaskGetIdleRunTimeCounterForCore(c);
    return s;
}

static void cpu_report(const cpu_snap_t *a) {
    cpu_snap_t b = cpu_snap();
    double span = (double)(b.t - a->t); /* run-time counters tick in microseconds (esp_timer) */
    printf("CPU core0 %.0f%% core1 %.0f%% over %.1fs\n", 100.0 * (1.0 - (double)(b.idle[0] - a->idle[0]) / span),
           100.0 * (1.0 - (double)(b.idle[1] - a->idle[1]) / span), span / 1e6);
}

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

static void handle(char *line) {
    /* skip noise from port open or reset: control bytes and bytes that cannot start UTF-8 */
    for (unsigned char ch; (ch = (unsigned char)*line) && (ch < 0x20 || ch == 0x7f || (ch >= 0x80 && ch < 0xc2) || ch >= 0xf5);)
        line++;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\r' || line[len - 1] == '\n' || line[len - 1] == ' ')) line[--len] = 0;
    if (!len) return;
    if (strcmp(line, "bench") == 0) {
        for (int k = 0; k < 4; k++) {
            int64_t us;
            int c = synthesize(BENCH[k], &us);
            report("REPORT", k, c, us);
        }
        printf("DONE\n");
        return;
    }
    if (strncmp(line, "model ", 6) == 0) {
        g.cur = (line[6] == 'm' || line[6] == 'M') ? 1 : 0;
        printf("model %c\nDONE\n", g.cur ? 'M' : 'S');
        return;
    }
#if CONFIG_IDF_TARGET_ESP32S3
    if (strcmp(line, "fusetest") == 0) { /* fused ld.ip kernel: kernel x memory x cores x interrupts */
        extern int vtts_s3_kernel;
        uint32_t r = esp_random();
        int8_t *ws = heap_caps_aligned_alloc(16, 64 * 480, MALLOC_CAP_INTERNAL), *xs = heap_caps_aligned_alloc(16, 480, MALLOC_CAP_INTERNAL);
        int8_t *wp = heap_caps_aligned_alloc(16, 64 * 480, MALLOC_CAP_SPIRAM), *xp = heap_caps_aligned_alloc(16, 480, MALLOC_CAP_SPIRAM);
        static int32_t out[64], ref[64];
        if (!ws || !xs || !wp || !xp) { printf("fusetest: out of memory\nDONE\n"); return; }
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
        printf("DONE\n");
        return;
    }
#endif
    if (strcmp(line, "selftest") == 0) { /* PIE dot vs scalar on random aligned vectors */
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
        printf("SELFTEST mismatches=%d\nDONE\n", bad);
        return;
    }
    if (strncmp(line, "dump ", 5) == 0) { /* synthesize (no playback) and send int16 PCM as base64 */
        static const char b64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        int64_t us;
        g.streaming = 0;
        int c = synthesize(line + 5, &us);
        report("DUMPED", 0, c, us);
        printf("PCM %d %ld\n", g.models[g.cur].sample_rate, g.n);
        static char out[1 + 4 * 64 + 2];
        uint8_t buf[192];
        for (long i = 0; i < g.n;) {
            int nb = 0;
            for (; nb < 192 && i < g.n; i++) {
                float v = g.pcm[i] > 1.0f ? 1.0f : g.pcm[i] < -1.0f ? -1.0f : g.pcm[i];
                int16_t q = (int16_t)lrintf(v * 32767.0f);
                buf[nb++] = (uint8_t)(q & 0xff);
                buf[nb++] = (uint8_t)((q >> 8) & 0xff);
            }
            int k = 0;
            out[k++] = 'B';
            for (int j = 0; j < nb; j += 3) {
                uint32_t w = (uint32_t)buf[j] << 16 | (j + 1 < nb ? (uint32_t)buf[j + 1] << 8 : 0) | (j + 2 < nb ? buf[j + 2] : 0);
                out[k++] = b64[(w >> 18) & 63];
                out[k++] = b64[(w >> 12) & 63];
                out[k++] = j + 1 < nb ? b64[(w >> 6) & 63] : '=';
                out[k++] = j + 2 < nb ? b64[w & 63] : '=';
            }
            out[k] = 0;
            puts(out);
        }
        printf("DONE\n");
        return;
    }
    if (strcmp(line, "prof") == 0) {
        int64_t tot = 0;
        for (int i = 0; i < vtts_prof_n; i++) tot += vtts_prof_us[i];
        for (int i = 0; i < vtts_prof_n; i++)
            printf("PROF %-14s %8.3fs %5.1f%%\n", vtts_prof_names[i], vtts_prof_us[i] / 1e6,
                   tot ? 100.0 * vtts_prof_us[i] / tot : 0.0);
        memset(vtts_prof_us, 0, sizeof(int64_t) * (size_t)vtts_prof_n);
        printf("DONE\n");
        return;
    }
    if (strncmp(line, "cores ", 6) == 0) {
        int c = atoi(line + 6) >= 2;
        vtts_par_enable(c);
        printf("cores %d\nDONE\n", c ? 2 : 1);
        return;
    }
    if (strncmp(line, "first ", 6) == 0) {
        g.first = atoi(line + 6) < 1 ? 1 : atoi(line + 6);
        printf("first %d\nDONE\n", g.first);
        return;
    }
    if (strncmp(line, "chunk ", 6) == 0) {
        int c = atoi(line + 6);
        g.chunk = c < 1 ? 1 : c > MAX_CHUNK ? MAX_CHUNK : c;
        printf("chunk %d\nDONE\n", g.chunk);
        return;
    }
    if (strncmp(line, "expr ", 5) == 0) { /* expressiveness for prosody models, 0.5..2.5 */
        float e = (float)atof(line + 5);
        e = e < 0.5f ? 0.5f : e > 2.5f ? 2.5f : e;
        for (int k = 0; k < 2; k++) vtts_set_expressiveness(&g.models[k], e);
        printf("expr %.2f (prosody model: %d)\nDONE\n", e, g.models[g.cur].prosody);
        return;
    }
    if (strncmp(line, "speed ", 6) == 0) { /* length scale 0.7..1.6 */
        float v = (float)atof(line + 6);
        g.speed = v < 0.7f ? 0.7f : v > 1.6f ? 1.6f : v;
        printf("speed %.2f\nDONE\n", g.speed);
        return;
    }
    if (strncmp(line, "gain ", 5) == 0) { /* gain in dB, 0..24 */
        float db = (float)atof(line + 5);
        db = db < 0 ? 0 : db > 24 ? 24 : db;
        g.gain = powf(10.0f, db / 20.0f);
        printf("gain %.1f dB\nDONE\n", db);
        return;
    }
    if (strncmp(line, "vol ", 4) == 0) {
        g.vol = atoi(line + 4);
        if (g.spk) board_speaker_set_vol(g.vol);
        printf("vol %d\nDONE\n", g.vol);
        return;
    }
    int64_t us;
    int direct = g.sb && g.out_rate == g.models[g.cur].sample_rate;
    g.streaming = direct;
    g.t_first = g.t_play = 0;
    g.blocked_us = 0;
    g.underruns = 0;
    g.synth_done = 0;
    cpu_snap_t cs = cpu_snap();
    if (direct) xSemaphoreGive(g.utt_start);
    int64_t t0 = esp_timer_get_time();
    int c = synthesize(line, &us);
    g.synth_done = 1;
    g.streaming = 0;
    report("SAID", 0, c, us);
    { /* learn the synthesis-only RTF: rises at once, falls slowly */
        double audio = (double)g.n / g.models[g.cur].sample_rate, rt = audio > 0.3 ? (g.synth_us - g.blocked_us) / 1e6 / audio : 0;
        if (rt > 0) g.rtf[g.cur] = rt > g.rtf[g.cur] ? (float)rt : 0.8f * g.rtf[g.cur] + 0.2f * (float)rt;
        printf("rtf %.3f (est %.3f), next: chunk %d, prebuffer %.0f ms\n", rt, g.rtf[g.cur], chunk_cap(),
               prebuffer_bytes() / 2.0 / g.models[g.cur].sample_rate * 1e3);
    }
    if (direct) {
        xSemaphoreTake(g.utt_end, portMAX_DELAY); /* playback finished */
        printf("first chunk %.0f ms, playback started %.0f ms, underruns %d\n", (g.t_first - t0) / 1e3,
               g.t_play ? (g.t_play - t0) / 1e3 : -1.0, g.underruns);
        cpu_report(&cs); /* synthesis and playback of the whole utterance */
    } else {
        play();
    }
    printf("DONE\n");
}

/* console input: UART (P4 boards, USB bridge) or the S3's own USB-Serial-JTAG */
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
static void console_init(void) {
    usb_serial_jtag_driver_config_t cfg = {.rx_buffer_size = 4096, .tx_buffer_size = 4096};
    usb_serial_jtag_driver_install(&cfg);
    usb_serial_jtag_vfs_use_driver();
}
static int console_read(uint8_t *ch) { return usb_serial_jtag_read_bytes(ch, 1, portMAX_DELAY); }
#else
static void console_init(void) { uart_driver_install(CONFIG_ESP_CONSOLE_UART_NUM, 4096, 0, 0, NULL, 0); }
static int console_read(uint8_t *ch) { return uart_read_bytes(CONFIG_ESP_CONSOLE_UART_NUM, ch, 1, portMAX_DELAY); }
#endif

static void console_task(void *arg) {
    (void)arg;
    console_init();
    static char line[2048];
    size_t n = 0;
    printf("board %s\n", board_name());
    printf("READY (type a Vietnamese sentence, or: bench | model s|m | vol N | gain dB)\n");
    for (;;) {
        uint8_t ch;
        if (console_read(&ch) != 1) continue;
        if (ch == '\n' || ch == '\r') {
            line[n] = 0;
            if (n) handle(line);
            n = 0;
        } else if (n < sizeof(line) - 1) {
            line[n++] = (char)ch;
        }
    }
}

void app_main(void) {
    board_early_init();
    const uint8_t *starts[2] = {model_s_start, model_m_start}, *ends[2] = {model_s_end, model_m_end};
    size_t need = 0;
    for (int k = 0; k < 2; k++) {
        /* weights are read many times per second: copy them from flash (XIP) to PSRAM */
        size_t bytes = (size_t)(ends[k] - starts[k]);
        uint8_t *blob = heap_caps_aligned_alloc(16, bytes, MALLOC_CAP_SPIRAM);
        const uint8_t *src = starts[k];
        if (blob) { memcpy(blob, starts[k], bytes); src = blob; }
        printf("model %c weights in %s\n", k ? 'M' : 'S', blob ? "psram" : "flash");
        int rc = vtts_init(&g.models[k], src, bytes);
        size_t ab = rc ? 0 : vtts_stream_arena_bytes(&g.models[k], VTTS_TEXT_MAX_IDS, MAX_CHUNK);
        printf("model %c: %u bytes, init %d, arena %u\n", k ? 'M' : 'S', (unsigned)(ends[k] - starts[k]), rc,
               (unsigned)ab);
        if (ab > need) need = ab;
    }
    g.arena_bytes = need;
    g.arena = heap_caps_aligned_alloc(16, need, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    g.arena_where = "sram";
    if (!g.arena) { g.arena = heap_caps_aligned_alloc(16, need, MALLOC_CAP_SPIRAM); g.arena_where = "psram"; }
    /* the most reused streaming buffers go to internal SRAM; keep 64 KB for drivers and stacks */
    {
        long room = (long)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) - 65536;
        size_t fast_n = room > FAST_SCRATCH_MAX ? FAST_SCRATCH_MAX : room > 16384 ? (size_t)room : 0;
        void *fast = fast_n ? heap_caps_aligned_alloc(16, fast_n, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) : NULL;
        vtts_set_fast_scratch(fast, fast ? fast_n : 0);
        printf("fast scratch %u bytes in sram\n", fast ? (unsigned)fast_n : 0u);
    }
    g.sb = xStreamBufferCreateWithCaps(4 * 22050 * sizeof(int16_t), 1024, MALLOC_CAP_SPIRAM);
    /* up to MAX_SECONDS, or what PSRAM has left (keep 64 KB spare) */
    long fit = ((long)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM) - 65536) / (long)sizeof(float);
    g.pcm_cap = (long)MAX_SECONDS * 22050 < fit ? (long)MAX_SECONDS * 22050 : fit;
    g.pcm = g.pcm_cap > 22050 ? heap_caps_malloc(sizeof(float) * (size_t)g.pcm_cap, MALLOC_CAP_SPIRAM) : NULL;
    printf("arena %u in %s; pcm %.1f s; free internal %u, psram %u\n", (unsigned)need, g.arena_where,
           g.pcm_cap / 22050.0,
           (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL), (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    if (!g.arena || !g.pcm) { printf("ERROR out of memory\n"); return; }
    g.gain = powf(10.0f, BOARD_DEFAULT_GAIN_DB / 20.0f);
    speaker_init();
    g.utt_start = xSemaphoreCreateBinary();
    g.utt_end = xSemaphoreCreateBinary();
    if (g.sb && g.spk) xTaskCreatePinnedToCore(speaker_task, "speaker", 4096, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(console_task, "console", 16384, NULL, 5, NULL, 0);
}
