# On-chip performance

Measurements of the int8 runtime (v0.3.1) on the ESP32-P4 and ESP32-S3 with the Vietnamese prototype models: S-vocos v0.1 (lite, 0.77M parameters, 1.1 MB) and M-vocos v0.2 (quality, 1.73M parameters, 2.6 MB). Both models run on both chips. The README keeps only the summary table.

Everything lives in PSRAM: the models, the working arena and the activations. Internal SRAM stays free for the application and for DMA.

## ESP32-P4

Chip rev 1.3, 360 MHz, 32 MB PSRAM. Measured on a Waveshare ESP32-P4-NANO; the ESP32-P4-86-Panel uses the same chip and firmware.

| Model | RTF (`bench`) | First audio chunk | Playback starts | Underruns |
|---|---:|---:|---:|---:|
| S (lite) | 0.166–0.18 | ~0.1 s | ~0.24 s | 0 |
| M (quality) | 0.267–0.27 | 0.27–0.42 s | 0.74–0.90 s | 0 |

## ESP32-S3

EchoEar 2.0 (ESP32-S3-WROOM-1 N16R8): 240 MHz, 8 MB octal PSRAM at 80 MHz, 16 MB flash. The Waveshare ESP32-S3-Touch-LCD-2.8 uses the same chip and firmware.

| Model | RTF (`bench`) | First audio chunk | Playback starts | CPU core 0 / core 1 while speaking | Underruns |
|---|---:|---:|---:|---:|---:|
| S (lite) | 0.26 | 0.13–0.19 s | 0.21–0.27 s | 28–29% / 18–20% | 0 |
| M (quality) | 0.48–0.49 | 0.26–0.29 s | 0.40–0.43 s | 45–50% / 32–36% | 0 |

Playback starts as soon as every later chunk is sure to be ready in time: the firmware learns each model's RTF, simulates the chunk schedule (25% margin) and picks the chunk size that gives the shortest wait. A slower model streams in smaller chunks, which costs a little CPU but lets it start sooner.

- At least 8 MB of PSRAM is required: both models are copied into PSRAM and the stream arena is about 2 MB.
- Audio from the chip matches the C runtime on a PC (correlation ≥ 0.99999).
- Pick the model by sound versus headroom: M sounds best; S starts speaking sooner and leaves more CPU for the application.

## Where the time goes

`prof` on the ESP32-S3 with M, share of synthesis time: vocoder MLP 37% (pw1 15%, pw2 12%, GELU + quantization 7%, residual 3%), iSTFT 15%, acoustic model 15%, depthwise conv + LayerNorm 10%, head 7%, vocoder input conv 6%, tokens 6%, durations 3%.

## How the runtime got here

The models and `.vtts` files have not changed since the first prototype release; all gains come from the runtime. Each step is bit-exact on a PC built with `-ffp-contract=off` (with the compiler's default FMA contraction a few int8 roundings can differ; correlation ≥ 0.99999).

| Step | P4 S | P4 M | S3 S | S3 M |
|---|---:|---:|---:|---:|
| First int8 runtime | 0.41–0.45 | 0.79–0.94 | — | — |
| GELU lookup table, multi-frame int8 kernels, half-size real FFT, two cores | 0.21–0.24 | 0.38–0.40 | 0.42–0.47 | 0.86–0.96 |
| Inline rounding, twiddle table, time-major head | 0.20–0.23 | 0.37–0.39 | 0.34–0.38 | 0.72–0.83 |
| Exact streaming with per-layer state | 0.18–0.19 | 0.30 | 0.31–0.32 | 0.55 |
| Fused dw conv + LayerNorm + quantization, 64-frame blocks, cached iSTFT window, two-core overlap-add | 0.166 | 0.27 | 0.28 | 0.51 |
| Register-tiled fp32 conv (token and duration blocks), lighter int8 epilogue | not yet measured | not yet measured | **0.26** | **0.49** |

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
