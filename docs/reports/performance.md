# On-chip performance

Measurements of the int8 runtime on the ESP32-P4 and ESP32-S3 with the v0.4.0 Vietnamese + English models, lite S (0.82M parameters, 1.2 MB) and quality M (1.83M parameters, 2.6 MB), the v0.5.0 Korean + English and Chinese + English models, the v0.6.0 Japanese + English, the v0.7.0 Portuguese (Brazil) + English the v0.8.0 Indonesian + English, Hindi + English and Spanish + English the v0.9.1 update of the `nu-10` M ([below](#nu-10-m-update-v091)) and the v0.9.0 English-only models (`nu-en`: S 0.82M, M 1.83M, the vi-en architecture; the others S 0.83M, M 1.84M; the same architecture with a larger token table). Both vi-en voices (`nam-1`, `nu-10`) give the same numbers within 0.005 RTF; the ko-en voice `nu-ko` is within 0.02 of them, M on the ESP32-S3 slightly faster ([Korean + English](#korean--english-v050)). Both models run on both chips. The README lists the RTF per voice and [voices.md](../voices.md#speed) the summary table.

Everything lives in PSRAM: the models, the working arena (about 1.9 MB) and the activations. Internal SRAM stays free for the application and for DMA.

Method: `bench` (four fixed Vietnamese sentences, no playback), then for eight Vietnamese, English and mixed sentences (the website samples) `dump` (synthesis without playback) and normal playback, which prints the first chunk, playback start, underruns and CPU load. Firmware from the v0.4.0 tree with `lang auto`.

## ESP32-P4

Chip rev 1.3, 360 MHz, 32 MB PSRAM. Measured on a Waveshare ESP32-P4-86-Panel-ETH-2RO; the ESP32-P4-NANO uses the same chip and firmware.

| Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---:|---:|---:|---:|---:|---:|
| S (lite) | 0.17–0.19 | 0.17–0.18 | 0.06–0.14 s | 0.06–0.15 s (median 0.11) | 17–19% / 12–13% | 0 |
| M (quality) | 0.25–0.27 | 0.25–0.28 | 0.11–0.27 s | 0.17–0.34 s (median 0.28) | 25–26% / 19–20% | 1 in 16 sentences |

## ESP32-S3

Waveshare ESP32-S3-Touch-LCD-2.8 (ESP32-S3R8): 240 MHz, 8 MB octal PSRAM, 16 MB flash. The EchoEar 2.0 uses the same chip and firmware.

Current firmware (branch-loop SIMD kernels, see [ESP32-S3: wrong dot products with `loopnez`](#esp32-s3-wrong-dot-products-with-loopnez); es-en `nu-es`, eight website sentences, two cores):

| Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---:|---:|---:|---:|---:|---:|
| S (lite) | 0.31–0.36 | 0.31–0.34 | 0.09–0.18 s | 0.16–0.27 s (median 0.24) | 30–33% / 21–22% | 2 in 8 sentences |
| M (quality) | 0.55–0.59 | 0.55–0.60 | 0.17–0.35 s | 0.26–0.50 s (median 0.43) | 49–53% / 36–39% | 0 |

Before the fix (v0.4.0 firmware, the numbers the v0.4.0–v0.6.0 releases were published with):

| Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---:|---:|---:|---:|---:|---:|
| S (lite) | 0.29–0.31 | 0.29–0.31 | 0.10–0.23 s | 0.17–0.32 s (median 0.26) | 29–30% / 19–20% | 1 in 16 sentences |
| M (quality) | 0.50–0.52 | 0.49–0.53 | 0.19–0.46 s | 0.31–0.61 s (median 0.47) | 44–49% / 31–35% | 2 in 16 sentences |

Compared with the Vietnamese prototype (v0.3.2: P4 S 0.15, M 0.24; S3 S 0.26, M 0.49), S is slower because the vi-en S is larger (0.82M vs 0.77M parameters, wider vocoder), and M is within 0.02.

Playback starts as soon as every later chunk is sure to be ready in time: the firmware learns each model's RTF, simulates the chunk schedule (25% margin) and picks the chunk size that gives the shortest wait. A slower model streams in smaller chunks, which costs a little CPU but lets it start sooner.

- At least 8 MB of PSRAM is required: both models are copied into PSRAM and the stream arena is about 2 MB.
- Image size with two vi-en models and the English lexicon only: 6.35 MB on the ESP32-P4 (2.03 MB free in the 8 MB app partition) and 6.24 MB on the ESP32-S3 (2.15 MB free). `build.sh` also embeds the Chinese and Japanese blobs (about 0.85 MB more).
- Every underrun so far was on the same sentence, "Hello! I am a text-to-speech voice ...": a very short first sentence followed by a long one.
- Pick the model by sound versus headroom: M sounds best; S starts speaking sooner and leaves more CPU for the application.

## ESP32-S3: wrong dot products with `loopnez`

The cause of the ESP32-S3 output differences described below (bursts or a changed phoneme duration, from v0.4.0 on, still present with the two-core fix of v0.7.0) is the S3 SIMD dot-product kernel: its inner loop was the Xtensa zero-overhead loop (`loopnez`) around the 128-bit loads (`ee.vld.128.ip`) and the multiply-accumulate, and that loop now and then returned a wrong sum. In one firmware build, same session, es-en sentences dumped on two cores and compared with the ESP32-P4: kernels with `loopnez` 11 of 112 differed, the same instructions in an ordinary branch loop 0 of 32, a plain C dot product 0 of 48. It was not state carried over between sentences (input ids and durations hashed identical in good and bad runs; junk written over the arena, scratch and stage before every chunk changed nothing), not a PSRAM read error (both cores checksumming 2.5 MB of PSRAM for minutes: 0 errors in 19 GB), and not a race in the runtime (ThreadSanitizer on a PC, memory barriers on the chip). ECC on the PSRAM did not help. A standalone ESP-IDF program reproduces it without vtts; the issue has been reported to Espressif.

The S3 kernels now use branch loops (two 16-byte blocks per iteration). With them the output staging of v0.7.0 is no longer needed and was removed: over id-en, hi-en and es-en (8 sentences each, both models, three times with two cores and once with one core) 144 of 144 two-core and 48 of 48 one-core dumps were identical to the ESP32-P4, with the staging and again without it. Speed (`bench`, two cores, mean of four sentences):

| Pair | M | S |
|---|---:|---:|
| vi-en (`nu-10`, `nam-1`) | 0.57 | 0.32 |
| ko-en (`nu-ko`) | 0.57 | 0.32 |
| zh-en (`nu-zh`) | 0.57 | 0.32 |
| ja-en (`nu-ja`) | 0.55 | 0.31 |
| pt-en (`nu-pt`) | 0.57 | 0.32 |
| id-en (`nu-id`) | 0.56 | 0.32 |
| hi-en (`nu-hi`) | 0.58 | 0.32 |
| es-en (`nu-es`) | 0.58 | 0.32 |
| en (`nu-en`) | 0.57 | 0.32 |

That is about 12% slower than the `loopnez` kernels of v0.6.0 (M 0.50, S 0.29) and much faster than the staged two-core mode of v0.7.0–v0.9.0 (M 0.68–0.71, S 0.41–0.43). The fast scratch (40 KB of internal RAM) stays; the ESP32-P4 is not affected (other instruction set, unchanged).

## ESP32-S3 two-core fix

(Superseded: see [above](#esp32-s3-wrong-dot-products-with-loopnez) for the cause and the current firmware.) Up to v0.6.0 the ESP32-S3 output with two cores (the default) was not deterministic: single values of the int8 layers came out wrong now and then (about one in 10^6), heard as short bursts that changed from run to run, mostly with M (the sections below describe it per pair). It is not a race in the runtime: it stays with interrupts masked, with the cores spinning instead of blocking on semaphores, with a larger worker stack, and with the weights copied before the SIMD loads; it rises with more PSRAM traffic (about 3x with 32-byte cache lines, 5x with PSRAM at 40 MHz) and never happens on one core or on the ESP32-P4. The firmware command `memtest` reproduces it without a model: both cores run an int8 layer with weights over 1.8 MB of PSRAM and store the outputs to PSRAM.

The S3 build now keeps the two-core work away from PSRAM stores: the int8 layers write their outputs to 32 KB of internal RAM and one core copies them to the arena (`vtts_set_out_stage`), their int8 activations sit in 40 KB of internal RAM (fast scratch), and the lighter passes (LayerNorm, quantization, depthwise conv, iSTFT) run on one core. The audio is unchanged (bit for bit on the PC). Measured with `nu-10`: 22 of 23 two-core dumps were bit-identical to `cores 1` (before: nearly every M sentence had bursts), and all eight website sentences dumped with two cores match `vtts_say` (correlation ≥ 0.9998, S and M). The cost is speed, about 1.4x the v0.6.0 time:

| Pair | M before → now | S before → now |
|---|---:|---:|
| vi-en (`nu-10`, `nam-1`) | 0.51 → 0.70 | 0.30 → 0.42 |
| ko-en (`nu-ko`) | 0.49 → 0.70 | 0.29 → 0.41 |
| zh-en (`nu-zh`) | 0.51 → 0.69 | 0.30 → 0.41 |
| ja-en (`nu-ja`) | 0.50 → 0.69 | 0.29 → 0.41 |

RTF from `bench` (mean of the four sentences). With `cores 1` the S3 gives M 0.84 and S 0.49. Internal RAM used on top of v0.6.0: 72 KB on the ESP32-S3, none on the ESP32-P4, whose output and speed are unchanged. Sections below describe the firmware at each release.

## Korean + English (v0.5.0)

The same method with the `nu-ko` models, firmware from the v0.5.0 tree with `lang ko`, and eight Korean, English and mixed sentences (the website samples) for `dump` and playback; `bench` uses four Korean sentences.

| Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---:|---:|---:|---:|---:|---:|
| ESP32-P4 | S (lite) | 0.17–0.18 | 0.17–0.19 | 0.06–0.10 s | 0.07–0.10 s (median 0.09) | 17–19% / 12–13% | 0 |
| ESP32-P4 | M (quality) | 0.25–0.26 | 0.25–0.29 | 0.11–0.19 s | 0.16–0.27 s (median 0.23) | 25–28% / 18–21% | 1 in 8 sentences |
| ESP32-S3 | S (lite) | 0.29–0.30 | 0.29–0.32 | 0.10–0.17 s | 0.18–0.26 s (median 0.23) | 28–31% / 18–20% | 1 in 8 sentences |
| ESP32-S3 | M (quality) | 0.48–0.49 | 0.49–0.53 | 0.19–0.32 s | 0.27–0.47 s (median 0.40) | 42–50% / 29–36% | 0 |

- Both underruns were on "Hello! I am a text-to-speech voice ...", the same short-then-long sentence as with vi-en.
- Image size with the two ko-en models and the English lexicon (no Chinese or Japanese blob): 6.40 MB on the ESP32-P4 (1.98 MB free in the 8 MB app partition) and 6.29 MB on the ESP32-S3 (2.10 MB free). ko-en needs no blob of its own; the Korean tables are compiled in.
- ESP32-P4 PCM against `vtts_say` on a PC: SNR 39–60 dB (correlation ≥ 0.9999) for the single-sentence samples, S and M. In the two-sentence samples the firmware paused about 150 ms longer between the sentences than `vtts_say` did then; `vtts_say` now joins sentences with the same 150 ms pause as the firmware.

### Chip output against the PC runtime

ESP32-P4 PCM (`dump`) against `vtts_say` on a PC for the single-sentence samples: SNR 33–72 dB (correlation ≥ 0.999), S and M alike. On the ESP32-S3 the S model matches the same way, but M with two cores (the default) is **not deterministic**: the same sentence dumped three times gives SNR 26–37 dB against the PC, and some sentences contain short bursts several frames long (up to 0.6–0.98 full scale where the PC output is near silence or much quieter). With `cores 1` the same sentences give 45–67 dB. This points to a race in the two-core path that M exercises on the S3; fixed after v0.6.0, see [ESP32-S3 two-core fix](#esp32-s3-two-core-fix); the website samples come from the ESP32-P4.

The v0.5.0 ko-en models reproduce it, and on them **S is affected too**. Three Korean and mixed sentences dumped three times with two cores, and once with `cores 1`, compared with `vtts_say`:

| Model | Two cores (3 runs) | `cores 1` |
|---|---|---|
| M | 8 of 9 dumps differ from `cores 1`: 10.8–33.8 dB, and the same sentence differs from run to run | 41–59 dB, identical to the ESP32-P4 output |
| S | 3 of 9 dumps differ from `cores 1`: −1.9 dB (one token's duration changed, so the rest of the sentence is shifted) and 20–35 dB; the other 6 are identical | 44–60 dB, identical to the ESP32-P4 output |

The `measure` run shows the same: on the S3, S had one sentence with a 0.5 s window at 3 dB (a burst) and M one sentence shifted after a changed duration, while the ESP32-P4 matched the PC on every sentence. `cores 1` avoids it on the S3 at the cost of speed.

## Chinese + English (v0.5.0)

The zh-en models (v0.5.0) have the same architecture as the vi-en ones with a larger token table (171 instead of 107 tokens: S 0.83M, M 1.84M parameters), and run at the same speed. Same method with `lang zh`: `bench` uses four Mandarin sentences, `dump` and playback the eight website sentences (Mandarin, Mandarin with English terms, English).

| Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---:|---:|---:|---:|---:|---:|
| ESP32-P4 | S (lite) | 0.17–0.20 | 0.17–0.19 | 0.06–0.11 s | 0.07–0.11 s (median 0.10) | 17–19% / 12–13% | 0 in 8 |
| ESP32-P4 | M (quality) | 0.26–0.27 | 0.25–0.29 | 0.11–0.21 s | 0.16–0.29 s (median 0.26) | 25–29% / 19–21% | 1 in 8 |
| ESP32-S3 | S (lite) | 0.28–0.32 | 0.29–0.32 | 0.10–0.17 s | 0.17–0.27 s (median 0.24) | 29–31% / 18–20% | 1 in 8 |
| ESP32-S3 | M (quality) | 0.50–0.51 | 0.49–0.53 | 0.19–0.34 s | 0.27–0.48 s (median 0.44) | 43–49% / 30–35% | 1 in 8 |

- Every underrun was again "Hello! I am a text-to-speech voice ...", a very short first sentence followed by a long one.
- Image with the two zh-en models, the English lexicon and the 116 KB ZLEX blob: 6.54 MB on the ESP32-P4 (1.85 MB free in the 8 MB app partition) and 6.42 MB on the ESP32-S3 (1.96 MB free).
- **ESP32-P4:** the dumps of the single-sentence samples match `vtts_say` on a PC (SNR 28–66 dB, correlation ≥ 0.999) for S and M, and the P4 and the S3 with one core give identical PCM. The three samples with two sentences match `vtts_say` up to the first sentence break and are shifted after it, identically on both chips (same total length: the firmware and the PC tool place the pause between sentences differently); they transcribe as cleanly as the others. All 16 published clips, decoded from MP3 and transcribed with Whisper large-v3: CER 0.003 on the Mandarin and mixed clips, 0.009 on the English ones; the worst clip is 0.036 (S, 零下 heard as 雲下), none is broken.
- **ESP32-S3 with two cores** (`cores 2`, the default), three dumps each of three sentences: M is not deterministic, as with vi-en (SNR −5 to 36 dB against the PC, bursts up to 0.99 full scale where the PC output is near silence, in 6 of 9 dumps). With zh-en **S is affected too**, more mildly: 4 of 9 dumps differ (SNR 11–18 dB, peaks up to 0.15 where the PC output is quiet), while the vi-en S was clean. With `cores 1` both models match the PC exactly (M 28–39 dB, S 37–66 dB, the same values as the P4). Fixed after v0.6.0 ([ESP32-S3 two-core fix](#esp32-s3-two-core-fix)); the website samples come from the ESP32-P4.

## Japanese + English (v0.6.0)

The ja-en models (v0.6.0) have the same architecture with a token table of 144 (S 0.83M, M 1.84M parameters) and run at the same speed as the other pairs. Same method with `lang ja`: `bench` uses four Japanese sentences, `dump` and playback the eight website sentences (Japanese, Japanese with English words, English).

| Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---:|---:|---:|---:|---:|---:|
| ESP32-P4 | S (lite) | 0.17–0.18 | 0.17–0.19 | 0.06–0.10 s | 0.07–0.10 s (median 0.09) | 17–19% / 12–13% | 0 in 8 |
| ESP32-P4 | M (quality) | 0.25–0.26 | 0.25–0.29 | 0.11–0.18 s | 0.18–0.26 s (median 0.24) | 25–28% / 18–21% | 1 in 8 |
| ESP32-S3 | S (lite) | 0.28–0.30 | 0.29–0.32 | 0.10–0.16 s | 0.18–0.25 s (median 0.24) | 28–31% / 18–21% | 1 in 8 |
| ESP32-S3 | M (quality) | 0.50 | 0.50–0.54 | 0.20–0.30 s | 0.31–0.45 s (median 0.41) | 42–50% / 30–36% | 0 in 8 |

- Both underruns were "Hello! I am a text-to-speech voice ...", a very short first sentence followed by a long one.
- Image with the two ja-en models, the English lexicon and the 721 KB JLEX blob: 6.90 MB on the ESP32-P4 (1.49 MB free in the 8 MB app partition) and 6.78 MB on the ESP32-S3 (1.60 MB free).
- **ESP32-P4:** the dumps of the single-sentence samples match `vtts_say` on a PC (SNR 37–56 dB, correlation ≥ 0.9999) for S and M; the samples with two sentences differ only in the pause the firmware places between sentences, as with zh-en. All 16 published clips, decoded from MP3 and transcribed with Whisper large-v3: CER 0.001 on the kana and kanji of the Japanese and mixed clips (one clip: アラーム heard as カラーム); the Latin parts lose a little (S: "ESP32" heard as "EST3", "Zoom" as ジュン; M: "Hello" as "Holol"). None is broken.
- **ESP32-S3 with two cores** (`cores 2`, the default), three dumps each of three sentences: M is not deterministic, as with the other pairs: 6 of 9 dumps differ from the ESP32-P4 (SNR 3–40 dB, differences up to 0.48 full scale; one dump is 0.08 s shorter, a token duration changed); the short question was identical all three times. S matched the ESP32-P4 bit for bit in all 9 dumps (unlike ko-en and zh-en S). With `cores 1` both models give the ESP32-P4 output exactly. Fixed after v0.6.0 ([ESP32-S3 two-core fix](#esp32-s3-two-core-fix)); the website samples come from the ESP32-P4.

## Portuguese (Brazil) + English (v0.7.0)

The pt-en models (v0.7.0) have the same architecture with a token table of 150 (S 0.83M, M 1.84M parameters). Measured with the current firmware (ESP32-S3 [two-core fix](#esp32-s3-two-core-fix) included) and `lang pt`: `bench` uses four Portuguese sentences, `dump` and playback the eight website sentences (Portuguese, Portuguese with English words, English).

| Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---:|---:|---:|---:|---:|---:|
| ESP32-P4 | S (lite) | 0.18–0.21 (mean 0.19) | 0.18–0.20 | 0.06–0.11 s | 0.06–0.12 s (median 0.09) | 18–21% / 13–14% | 0 in 8 |
| ESP32-P4 | M (quality) | 0.27–0.29 (mean 0.28) | 0.27–0.31 | 0.10–0.21 s | 0.13–0.29 s (median 0.24) | 26–30% / 20–22% | 2 in 8 |
| ESP32-S3 | S (lite) | 0.41–0.45 (mean 0.42) | 0.42–0.45 | 0.12–0.28 s | 0.21–0.39 s (median 0.32) | 39–42% / 9–10% | 1 in 8 |
| ESP32-S3 | M (quality) | 0.67–0.71 (mean 0.69) | 0.68–0.75 | 0.21–0.55 s | 0.28–0.73 s (median 0.58) | 57–64% / 17–19% | 2 in 8 |

- The ESP32-P4 RTF is about 0.01–0.02 above the ja-en and ko-en models. The Portuguese `bench` sentences are short (2.0–4.6 s of audio, the shortest 0.21 for S and 0.29 for M), and the fixed cost per sentence weighs more; the longest bench sentence gives 0.177 (S) and 0.265 (M), the same as the other pairs.
- Every underrun was on a text that starts with a one-word sentence followed by a longer one ("Olá! Eu sou ...", and with M "Hello! This text-to-speech voice ...", the English sample of the first run, later replaced by the sentence without "Hello!"), as with the other pairs.
- Image with the two pt-en models and the English lexicon (no blob of its own; the Portuguese front-end is compiled in only for a pt-en model): 6.22 MB on the ESP32-P4 (2.17 MB free in the 8 MB app partition) and 6.10 MB on the ESP32-S3 (2.28 MB free).
- **ESP32-P4:** the dumps match `vtts_say` on a PC (correlation ≥ 0.9993, SNR 28–57 dB) for all 16 clips. All 16 published clips, decoded from MP3 and transcribed with Whisper large-v3: CER 0.014 (M) and 0.009 (S) on average over the six Portuguese and mixed clips (the errors: "ESP32", read with Portuguese letter names, heard as "SP32"; "à Netflix" as "a Netflix"; "às 6:30" written "6h30"); the English clips score 0–0.09, the only error being "ESP32" again (spelled the Portuguese way, heard as "SPP-S2"). None is broken.
- **ESP32-S3 with two cores:** all 16 dumps of the measurement run are identical to the ESP32-P4 dumps of the same text (SNR ≥ 95 dB, the int16 rounding), so the two-core fix holds for pt-en too.

## `nu-10` M update (v0.9.1)

The updated `nu-10` M (longer joint distillation stage, same architecture and size) with the v0.4.0 `nu-10` S, firmware of v0.9.1 with the [ESP32-S3 fix](#esp32-s3-wrong-dot-products-with-loopnez) (vi and en front-ends only), `lang auto`, two cores, same method as the v0.4.0 measurement: `bench` (four Vietnamese sentences), then `dump` and playback of the eight website sentences.

| Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---:|---:|---:|---:|---:|---:|
| ESP32-P4 | S (lite, v0.4.0) | 0.18–0.19 (mean 0.18) | 0.17–0.19 | 0.06–0.14 s | 0.07–0.14 s (median 0.11) | 17–20% / 13–14% | 0 in 8 |
| ESP32-P4 | M (quality, v0.9.1) | 0.26–0.28 (mean 0.27) | 0.25–0.30 | 0.11–0.27 s | 0.19–0.35 s (median 0.28) | 25–28% / 19–21% | 0 in 8 |
| ESP32-S3 | S (lite, v0.4.0) | 0.31–0.33 (mean 0.32) | 0.31–0.34 | 0.11–0.23 s | 0.20–0.33 s (median 0.27) | 30–32% / 21% | 0 in 8 |
| ESP32-S3 | M (quality, v0.9.1) | 0.54–0.57 (mean 0.55) | 0.55–0.60 | 0.20–0.47 s | 0.35–0.62 s (median 0.49) | 50–53% / 36–39% | 0 in 8 |

- Speed is that of the v0.4.0 M within 0.01–0.02 RTF, as expected for the same architecture.
- Images with the two models and the English lexicon: 6.12 MB on the ESP32-P4 (2.27 MB free in the 8 MB app partition), 6.01 MB on the ESP32-S3 (2.38 MB free).
- **ESP32-P4:** the eight new `nu-10` Quality clips of the website are the ESP32-P4's dumps of this model, 64 kbps MP3, transcribed again (PhoWhisper-large for Vietnamese, Whisper large-v3 for mixed and English): CER 0 for 7 of 8; the Vietnamese intro scores 0.07 because PhoWhisper writes "chip ESP32" as "chiếc est d ba hai" (the v0.4.0 clip: "chiếc est pê ba hai", 0.06). None is broken. The `nu-10` Lite clips are unchanged (same S model).
- **ESP32-S3 against the ESP32-P4:** all 16 ESP32-S3 dumps (two cores) have the same length as the ESP32-P4's and differ by at most 1 LSB (correlation 1.0000); no burst, no changed duration. The ESP32-P4 dumps with this firmware are bit-identical to those made before the S3 fix was merged.

## English (v0.9.0)

The English-only models `nu-en` (v0.9.0) use the vi-en architecture and token set (S 0.82M, M 1.83M parameters). The files record the text mode `en` (dim `text_mode`), and the firmware starts them in English (`model S: ..., token set vi-en (header), lang en`); no optional language is compiled in (`vtts: optional languages compiled in: none`). `bench` uses the four fixed English sentences of the `en` mode, `dump` and playback the eight website sentences (an introduction, smart-home commands, numbers, a date, a time, a question and a longer news-like sentence).

| Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---:|---:|---:|---:|---:|---:|
| ESP32-P4 | S (lite) | 0.18–0.21 (mean 0.19) | 0.18–0.20 | 0.06–0.14 s | 0.07–0.14 s (median 0.10) | 18–20% / 13–14% | 0 in 8 |
| ESP32-P4 | M (quality) | 0.27–0.29 (mean 0.28) | 0.27–0.31 | 0.11–0.27 s | 0.17–0.35 s (median 0.27) | 26–30% / 20–22% | 1 in 8 |
| ESP32-S3 | S (lite) | 0.41–0.46 (mean 0.43) | — | — | — | — | — |
| ESP32-S3 | M (quality) | 0.69–0.73 (mean 0.71) | — | — | — | — | — |

- Speed is that of the vi-en voices within about 0.01–0.02 RTF.
- The one underrun (M) was on the intro, which starts with the one-word sentence "Hello!" followed by a longer one, as with the other pairs.
- On the ESP32-S3 only `bench` was run for this release.
- Images with the two models and the English lexicon: 6.12 MB on the ESP32-P4 (2.27 MB free in the 8 MB app partition) and 6.01 MB on the ESP32-S3 (2.38 MB free), about 80–90 KB smaller than the v0.8.0 pairs because no optional front-end is compiled in.
- **ESP32-P4:** The ESP32-P4 output matches `vtts_say` on a PC (same length for all 16 clips, correlation ≥ 0.996, SNR 21–44 dB). All 16 published clips, decoded from MP3 and transcribed with Whisper large-v3: CER 0 for 12 of them; the other four are the intro ("Hello!" not transcribed, and "ESP32" heard as "ESP3 to" with M; CER 0.05–0.06) and the date sentence ("9:30" written "9.30", CER 0.16 for both models). None is broken.
- **ESP32-S3 with two cores:** On the ESP32-S3 only `bench` was run for this release (two cores, the default); its dumps were not compared with the ESP32-P4.

## Indonesian + English, Hindi + English and Spanish + English (v0.8.0)

The id-en, hi-en and es-en models (v0.8.0) have the same architecture with token tables of 141, 157 and 138 (S 0.83M, M 1.84M parameters). One firmware per pair, with only that pair's front-end compiled in (`vtts: optional languages compiled in: id` / `hi` / `es`), measured with `lang id` / `lang hi` / `lang es`: `bench` uses four sentences of the main language, `dump` and playback the eight website sentences (main language, main language with English words, English).

| Pair | Chip | Model | RTF (`bench`) | RTF (`dump`, 8 sentences) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---|---|---:|---:|---:|---:|---:|---:|
| id-en | ESP32-P4 | S (lite) | 0.18–0.20 (mean 0.18) | 0.17–0.20 | 0.06–0.11 s | 0.07–0.12 s (median 0.09) | 18–20% / 13–14% | 0 in 8 |
| id-en | ESP32-P4 | M (quality) | 0.26–0.28 (mean 0.27) | 0.26–0.30 | 0.10–0.21 s | 0.17–0.28 s (median 0.24) | 25–29% / 19–22% | 1 in 8 |
| id-en | ESP32-S3 | S (lite) | 0.40–0.44 (mean 0.42) | 0.41–0.45 | 0.12–0.28 s | 0.23–0.39 s (median 0.32) | 39–42% / 9–10% | 2 in 8 |
| id-en | ESP32-S3 | M (quality) | 0.67–0.70 (mean 0.68) | 0.66–0.75 | 0.23–0.55 s | 0.38–0.72 s (median 0.57) | 58–64% / 17–20% | 2 in 8 |
| hi-en | ESP32-P4 | S (lite) | 0.18–0.20 (mean 0.19) | 0.17–0.20 | 0.06–0.12 s | 0.07–0.12 s (median 0.09) | 18–20% / 13–14% | 0 in 8 |
| hi-en | ESP32-P4 | M (quality) | 0.27–0.28 (mean 0.27) | 0.26–0.30 | 0.11–0.23 s | 0.17–0.30 s (median 0.23) | 25–30% / 19–22% | 1 in 8 |
| hi-en | ESP32-S3 | S (lite) | 0.40–0.45 (mean 0.42) | 0.41–0.45 | 0.14–0.30 s | 0.23–0.41 s (median 0.30) | 39–42% / 9–10% | 2 in 8 |
| hi-en | ESP32-S3 | M (quality) | 0.68–0.70 (mean 0.69) | 0.67–0.74 | 0.27–0.60 s | 0.39–0.78 s (median 0.55) | 57–64% / 17–20% | 1 in 8 |
| es-en | ESP32-P4 | S (lite) | 0.17–0.21 (mean 0.19) | 0.18–0.20 | 0.06–0.11 s | 0.06–0.11 s (median 0.09) | 18–20% / 13–14% | 0 in 8 |
| es-en | ESP32-P4 | M (quality) | 0.26–0.29 (mean 0.28) | 0.26–0.31 | 0.10–0.21 s | 0.15–0.28 s (median 0.25) | 26–30% / 19–22% | 2 in 8 |
| es-en | ESP32-S3 | S (lite) | 0.41–0.46 (mean 0.42) | 0.41–0.46 | 0.12–0.27 s | 0.20–0.39 s (median 0.32) | 39–43% / 9–10% | 2 in 8 |
| es-en | ESP32-S3 | M (quality) | 0.68–0.73 (mean 0.70) | 0.68–0.74 | 0.22–0.54 s | 0.32–0.71 s (median 0.58) | 58–64% / 17–19% | 2 in 8 |

- Speed is the same as the other pairs within 0.01 RTF; the larger Hindi token table costs nothing measurable.
- Every underrun was on a text that starts with a one-word sentence followed by a longer one ("Halo! Saya adalah ...", "नमस्ते! मैं ...", "¡Hola! Soy ...", "Hello! I am a text-to-speech voice ..."), as with the other pairs.
- Images with the two models of the pair and the English lexicon (no blob of their own; the Indonesian and Spanish rules and the Hindi tables are compiled in): id-en 6.21 MB on the ESP32-P4 (2.17 MB free in the 8 MB app partition) and 6.10 MB on the ESP32-S3 (2.29 MB free); hi-en 6.20 MB on the ESP32-P4 (2.19 MB free) and 6.09 MB on the ESP32-S3 (2.30 MB free); es-en 6.21 MB on the ESP32-P4 (2.18 MB free) and 6.10 MB on the ESP32-S3 (2.29 MB free). Devanagari needs no blob: the Hindi module with its tables adds about 25 KB.
- **ESP32-P4:** the dumps match `vtts_say` on a PC for all 48 clips (id-en correlation ≥ 0.9997, SNR 32–78 dB; hi-en ≥ 0.9995, SNR 30–42 dB; es-en ≥ 0.998, SNR 24–67 dB). All 48 published clips, decoded from MP3 and transcribed with Whisper large-v3: id-en CER 0 for 15 of 16 (M intro: "ESP32" heard as "ISP32"); hi-en Devanagari CER 0.11 (M) and 0.12 (S) on average over the six Hindi and mixed clips (first consonants and Whisper's spelling, see the [hi-en report](hi-student-eval.md#on-the-chip)), English clips 0–0.08; es-en CER 0 for 12 of 16, the others 0.010–0.021 ("ESP32" heard as "SP32"). None is broken.
- **ESP32-S3 with two cores: not always deterministic again.** In the measurement run 15 of the 16 id-en dumps were identical to the ESP32-P4 (the 16th, S news, differs for 0.25 s, up to 0.15 full scale) but only 10 of the 16 hi-en dumps (S and M, three with a different length: a token duration changed) and 12 of the 16 es-en dumps (three with a different length). A second hi-en run on the ESP32-S3, four sentences three times each with `cores 2` and once with `cores 1`: 7 of the 24 two-core dumps differ from the ESP32-P4 (3 with another length, up to 0.45 full scale), every one-core dump is identical. So the [two-core fix](#esp32-s3-two-core-fix) lowers the rate of the PSRAM errors but does not remove them; `cores 1` gives exact output, at the cost of speed. The website samples come from the ESP32-P4.

## Where the time goes

`prof` on the ESP32-S3 with M, share of synthesis time: vocoder MLP 37% (pw1 15%, pw2 12%, GELU + quantization 7%, residual 3%), iSTFT 15%, acoustic model 15%, depthwise conv + LayerNorm 10%, head 7%, vocoder input conv 6%, tokens 6%, durations 3%.

## How the runtime got here

Measured with the Vietnamese prototype models (v0.1–v0.3), whose files did not change in that period; all gains come from the runtime. Each step is bit-exact on a PC built with `-ffp-contract=off` (with the compiler's default FMA contraction a few int8 roundings can differ; correlation ≥ 0.99999).

| Step | P4 S | P4 M | S3 S | S3 M |
|---|---:|---:|---:|---:|
| First int8 runtime | 0.41–0.45 | 0.79–0.94 | — | — |
| GELU lookup table, multi-frame int8 kernels, half-size real FFT, two cores | 0.21–0.24 | 0.38–0.40 | 0.42–0.47 | 0.86–0.96 |
| Inline rounding, twiddle table, time-major head | 0.20–0.23 | 0.37–0.39 | 0.34–0.38 | 0.72–0.83 |
| Exact streaming with per-layer state | 0.18–0.19 | 0.30 | 0.31–0.32 | 0.55 |
| Fused dw conv + LayerNorm + quantization, 64-frame blocks, cached iSTFT window, two-core overlap-add | 0.166 | 0.27 | 0.28 | 0.51 |
| Register-tiled fp32 conv (token and duration blocks), lighter int8 epilogue | **0.15** | **0.24** | **0.26** | **0.49** |

Tried and not kept:
- **Fast scratch in internal SRAM** (`vtts_set_fast_scratch`): about 2% faster on the P4 with 96 KB. Available in the API, off in the firmware (`FAST_SCRATCH_MAX 0`) so SRAM stays free for DMA.
- **Software-pipelined S3 kernel** (two register pairs): slower in the kernel benchmark (773 → 690 MMAC/s at 160, 1048 → 846 at 480). The plain load + MAC loop already reaches about 4.4 MAC per cycle.
- **Fused `ee.vmulas.s8.accx.ld.ip` kernel on the S3** (2 instructions per 16 bytes instead of 3): rewritten without any load past the last block, it is correct in every case of the `fusetest` matrix (SRAM/PSRAM × one/two cores × interrupts on/off: 0 wrong, 0 unstable), so earlier two-core failures came from an older kernel, not from the hardware. It is 8–12% faster per kernel but about 1% end to end, so the plain loop stays the default; `vtts_s3_kernel = 1` selects the fused one.
- **`-O3`**, **32- or 16-frame steps** and **hot code in IRAM** on the S3: no gain, or about 2% for IRAM at the cost of internal RAM.
- **Load-time int8 for the token blocks** (`vtts_prepare`): about 2× faster for that stage, but PCM correlation with fp32 dropped to 0.995, so these blocks stay fp32 and use the register-tiled float conv instead.
- **Four channels at once in the depthwise conv**, **frame loop of the S3 kernel in assembly**: bit-exact but no measurable gain.

On the S3, about 40% of the int8 layers' time is outside the dot kernel, and float code runs several times slower than its operation count suggests. Neither instruction fetch (IRAM), working-set size (step 16–64) nor the kernel's instruction count explains it alone; the remaining time is spread over memory accesses through the 64 KB data cache. Further large gains on the S3 would need a smaller vocoder (retraining) rather than runtime changes.

Plan and research: [2026-11-17-runtime-optimization.md](../design/plans/2026-11-17-runtime-optimization.md), [runtime-optimization-research.md](runtime-optimization-research.md).

## How to measure

- `bench`: synthesizes 4 fixed sentences without playback and prints the RTF per sentence.
- `prof`: time per model stage.
- `selftest`: SIMD kernels against plain C, including both cores at once; on the S3 `fusetest` also checks the fused kernel.
- During playback the firmware prints `first chunk`, `playback started`, the number of underruns and per-core CPU load after each sentence.
- The RTF on the `SAID` line (with playback) includes time spent waiting for the playback buffer, so it is higher than the true RTF. Take the true RTF from `bench` or `dump`.
