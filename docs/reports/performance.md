# On-chip performance

Measurements of the int8 runtime on the ESP32-P4 and ESP32-S3 with the v0.4.0 Vietnamese + English models, lite S (0.82M parameters, 1.2 MB) and quality M (1.83M parameters, 2.6 MB), and the v0.5.0 Korean + English models (S 0.83M, M 1.84M; the same architecture with 46 more input tokens). Both vi-en voices (`nam-1`, `nu-10`) give the same numbers within 0.005 RTF; the ko-en voice `nu-ko` is within 0.02 of them, M on the ESP32-S3 slightly faster ([Korean + English](#korean--english-v050)). Both models run on both chips. The README keeps only the summary table.

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
- ESP32-P4 PCM against `vtts_say` on a PC: SNR 39–60 dB (correlation ≥ 0.9999) for the single-sentence samples, S and M. In the two-sentence samples the firmware pauses about 150 ms longer between the sentences than `vtts_say`; aligned, the sentences match the same way.

### Chip output against the PC runtime

ESP32-P4 PCM (`dump`) against `vtts_say` on a PC for the single-sentence samples: SNR 33–72 dB (correlation ≥ 0.999), S and M alike. On the ESP32-S3 the S model matches the same way, but M with two cores (the default) is **not deterministic**: the same sentence dumped three times gives SNR 26–37 dB against the PC, and some sentences contain short bursts several frames long (up to 0.6–0.98 full scale where the PC output is near silence or much quieter). With `cores 1` the same sentences give 45–67 dB. This points to a race in the two-core path that M exercises on the S3; it is not fixed yet, and the website samples come from the ESP32-P4.

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
- **ESP32-S3 with two cores** (`cores 2`, the default), three dumps each of three sentences: M is not deterministic, as with vi-en (SNR −5 to 36 dB against the PC, bursts up to 0.99 full scale where the PC output is near silence, in 6 of 9 dumps). With zh-en **S is affected too**, more mildly: 4 of 9 dumps differ (SNR 11–18 dB, peaks up to 0.15 where the PC output is quiet), while the vi-en S was clean. With `cores 1` both models match the PC exactly (M 28–39 dB, S 37–66 dB, the same values as the P4). The race in the two-core path is not fixed yet; the website samples come from the ESP32-P4.

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
