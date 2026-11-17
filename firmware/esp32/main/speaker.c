/* SPDX-License-Identifier: Apache-2.0 */
/* speaker.c -- playback: gain with a soft limiter, the stream buffer between synthesis and the
 * speaker task, and the prebuffer / chunk size derived from the measured RTF. */
#include <math.h>

#include "app.h"
#include "bsp.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/task.h"

#define OUT_RATE_TRY 22050
#define OUT_RATE_FALLBACK 16000

static const char *TAG = "speaker";

/* gain + soft limiter: linear below 0.7, smoothly saturating to 1.0 above */
static inline float shape(float v) {
    v *= g.gain;
    float a = fabsf(v);
    if (a <= 0.7f) return v;
    float over = (a - 0.7f) / 0.3f;
    float y = 0.7f + 0.3f * (over / (1.0f + over));
    return v < 0 ? -y : y;
}

void speaker_init(void) {
    const int rates[2] = {OUT_RATE_TRY, OUT_RATE_FALLBACK};
    g.out_rate = bsp_speaker_open(rates, 2);
    if (!g.out_rate) { ESP_LOGE(TAG, "speaker init failed"); return; }
    g.spk = 1;
    bsp_speaker_set_vol(g.vol);
    printf("speaker: %d Hz\n", g.out_rate);
}

void speaker_stream(const float *pcm, long n) {
    static int16_t buf[1024];
    if (!g.t_first) g.t_first = esp_timer_get_time();
    for (long i = 0; i < n;) {
        int k = 0;
        for (; k < 1024 && i < n; k++, i++) buf[k] = (int16_t)lrintf(shape(pcm[i]) * 32767.0f);
        int64_t tb = esp_timer_get_time();
        xStreamBufferSend(g.sb, buf, sizeof(int16_t) * (size_t)k, portMAX_DELAY);
        g.blocked_us += esp_timer_get_time() - tb;
    }
}

void speaker_play_buffer(void) {
    long n = g.n < g.pcm_cap ? g.n : g.pcm_cap;
    if (!g.spk || !g.pcm || n == 0) return;
    const int sr = g.models[g.cur].sample_rate;
    static int16_t block[512];
    double step = (double)sr / g.out_rate, pos = 0.0;
    while (pos < n - 1) {
        int k = 0;
        for (; k < 512 && pos < n - 1; k++, pos += step) {
            long i = (long)pos;
            float f = (float)(pos - i), v = (g.pcm[i] * (1.0f - f) + g.pcm[i + 1] * f) / 32767.0f; /* linear resample */
            block[k] = (int16_t)lrintf(shape(v) * 32767.0f);
        }
        bsp_speaker_write(block, k);
    }
}

/* Prebuffer before playback starts: the smallest amount of audio, at a chunk boundary, after which
 * every later chunk is ready before playback reaches it. Simulated over the chunk schedule (first
 * chunk, then doubling up to the cap) with the measured RTF of the current model plus a margin. */
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
int speaker_chunk_cap(void) {
    static const int caps[] = {128, 96, 64, 48, 32};
    const int nc = (int)(sizeof caps / sizeof caps[0]);
    int best = caps[nc - 1] < g.chunk ? caps[nc - 1] : g.chunk;
    float best_s = prebuffer_sec(best);
    for (int i = 0; i < nc; i++) {
        if (caps[i] > g.chunk) continue;
        float s = prebuffer_sec(caps[i]);
        if (s < best_s - 1e-3f || (s < best_s + 1e-3f && caps[i] > best)) { best = caps[i]; best_s = s; }
    }
    return best;
}

size_t speaker_prebuffer_bytes(void) {
    return (size_t)(prebuffer_sec(speaker_chunk_cap()) * (float)g.models[g.cur].sample_rate) * sizeof(int16_t);
}

/* plays whatever the synthesizer streams (requires the model rate) */
static void speaker_task(void *arg) {
    (void)arg;
    static int16_t block[512];
    for (;;) {
        xSemaphoreTake(g.utt_start, portMAX_DELAY);
        /* buffer enough of the new utterance (or all of it) before starting */
        while (xStreamBufferBytesAvailable(g.sb) < speaker_prebuffer_bytes() && !g.synth_done) vTaskDelay(pdMS_TO_TICKS(5));
        g.t_play = esp_timer_get_time();
        for (;;) {
            size_t got = xStreamBufferReceive(g.sb, block, sizeof block, pdMS_TO_TICKS(2));
            if (got) {
                if (g.spk) bsp_speaker_write(block, (int)(got / sizeof(int16_t)));
                continue;
            }
            if (g.synth_done) break; /* utterance finished */
            g.underruns++;          /* synthesis fell behind playback */
            while (!xStreamBufferBytesAvailable(g.sb) && !g.synth_done) vTaskDelay(pdMS_TO_TICKS(1));
        }
        xSemaphoreGive(g.utt_end);
    }
}

void speaker_start(void) {
    g.utt_start = xSemaphoreCreateBinary();
    g.utt_end = xSemaphoreCreateBinary();
    if (g.sb && g.spk) xTaskCreatePinnedToCore(speaker_task, "speaker", 4096, NULL, 10, NULL, 0);
}
