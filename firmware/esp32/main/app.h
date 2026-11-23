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
#define KEEP_SECONDS 60  /* PCM kept by `dump` and resampled playback (allocated only for them) */

typedef struct {
    vtts_model models[2];
    int cur; /* 0 = S, 1 = M */
    void *arena;
    size_t arena_bytes;
    const char *arena_where;
    size_t fast_bytes; /* fast scratch in internal RAM */
    int16_t *pcm;    /* NULL, or KEEP_SECONDS of audio while `dump` or resampled playback needs it */
    long pcm_cap, n; /* samples kept, samples synthesized */
    int chunks_done; /* text chunks synthesized in the current utterance */
    double sumsq;    /* for the RMS on the report line, accumulated while synthesizing */
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
    int debuzz;         /* 0 = off, else dB taken off above ~6 kHz before the speaker (speaker_filter_set) */
    float speed;        /* length_scale: > 1 reads slower */
    int64_t blocked_us; /* time the synthesizer waited on a full playback buffer */
    float rtf[2];       /* measured RTF per model (synthesis only), sets the prebuffer */
    vtts_text_ws *ws;   /* text front-end workspace, PSRAM */
    vtts_lex lex;       /* English lexicon (VLEX blob in flash) */
    int has_lex;
    vtts_zlex zh;       /* Mandarin readings (ZLEX blob in flash), for zh-en models */
    int has_zh;
    vtts_jlex ja;       /* Japanese readings and NFKC data (JLEX blob in flash), for ja-en models */
    int has_ja;
    vtts_rlex ru;       /* Russian stress tables (RLEX blob in flash), for ru-en models */
    int has_ru;
    /* text mode per model, from its token set (vtts_text_default_lang, console `lang`);
     * -1: the token set has no device front-end (unknown): only `ids` */
    int lang[2];
} app_t;

extern app_t g;

extern const uint8_t model_s_start[] asm("_binary_model_s_vtts_start");
extern const uint8_t model_s_end[] asm("_binary_model_s_vtts_end");
extern const uint8_t model_m_start[] asm("_binary_model_m_vtts_start");
extern const uint8_t model_m_end[] asm("_binary_model_m_vtts_end");
extern const uint8_t lex_en_start[] asm("_binary_lex_en_bin_start");
extern const uint8_t lex_en_end[] asm("_binary_lex_en_bin_end");
#if VTTS_EMBED_ZH /* main/lex_zh.bin was present at build time (build.sh builds it) */
extern const uint8_t lex_zh_start[] asm("_binary_lex_zh_bin_start");
extern const uint8_t lex_zh_end[] asm("_binary_lex_zh_bin_end");
#endif
#if VTTS_EMBED_JA /* main/lex_ja.bin was present at build time (build.sh builds it) */
extern const uint8_t lex_ja_start[] asm("_binary_lex_ja_bin_start");
extern const uint8_t lex_ja_end[] asm("_binary_lex_ja_bin_end");
#endif
#if VTTS_EMBED_RU /* Russian is enabled (a ru-en model is embedded) and main/lex_ru.bin was built */
extern const uint8_t lex_ru_start[] asm("_binary_lex_ru_bin_start");
extern const uint8_t lex_ru_end[] asm("_binary_lex_ru_bin_end");
#endif

/* synth.c */
int synth_text(const char *text, int64_t *total_us); /* text or "ids ..." -> PCM; chunks */
const char *synth_lang_name(int k); /* text mode of model k, or "none" (ids only) */
void synth_report(const char *tag, int idx, int chunks, int64_t total_us);
void synth_say(const char *text);  /* speak, then SAID / timing / CPU lines */
void synth_dump(const char *text); /* PCM as base64 lines, no playback */
void synth_bench(void);

/* speaker.c */
void speaker_init(void);
void speaker_start(void);                     /* playback task (resamples when the speaker runs at another rate) */
int speaker_can_stream(void);                 /* the playback task can play the current model (rate or resampler) */
void speaker_stream(const float *pcm, long n); /* queue model-rate PCM for playback */
void speaker_play_buffer(void);               /* play g.pcm resampled (no stream buffer, or no resampler) */
int pcm_keep(void);                           /* allocate g.pcm (PSRAM) for the next utterance */
void pcm_release(void);
int speaker_chunk_cap(void);
void speaker_filter_set(int db); /* de-buzz high-shelf cut in dB, 0 = off */
void speaker_filter_reset(void); /* clear the filter state before an utterance */
size_t speaker_prebuffer_bytes(void);

/* selftest.c */
int selftest_run(void);
int fusetest_run(void);
int memtest_run(void); /* SIMD kernel on two cores over ~2 MB of PSRAM weights */

/* console.c */
void console_start(void);
