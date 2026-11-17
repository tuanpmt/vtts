# On-device TTS performance research: ESP32-S3 and ESP32-P4

> **Status:** research report (2026-11-17); the optimization work it proposes is in progress. Measured numbers for the current runtime are in [performance.md](performance.md).

This report is based on code inspection and on disassembly of the existing firmware builds for the ESP32-S3 and ESP32-P4 (`firmware/esp32/build_s3/vtts_bench.elf` and `build/vtts_bench.elf`), used to check for library calls and code placement. The speedup figures below are estimates from arithmetic and code inspection, not measurements.

## 1. Compute per second of audio, and what the measured RTF implies

The decoder runs at 22050 / 256 = 86.13 frames/s, with n_fft = 4·hop = 1024. The head therefore outputs 1026 channels.

| per frame (MAC) | S (C=112, M=336, 4 blk, a=64) | M (C=160, M=480, 6 blk, a=96) |
|---|---:|---:|
| `decoder.pre` k7: 192·7·C | 150,528 | 215,040 |
| ConvNeXt blocks: (7C + 2·C·M) × blocks | 304,192 | 928,320 |
| head: C·1026 | 114,912 | 164,160 |
| acoustic frame blocks + out: 4·5·a² + 192a | 94,208 | 202,752 |
| **total per frame** | **663,840 (57.2 MMAC/s)** | **1,510,272 (130.1 MMAC/s)** |

Streaming recomputes a halo around every chunk:
- Decoder halo Rd = 3(1+blocks)+4, which is 19 for S and 25 for M.
- Acoustic halo Ra = 8.

At chunk 128 this gives:
- **S: ~72.5 MMAC/s**. The decoder is ×166/128 and the acoustic model ×182/128.
- **M: ~178 MMAC/s**. The decoder is ×178/128 and the acoustic model ×194/128.

The ramp-up chunks (12 → 24 → 48 → 96) are worse. For a 3 s M sentence the pre+blocks work is about **1.9×** what a single pass would need.

**What this means.** On the S3, the delivered throughput is 72.5/0.45 ≈ 160 and 178/0.92 ≈ 195 MMAC/s. The plain two-core kernel can do ~1700 MMAC/s, so **int8 MACs are only about 10–12% of S3 time**. On the P4 the figures are ~330 and ~470 MMAC/s, so MACs are roughly 15–20%. On both chips the time goes to the float glue around the MACs, memory stalls, single-core sections and recomputing the halo.

## 2. Why the S3 is slow (evidence)

1. **Channel-major float buffers in PSRAM are read one column at a time.** The worst case is `istft_frames`→`head_bin`. It reads `head[k*hb + j]` with hb = 16, so each row is exactly one 64 B line. Every frame therefore walks all 1026 lines, about 66 KB, which is the whole cache. That costs ~5.8 MB/s of PSRAM reads, roughly 70–110 ms per second of audio at 50–80 MB/s effective. This explains why `istft` takes 23% on the S3 but much less on the P4, where the 256 KB L2 holds the buffer.
   - The same pattern hits `quant_cols` on `h` ([M][32] floats: 43 KB for S, 61 KB for M), `layernorm_cols`, and the `col` transposes.
   - The S3 data cache (64 KB) is shared by both cores, and flash and PSRAM share one memory bus.
2. **Library calls in hot loops (confirmed in the disassembly).**
   - S3: `quant_cols` calls `lrintf` (about 60 instructions, ~270k calls/s for S and ~560k for M). `istft_frames` makes 2 `floorf` and 3 `nearbyintf` calls per bin pair. The final PCM loop calls `floorf` per sample through `fast_exp`.
   - P4: `lrintf` is already inlined (`fcvt.w.s`), but `floorf` and `nearbyintf` are still library calls in `istft_frames`.
3. **Large single-core loops on PSRAM data** inside `vocos_region`: the `col` copies, the residual `x += o*gm`, the overlap-add (OLA) and `env` accumulation (two buffers of ~138 KB), the `ola/env` divide plus `fast_tanh` for every sample, and the relu/residual in `conv_block`.
4. **All hot code runs from flash.** `lconv_rows`, `quant_cols` and the others sit at 0x4200xxxx, so instruction-cache misses compete with PSRAM data misses on the shared bus.
5. **The S3 dot kernel stalls and has per-call overhead.** It does a load–load–MAC with a load-use stall and makes one call per (row, frame). With ci = 112 there are only 7 blocks per dot, so about 10 cycles of `zero.accx`/`srs`/pointer overhead sits on roughly 30 cycles of work.

## 3. Answers by topic

### Kernels
- **S3, without fused instructions (low risk).** Software-pipeline the plain loads in `vtts_port_s3.c` with two register pairs: `vld q2; vld q3; vmulas q0,q1; vld q0; vld q1; vmulas q2,q3`. Also move the frame loop inside the asm (one call per weight row, results stored with `s32i`). Expect **1.3–1.5×** on the kernel, about 5–10% end-to-end.
- **Root cause of the fused-instruction failure.** These are untested hypotheses, to be separated by a test matrix in `selftest`:
  - (a) The PIE (TIE) coprocessor state is not saved by an interrupt or context switch. Test by bracketing the loop with `portDISABLE_INTERRUPTS`, and check `xtensa_context.S` in IDF 6.1 for saving of coprocessor 3.
  - (b) A load/MAC hazard that only shows when the other core makes cache-miss timing longer. Test fused on one core with a non-PIE memory-heavy loop on the other core; also fused on one core with the plain kernel on the other.
  - (c) The data location. Test with both operands in SRAM against PSRAM.

  If (b) is confirmed, a safe pattern is "fused MAC on one core, float glue on the other" (pipeline parallelism) rather than splitting the same work across both cores.
- **QACC lane-wise accumulation is not worthwhile.** Each 20-bit lane holds ci/16 × 16129, which fits only for ci ≤ 512, and the 16-lane reduction costs more than it saves on short dots.
- **int16 activations: no.** They halve SIMD throughput and double traffic. Use them only if quality requires it.
- **esp-nn** assumes TFLite-style requantization and does not match the per-frame float epilogue. Borrow loop ideas only.

### Float paths
- Replace `lrintf`/`floorf`/`nearbyintf` with inline code: magic-constant rounding `(x + 12582912.f) - 12582912.f`, or truncate and correct.
- Precompute a twiddle table with n_fft/2 entries.
- `env` is deterministic: precompute `1/env` (steady state is a constant; edges handled separately).
- Replace `ola/env` with a 1024-float OLA ring buffer in SRAM that emits `hop` samples per frame.
- Use a lookup table for `tanh`, as GELU already does.
- Fuse "dwconv → LN → quantize" and "pw1 epilogue + bias → GELU → per-frame quantize" into one per-frame pass over a time-major layout. This removes the `y`, `col` and float `h` round-trips.
- A fixed-point depthwise conv or LN is not worth doing. After fusion they are a few percent.
- **esp-dsp FFT** (`dsps_fft2r_fc32` with the S3 `aes3` and P4 assembly variants; Apache-2.0; tables can be static so no malloc): expect 1.5–2× on the FFT itself. That is only about 2–4% overall once the cache problem is fixed, so it has lower priority.

### Memory placement (S3)
- Use a two-tier arena: a new call such as `vtts_set_fast_scratch(p, n)` places the per-block tiles in internal SRAM. For M: `col` 20 KB, `h` 61 KB, `o` 20 KB, int8 tile 15 KB, plus `head` and `fbuf` at HEAD_BLOCK = 8 (33 + 32 KB, which can share space with the MLP tiles), `win` 4 KB, the GELU table 8 KB and the OLA ring 4 KB. That is about 130 KB, within the 217 KB free.
- Large windows (`x`, `y`, `z`) stay in PSRAM but are streamed sequentially.
- Weight traffic is about 2.2 MB/s of audio for S and 5.2 MB/s for M. That costs only 30–65 ms per second of audio, so DMA or streaming weights is not a priority. Octal PSRAM at 80 MHz DTR is 160 MB/s raw, roughly 50–90 MB/s effective.

### Algorithm and model
- **Exact streaming with per-layer state.** Keep K−1 input frames per conv layer (about 27 KB for M) and compute each frame once. This is bit-exact, because quantization is per frame, and it removes both the halo and the ramp-up overhead: **1.3–1.9× on MAC-related work**. It also shrinks the arena enough to sit entirely in SRAM.
- **S3 "lite" preset**: a=96, d=64 (M's front end), v_dim 128, 4 blocks, mult 3, `pre` k3. That is 805k MAC/frame (69 MMAC/s), versus 664k for S and 1.51M for M.
  - It needs a dimension for the `pre` kernel size, since `lconv(&pre,…,7)` is hard-coded.
  - With 16 kHz audio and hop 256 (62.5 fps) everything scales by ×0.726.
  - n_fft = 2·hop would halve the head and FFT cost, but with higher quality risk.
  - Retraining on the RTX 3060 with AI-assisted pipeline work is moderate effort.
- **Quick knob**: the `chunk 256` command already exists. At steady state it cuts M MACs by about 13%.

### Build
- Put hot functions in IRAM on the S3 through a `VTTS_HOT` macro (`lconv_rows`, `vtts_dots_s8s8`, `quant_cols`, `layernorm_cols`, `dwconv_rows`, `istft_frames`, `ifft`, `gelu_range`; about 8–12 KB). Expect 0–10%.
- `CONFIG_SPIRAM_XIP_FROM_PSRAM` is an alternative.
- PSRAM at 120 MHz is experimental and high risk; expect +10–25% on memory-bound parts.
- `-O3`: 0–5%.
- `-ffast-math`: small gain, but it breaks the host-match property (correlation 1.000000), so avoid it.
- The data cache is already at its maximum (64 KB, 64 B lines). Check that it is 8-way.
- CPU clocks are already at their maximum: 240 MHz on the S3, 360 MHz on the P4 rev1.3.

## 4. Prioritised plans

All RTFs below are estimates.

**ESP32-S3** (now: S 0.45, M 0.92)

| # | Change | Effort | Risk | S RTF | M RTF |
|---|---|---|---|---:|---:|
| 1 | iSTFT rework: time-major head output (or HEAD_BLOCK 8 in SRAM), inline floor/round/lrint, twiddle table, OLA ring + `1/env` table, tanh lookup table; try `chunk 256` | 1–2 days | low, bit-near-exact | 0.33–0.36 | 0.72–0.78 |
| 2 | Two-tier arena (hot tiles in SRAM) plus time-major fused LN+quantize and GELU+quantize; parallelise the residual/`col` copies | 2–4 days | low–medium | 0.26–0.30 | 0.55–0.62 |
| 3 | Exact streaming with layer-state caches (no halo); whole arena fits in SRAM | 3–5 days | medium (needs a whole-utterance equivalence test) | 0.19–0.23 | 0.40–0.48 |
| 4 | Software-pipelined plain-load kernel with the frame loop in asm; root-cause the fused failure and adopt it if proven safe | 1–3 days | low (plain) / medium (fused) | 0.17–0.21 | 0.35–0.42 |
| 5 | IRAM hot code, then try XIP from PSRAM and PSRAM at 120 MHz | 0.5–1 day | low / high | 0.16–0.20 | 0.33–0.40 |

If these runtime gains fall short, the fallback is to train the "lite" preset (16 kHz). It would land at about 0.2–0.25 on the S3 even with today's runtime improvements only partly done.

**ESP32-P4** (now: S 0.22, M 0.38)

| # | Change | S RTF | M RTF |
|---|---|---:|---:|
| 1 | Exact streaming without halo | 0.15–0.17 | 0.26–0.30 |
| 2 | iSTFT cleanup: inline `floorf`/`nearbyintf`, twiddle table, OLA ring, `1/env` | 0.13–0.15 | 0.24–0.27 |
| 3 | Fused time-major epilogues; hot tiles in L2MEM (two-tier arena) | 0.11–0.13 | 0.20–0.23 |
| 4 | Parallelise the remaining serial loops; esp-dsp P4 FFT | 0.10–0.12 | 0.19–0.22 |
| 5 | `-O3`; multi-frame asm (one call per row) | 0.10–0.11 | 0.18–0.21 |

## 5. What to measure

- **Cycle counts per profile slot**, using `esp_cpu_get_cycle_count`. Add slots for `quant`, `gelu`, `col/residual`, `ola+final`, and `pre` separately from dw/LN.
- **`prof` with `vtts_par_enable(0)`**, to get the serial fraction.
- **S3 data-cache miss and stall counts** from the IDF `perfmon` (xtensa_perfmon) component, before and after fixes 1 and 2.
- **A microbenchmark of `istft_frames`** with `head` in SRAM against PSRAM. This directly tests the column-walk hypothesis.
- **Fused-kernel test matrix** in `selftest`: interrupts off/on × SRAM/PSRAM × other core idle/plain/fused.
- **Quality gates** for every step: PCM correlation ≥ 0.9999 against the host runtime, and a bit-exact whole-utterance versus streaming comparison for the state-caching change.
- **Bench results** for both short and long sentences, since the ramp-up overhead dominates short ones, plus first-audio latency.
