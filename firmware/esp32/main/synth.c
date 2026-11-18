/* SPDX-License-Identifier: Apache-2.0 */
/* synth.c -- text (or token ids from a host front-end) -> PCM with the vtts runtime, and the
 * SAID / DUMPED / REPORT lines of the console protocol. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/task.h"

/* four fixed sentences per text front-end (the same content in each language) */
static const char *const BENCH[] = {
    "Xin chào, tôi là trợ lý giọng nói của bạn.",
    "Nhiệt độ trong phòng hiện là 26 độ, độ ẩm 65%.",
    "Báo thức lúc 6:30 sáng mai đã được đặt.",
    "Hôm nay là thứ Bảy, ngày 14/11/2026.",
};
static const char *const BENCH_ZH[] = {
    "你好，我是你的语音助手。",
    "现在室内温度是26度，湿度65%。",
    "明天早上6:30的闹钟已经设好了。",
    "今天是2026年11月14日，星期六。",
};

const char *synth_lang_name(int k) { return g.lang[k] < 0 ? "none" : vtts_text_lang_name((vtts_lang)g.lang[k]); }

/* PCM kept only while `dump` or resampled playback needs it: up to KEEP_SECONDS of int16 in PSRAM,
 * or less if PSRAM is short (keep 64 KB spare) */
int pcm_keep(void) {
    if (g.pcm) return 1;
    long want = (long)KEEP_SECONDS * g.models[g.cur].sample_rate;
    long fit = ((long)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM) - 65536) / (long)sizeof(int16_t);
    g.pcm_cap = want < fit ? want : fit;
    g.pcm = g.pcm_cap > 22050 ? heap_caps_malloc(sizeof(int16_t) * (size_t)g.pcm_cap, MALLOC_CAP_SPIRAM) : NULL;
    if (!g.pcm) { g.pcm_cap = 0; printf("ERROR no PSRAM for the PCM buffer\n"); }
    return g.pcm != NULL;
}

void pcm_release(void) {
    heap_caps_free(g.pcm);
    g.pcm = NULL;
    g.pcm_cap = 0;
}

static int on_pcm(const float *pcm, long n, void *user) {
    (void)user;
    if (g.streaming && g.sb) speaker_stream(pcm, n);
    for (long i = 0; i < n; i++) g.sumsq += (double)pcm[i] * pcm[i];
    if (g.pcm) {
        for (long i = 0; i < n && g.n + i < g.pcm_cap; i++) {
            float v = pcm[i] > 1.0f ? 1.0f : pcm[i] < -1.0f ? -1.0f : pcm[i];
            g.pcm[g.n + i] = (int16_t)lrintf(v * 32767.0f);
        }
    }
    g.n += n;
    return !g.streaming && g.pcm && g.n >= g.pcm_cap; /* a dump stops when its buffer is full */
}

static int on_ids(const int32_t *ids, int n, void *user) {
    (void)user;
    const vtts_model *m = &g.models[g.cur];
    int64_t t0 = esp_timer_get_time();
    /* only the first sentence needs a small first chunk; later ones play from a full buffer */
    int cap = speaker_chunk_cap(), first = (g.n == 0 && g.first < cap) ? g.first : cap;
    long s = vtts_synthesize_stream_ex(m, ids, n, g.speed, first, cap, on_pcm, NULL, g.arena, g.arena_bytes);
    g.synth_us += esp_timer_get_time() - t0;
    if (s < 0) { printf("ERROR synth %ld\n", s); return 1; }
    /* 150 ms pause between chunks, like the host renderer */
    long gap = (long)(0.15f * m->sample_rate);
    static const float zeros[512];
    for (long i = 0; i < gap; i += 512) on_pcm(zeros, gap - i < 512 ? gap - i : 512, NULL);
    return 0;
}

/* "1 34 57 ...;1 20 ...": token ids from a front-end on the host (e.g. bilingual text), chunks
 * separated by ';' */
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

int synth_text(const char *text, int64_t *total_us) {
    g.n = 0;
    g.sumsq = 0;
    g.synth_us = 0;
    int64_t t0 = esp_timer_get_time();
    int chunks;
    if (strncmp(text, "ids ", 4) == 0) chunks = synth_ids(text + 4);
    else if (g.lang[g.cur] < 0) { /* ko-en, ja-en: no device front-end yet */
        printf("ERROR token set %s has no on-device text front-end; send ids (scripts/device/say.py --lang)\n",
               vtts_token_set_name(vtts_token_set(&g.models[g.cur])));
        chunks = 0;
    } else { /* the mode follows the model's token set: V1 (v1), VI|EN|AUTO (vi-en), ZH (zh-en) */
        vtts_text_opts o = {.lang = (vtts_lang)g.lang[g.cur], .lex = g.has_lex ? &g.lex : NULL,
                            .zh = g.has_zh ? &g.zh : NULL};
        chunks = vtts_text_to_ids_ex(text, g.ws, &o, on_ids, NULL);
    }
    *total_us = esp_timer_get_time() - t0;
    return chunks;
}

void synth_report(const char *tag, int idx, int chunks, int64_t total_us) {
    double audio = (double)g.n / g.models[g.cur].sample_rate;
    double rms = g.n ? sqrt(g.sumsq / g.n) : 0;
    printf("%s model=%c chunk=%d idx=%d chunks=%d audio=%.2fs synth=%.3fs total=%.3fs RTF=%.3f rms=%.4f arena=%u(%s)\n",
           tag, g.cur ? 'M' : 'S', g.chunk, idx, chunks, audio, g.synth_us / 1e6, total_us / 1e6,
           audio > 0 ? (total_us / 1e6) / audio : 0.0, rms, (unsigned)g.arena_bytes, g.arena_where);
}

void synth_bench(void) {
    const char *const *set = g.lang[g.cur] == VTTS_LANG_ZH ? BENCH_ZH : BENCH;
    for (int k = 0; k < 4; k++) {
        int64_t us;
        int c = synth_text(set[k], &us);
        synth_report("REPORT", k, c, us);
    }
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

void synth_say(const char *text) {
    int64_t us;
    int direct = g.sb && g.out_rate == g.models[g.cur].sample_rate; /* stream to the speaker task */
    if (!direct && !pcm_keep()) return; /* the speaker runs at another rate: resample a kept copy */
    g.streaming = direct;
    g.t_first = g.t_play = 0;
    g.blocked_us = 0;
    g.underruns = 0;
    g.synth_done = 0;
    cpu_snap_t cs = cpu_snap();
    if (direct) xSemaphoreGive(g.utt_start);
    int64_t t0 = esp_timer_get_time();
    int c = synth_text(text, &us);
    g.synth_done = 1;
    g.streaming = 0;
    synth_report("SAID", 0, c, us);
    { /* learn the synthesis-only RTF: rises at once, falls slowly */
        double audio = (double)g.n / g.models[g.cur].sample_rate, rt = audio > 0.3 ? (g.synth_us - g.blocked_us) / 1e6 / audio : 0;
        if (rt > 0) g.rtf[g.cur] = rt > g.rtf[g.cur] ? (float)rt : 0.8f * g.rtf[g.cur] + 0.2f * (float)rt;
        printf("rtf %.3f (est %.3f), next: chunk %d, prebuffer %.0f ms\n", rt, g.rtf[g.cur], speaker_chunk_cap(),
               speaker_prebuffer_bytes() / 2.0 / g.models[g.cur].sample_rate * 1e3);
    }
    if (direct) {
        xSemaphoreTake(g.utt_end, portMAX_DELAY); /* playback finished */
        printf("first chunk %.0f ms, playback started %.0f ms, underruns %d\n", (g.t_first - t0) / 1e3,
               g.t_play ? (g.t_play - t0) / 1e3 : -1.0, g.underruns);
        cpu_report(&cs); /* synthesis and playback of the whole utterance */
    } else {
        speaker_play_buffer();
        pcm_release();
    }
}

/* synthesize without playback and send int16 PCM: "PCM <rate> <samples>", then base64 lines "B..." */
void synth_dump(const char *text) {
    static const char b64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    int64_t us;
    g.streaming = 0;
    if (!pcm_keep()) return;
    int c = synth_text(text, &us);
    synth_report("DUMPED", 0, c, us);
    long n = g.n < g.pcm_cap ? g.n : g.pcm_cap;
    printf("PCM %d %ld\n", g.models[g.cur].sample_rate, n);
    static char out[1 + 4 * 64 + 2];
    uint8_t buf[192];
    for (long i = 0; i < n;) {
        int nb = 0;
        for (; nb < 192 && i < n; i++) {
            int16_t q = g.pcm[i];
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
    pcm_release();
}
