/* SPDX-License-Identifier: Apache-2.0 */
/* main.c -- vtts firmware for ESP32-P4 and ESP32-S3 boards: type a sentence on the serial console
 * and the board speaks it. Everything runs on the chip: text -> token ids (runtime/src/vtts_text.c)
 * -> int8 student model (vtts runtime, SIMD kernels in runtime/ports/) -> speaker (board support
 * in bsp/ and boards/<id>/).
 *
 * Modules: main.c (start-up), synth.c (synthesis and report lines), speaker.c (playback and
 * prebuffer), console.c (commands), selftest.c (kernel checks); see app.h.
 *
 * Console (one line per command; every command ends with a DONE line; `help` lists them):
 *   <sentence>            synthesize and speak: SAID line with RTF, first chunk / playback start,
 *                         underruns and CPU load per core
 *   model s|m             lite or quality model
 *   vol 0-100, gain dB    volume; the digital gain has a soft limiter
 *   speed 0.7-1.6         speaking rate (higher is slower)
 *   expr 0.5-2.5          intonation range (models with a pitch predictor)
 *   bench, prof           RTF on four fixed sentences; time per synthesis stage
 *   selftest, fusetest    SIMD kernels against plain C, including both cores at once
 *   dump <sentence>       synthesize and send the PCM as base64 (scripts/device/say.py --dump-dir)
 *   ids <ids;ids...>      speak token ids from a host front-end (scripts/device/say.py --lang)
 *   lang <mode>           text mode, valid modes per token set of the current model: v1 vi;
 *                         vi-en vi|en|auto (vi reads English words too); zh-en zh; ko-en ko; hi-en hi;
 *                         ja-en ja. The front-end follows the model's token set (header)
 *   chunk N, first N, cores 1|2   streaming and scheduling knobs for experiments
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "app.h"
#include "bsp.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"

#ifndef FAST_SCRATCH_MAX
/* bytes of internal SRAM for hot synthesis buffers; 0 keeps everything in PSRAM so internal RAM
 * stays free for DMA (about 2% faster with 96 KB on the P4) */
#define FAST_SCRATCH_MAX 0
#endif

#if CONFIG_IDF_TARGET_ESP32S3
#define RTF_INIT_S 0.30f
#define RTF_INIT_M 0.53f
#else
#define RTF_INIT_S 0.18f
#define RTF_INIT_M 0.29f
#endif

app_t g = {.vol = BSP_DEFAULT_VOL, .chunk = 128, .first = 12, .gain = 1.0f, .speed = 1.0f, .rtf = {RTF_INIT_S, RTF_INIT_M},
           .lang = {-1, -1}};

int64_t vtts_now_us(void) { return esp_timer_get_time(); } /* runtime profiling clock */

void app_main(void) {
    bsp_early_init();
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
        /* the text front-end follows the token set recorded in the model (old files: by vocab) */
        int ts = rc ? VTTS_TOKSET_UNKNOWN : vtts_token_set(&g.models[k]);
        vtts_lang l;
        g.lang[k] = vtts_text_default_lang(ts, &l) == 0 ? (int)l : -1;
        printf("model %c: %u bytes, init %d, arena %u, token set %s (%s), lang %s\n", k ? 'M' : 'S', (unsigned)bytes, rc,
               (unsigned)ab, vtts_token_set_name(ts), rc ? "-" : g.models[k].token_set_in_file ? "header" : "vocab",
               synth_lang_name(k));
        if (ab > need) need = ab;
    }
    /* English lexicon for bilingual models, read in place from flash */
    g.has_lex = vtts_lex_init(&g.lex, lex_en_start, (size_t)(lex_en_end - lex_en_start)) == 0;
    printf("lexicon %u bytes, %s\n", (unsigned)(lex_en_end - lex_en_start), g.has_lex ? "ok" : "missing");
#if VTTS_EMBED_ZH
    /* Mandarin readings for zh-en models, read in place from flash */
    g.has_zh = vtts_zlex_init(&g.zh, lex_zh_start, (size_t)(lex_zh_end - lex_zh_start)) == 0;
    printf("zh readings %u bytes, %s\n", (unsigned)(lex_zh_end - lex_zh_start), g.has_zh ? "ok" : "invalid");
#else
    printf("zh readings not embedded\n");
#endif
#if VTTS_EMBED_JA
    /* Japanese readings for ja-en models, read in place from flash */
    g.has_ja = vtts_jlex_init(&g.ja, lex_ja_start, (size_t)(lex_ja_end - lex_ja_start)) == 0;
    printf("ja readings %u bytes, %s\n", (unsigned)(lex_ja_end - lex_ja_start), g.has_ja ? "ok" : "invalid");
#else
    printf("ja readings not embedded\n");
#endif
    for (int k = 0; k < 2; k++) {
        if (g.lang[k] == VTTS_LANG_ZH && !g.has_zh) printf("WARNING model %c is zh-en but has no zh readings: Han text is skipped\n", k ? 'M' : 'S');
        if (g.lang[k] == VTTS_LANG_JA && !g.has_ja) printf("WARNING model %c is ja-en but has no ja readings: Japanese text is skipped\n", k ? 'M' : 'S');
    }
    g.arena_bytes = need;
    g.arena = heap_caps_aligned_alloc(16, need, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    g.arena_where = "sram";
    if (!g.arena) { g.arena = heap_caps_aligned_alloc(16, need, MALLOC_CAP_SPIRAM); g.arena_where = "psram"; }
    { /* optional fast scratch for the most reused streaming buffers; keep 64 KB for drivers and stacks */
        long room = (long)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) - 65536;
        size_t fast_n = room > FAST_SCRATCH_MAX ? FAST_SCRATCH_MAX : room > 16384 ? (size_t)room : 0;
        void *fast = fast_n ? heap_caps_aligned_alloc(16, fast_n, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) : NULL;
        vtts_set_fast_scratch(fast, fast ? fast_n : 0);
        printf("fast scratch %u bytes in sram\n", fast ? (unsigned)fast_n : 0u);
    }
    g.sb = xStreamBufferCreateWithCaps(4 * 22050 * sizeof(int16_t), 1024, MALLOC_CAP_SPIRAM);
    g.ws = heap_caps_malloc(sizeof *g.ws, MALLOC_CAP_SPIRAM);
    /* no PCM buffer while speaking: audio streams to the speaker; `dump` allocates one when needed */
    printf("arena %u in %s; free internal %u, psram %u\n", (unsigned)need, g.arena_where,
           (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL), (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    if (!g.arena || !g.ws) { printf("ERROR out of memory\n"); return; }
    g.gain = powf(10.0f, BSP_DEFAULT_GAIN_DB / 20.0f);
    speaker_init();
    speaker_start();
    console_start();
}
