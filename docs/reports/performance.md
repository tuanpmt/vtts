# On-chip performance

Detailed measurements of the int8 runtime on the ESP32-P4 and ESP32-S3, with the Vietnamese prototype models (S-vocos v0.1 lite, M-vocos v0.2 quality). The README keeps only the summary table. Ongoing optimization work: [runtime-optimization-research.md](runtime-optimization-research.md).

## ESP32-P4

Chip rev 1.3, 360 MHz, 32 MB PSRAM. Measured on a Waveshare ESP32-P4-NANO; the ESP32-P4-86-Panel uses the same chip and the same firmware and gives the same numbers.

| Model | RTF (2 cores, PIE SIMD) | Speech starts | Flash | Working RAM |
|---|---:|---:|---:|---:|
| S-vocos | 0.20–0.24 | 0.3–0.5 s | 1.1 MB | ~0.4 MB (streaming) |
| M-vocos v0.2 | 0.34–0.42 | 1.2–1.3 s | 2.6 MB | ~0.6 MB (streaming) |

CPU load while synthesizing and playing at the same time (a 5-sentence weather bulletin, averaged over the whole playback; core 0 includes the console task and the task that feeds audio to the speaker):

| Model | Core 0 | Core 1 | Playback underruns |
|---|---:|---:|---:|
| S-vocos | 21% | 16% | 0 |
| M-vocos v0.2 | 35% | 28% | 0 |

### Runtime optimization (v0.3.0)

The models and `.vtts` files are unchanged and the audio is almost identical to the previous version (correlation 0.9998).

| Model | RTF v0.2.0 | RTF v0.3.0 | Speedup | Speech starts |
|---|---:|---:|---:|---:|
| S-vocos | 0.41–0.45 | 0.20–0.22 | ~2.1× | 0.6–0.9 s → 0.3 s |
| M-vocos v0.2 | 0.79–0.94 | 0.34–0.42 | ~2.3× | 2.4 s → 1.2 s |

Main changes:
- GELU uses a lookup table instead of `tanhf`.
- The int8 kernels process several frames per call, with a pipelined loop built on the PIE instruction `esp.vmulas.s8.xacc.ld.ip`.
- The iSTFT uses a half-size real FFT.
- Depthwise convolution, LayerNorm, activation quantization and the iSTFT are split across both cores.

## ESP32-S3

Waveshare ESP32-S3-Touch-LCD-2.8: ESP32-S3R8, 240 MHz, 8 MB octal PSRAM, 16 MB flash. Same firmware and same two models as on the P4. The int8 kernels use the 128-bit SIMD instruction `ee.vmulas.s8.accx`.

| Model | RTF (2 cores, SIMD) | Speech starts | CPU core 0 / core 1 during playback | Playback underruns |
|---|---:|---:|---:|---:|
| S-vocos | 0.42–0.47 | ~0.8 s | 40% / 29% | 0 |
| M-vocos v0.2 | 0.85–0.99 | ~2.4 s | 75% / 62% | 0 |

- Audio from the S3 matches the C runtime on a PC: correlation 1.000000 for S and 0.999992 for M.
- In v0.3.0 the M model was close to real time on the S3. On the main branch it runs at RTF 0.50 (see below), so both models are usable on the S3; S leaves more CPU for the application.
- At least 8 MB of PSRAM is required: both models are copied into PSRAM and the working area is about 1.9 MB. Boards with 2 MB of PSRAM are not enough.
- The default kernel loads first and then multiply-accumulates. An earlier kernel with the fused instruction `ee.vmulas.s8.accx.ld.ip` gave wrong sums on two cores; a rewrite is correct (see below) but barely faster end to end. The firmware `selftest` runs the kernel on both cores at once, and `fusetest` checks the fused form.

## Runtime optimization (main branch, after v0.3.0)

Plan: [2026-11-17-runtime-optimization.md](../design/plans/2026-11-17-runtime-optimization.md). Same model files. Everything lives in PSRAM (arena, weights, activations); internal SRAM stays free for DMA. Each step is bit-exact on a PC built with `-ffp-contract=off`; with the compiler's default FMA contraction a few int8 roundings can differ (min correlation 0.99999).

| Board | Model | v0.3.0 | Inline rounding, time-major head | Exact streaming | Fusion, 64-frame blocks, iSTFT | 
|---|---|---:|---:|---:|---:|
| ESP32-P4-NANO | S | 0.212–0.239 | 0.200–0.227 | 0.182–0.194 | **0.166** |
| ESP32-P4-NANO | M | 0.379–0.399 | 0.369–0.390 | 0.303–0.304 | **0.269** |
| EchoEar 2.0 (S3) | S | 0.42–0.47 | 0.34–0.38 | 0.305–0.322 | **0.281–0.283** |
| EchoEar 2.0 (S3) | M | 0.86–0.96 | 0.72–0.83 | 0.550 | **0.505–0.510** |

The stream arena grows from 1.47 to 1.96 MB with 64-frame steps (PSRAM).

Tried and not kept:
- **Fast scratch in internal SRAM** (`vtts_set_fast_scratch`): about 2% faster on the P4 with 96 KB. Available in the API, off in the firmware (`FAST_SCRATCH_MAX 0`).
- **Software-pipelined S3 kernel** (two register pairs): slower in the kernel benchmark (773 → 690 MMAC/s at 160, 1048 → 846 at 480). The plain load + MAC loop already reaches about 4.4 MAC per cycle.
- **`-O3`** on the S3: no gain (M 0.508–0.513).
- **Fused `ee.vmulas.s8.accx.ld.ip` kernel on the S3** (2 instructions per 16 bytes instead of 3): rewritten without any load past the last block, it is **correct** in every case of the `fusetest` matrix (SRAM/PSRAM × one/two cores × interrupts on/off: 0 wrong, 0 unstable), so the earlier two-core failures came from the old kernel, not from the hardware. It is 8–12% faster in the kernel benchmark but only about 1% end to end (M 0.505 → 0.501), so the plain loop stays the default; `vtts_s3_kernel = 1` selects the fused one.

## How to measure

- `bench`: synthesizes 4 fixed sentences without playback and prints the RTF per sentence.
- `prof`: time per model stage.
- During playback the firmware prints `first chunk`, `playback started`, the number of underruns and per-core CPU load after each sentence.
- The RTF on the `SAID` line (with playback) includes time spent waiting for the playback buffer, so it is higher than the true RTF. Take the true RTF from `bench` or `dump`.
