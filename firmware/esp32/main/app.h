/* SPDX-License-Identifier: Apache-2.0 */
/* app.h -- state and functions shared by the firmware modules:
 *   main.c     start-up: models, memory, tasks
 *   synth.c    text or token ids -> PCM, SAID / DUMPED / REPORT lines
 *   speaker.c  playback: limiter, stream buffer, speaker task, prebuffer from the measured RTF
 *   console.c  serial line input and commands (esp_console)
 *   selftest.c SIMD kernel checks */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/stream_buffer.h"
#include "vtts.h"
#include "vtts_lex.h"
#include "vtts_text.h"

#define MAX_CHUNK 256    /* frames per streaming chunk, upper bound */
#define MAX_SECONDS 120  /* PCM kept per utterance (stats, dump, resampled playback) */

typedef struct {
    vtts_model models[2];
    int cur; /* 0 = S, 1 = M */
    void *arena;
    size_t arena_bytes;
    const char *arena_where;
    float *pcm;      /* MAX_SECONDS of audio, PSRAM */
    long pcm_cap, n; /* samples */
    int64_t synth_us;
    int spk; /* speaker available */
    int out_rate, vol, chunk, first;
    StreamBufferHandle_t sb; /* int16 PCM at the model rate, synthesized ahead of playback */
    int streaming;           /* 1 while a SAID command feeds the speaker */
    int64_t t_first, t_play;
    volatile int synth_done; /* lets the speaker start before the prebuffer fills */
    volatile int underruns;
    SemaphoreHandle_t utt_start, utt_end; /* one utterance at a time between console and speaker */
    float gain;         /* digital gain before the codec (linear), with a soft limiter */
    float speed;        /* length_scale: > 1 reads slower */
    int64_t blocked_us; /* time the synthesizer waited on a full playback buffer */
    float rtf[2];       /* measured RTF per model (synthesis only), sets the prebuffer */
    vtts_text_ws *ws;   /* text front-end workspace, PSRAM */
    vtts_lex lex;       /* English lexicon (VLEX blob in flash) */
    int has_lex;
    vtts_lang lang;     /* mode for bilingual models (token set v2): VI, EN or AUTO */
} app_t;

extern app_t g;

extern const uint8_t model_s_start[] asm("_binary_model_s_vtts_start");
extern const uint8_t model_s_end[] asm("_binary_model_s_vtts_end");
extern const uint8_t model_m_start[] asm("_binary_model_m_vtts_start");
extern const uint8_t model_m_end[] asm("_binary_model_m_vtts_end");
extern const uint8_t lex_en_start[] asm("_binary_lex_en_bin_start");
extern const uint8_t lex_en_end[] asm("_binary_lex_en_bin_end");

/* synth.c */
int synth_text(const char *text, int64_t *total_us); /* text or "ids ..." -> g.pcm; chunks */
void synth_report(const char *tag, int idx, int chunks, int64_t total_us);
void synth_say(const char *text);  /* speak, then SAID / timing / CPU lines */
void synth_dump(const char *text); /* PCM as base64 lines, no playback */
void synth_bench(void);

/* speaker.c */
void speaker_init(void);
void speaker_start(void);                     /* playback task, when the speaker runs at the model rate */
void speaker_stream(const float *pcm, long n); /* queue model-rate PCM for playback */
void speaker_play_buffer(void);               /* play g.pcm resampled (speaker at another rate) */
int speaker_chunk_cap(void);
size_t speaker_prebuffer_bytes(void);

/* selftest.c */
int selftest_run(void);
int fusetest_run(void);

/* console.c */
void console_start(void);
