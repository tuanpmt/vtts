# Runtime optimization for ESP32-S3 and ESP32-P4 — implementation plan

> Status: closed (2026-11-17). Tasks 1–3 done; Tasks 4–5 tried, kept only what measured better; follow-ups (adaptive prebuffer, tiled fp32 conv, lighter int8 epilogue) done. Remaining S3 time is spread over many stages; an int16 FFT would save about 3% (FFT is ~5% of the time), so further speedups move to a smaller vocoder variant (bilingual plan, Task 15 Step 8). Results: [performance.md](../../reports/performance.md).

**Goal:** lower the RTF of both models on both chips without changing the model files:
- ESP32-S3: M from about 0.92 to ≤ 0.5.
- ESP32-P4: M from about 0.38 to ≤ 0.25.

**Spec:** [runtime-optimization-research.md](../../reports/runtime-optimization-research.md)

## Global constraints

- The `.vtts` file format and the public API in `runtime/include/vtts.h` stay unchanged. New functions may be added.
- **Quality gate after every task:** a regression harness renders the real S and M models in streaming mode (first chunk 12, then 128 frames, as in the firmware) on 6 sentences and compares the PCM with the previous version.
  - Tasks 1, 2, 4 and 5 must be bit-exact; otherwise correlation ≥ 0.999999 with a written reason.
  - Task 3 must reach correlation ≥ 0.9999.
  - `uv run pytest -q tests/export/test_runtime_golden.py` must pass.
- No `-ffast-math`: on-chip audio must keep matching the C runtime on a PC.
- C99, no `malloc` in the runtime.
- After each task, measure `bench` and `prof` on hardware and record the results in `docs/reports/performance.md`.

## Task 1: iSTFT and rounding cleanup (bit-exact) — done

- Replace `nearbyintf`, `lrintf` and `floorf` in hot loops with inline code: rounding with the 1.5·2²³ constant, floor by truncation and correction. Both are identical to the library functions for |x| < 2²².
- Precompute the twiddles `sincos(2πk/N)` once per N with the same `fast_sincos`.
- The head writes time-major output `[t][n_fft + 2]`, so the iSTFT reads each frame contiguously instead of walking columns.
- Result on ESP32-P4-NANO: bit-exact. iSTFT time -25%. RTF S 0.212–0.239 → 0.200–0.227, M 0.379–0.399 → 0.369–0.390.

## Task 2: Time-major fusion and fast scratch memory (bit-exact) — done

- Fuse "depthwise conv → LayerNorm → quantize" into one pass per frame.
- Fuse the pw1 epilogue with GELU and quantization, so the float `h` buffer goes away.
- Split the residual and `col` copy loops across both cores.
- Add `vtts_set_fast_scratch(void *p, size_t n)` so the hot tiles (`col`, int8 `h`, `o`, `head`, `fbuf`, `win`) live in internal SRAM. The firmware passes about 130 KB.
- Result: fusion, 64-frame MLP blocks and a cached window with two-core overlap-add. P4 S 0.182 → 0.166, M 0.303 → 0.269; S3 S 0.31 → 0.28, M 0.55 → 0.505. Fast scratch gave about 2% and is off in the firmware, because real applications keep internal SRAM for DMA.
- Gate ruling: the PC harness compares with `-ffp-contract=off` (bit-exact); clang's default FMA contraction makes a few int8 roundings differ (min corr 0.99999 on M), which only reflects where the compiler fuses multiply-adds.

## Task 3: Exact streaming with per-layer state — done

- Every convolution layer keeps the K−1 input frames it needs from the previous chunk. Each frame is computed exactly once, which removes the halo and the ramp-up overhead.
- **Gate:** streaming must match whole-utterance synthesis, with a dedicated test.

## Task 4: Pipelined ESP32-S3 kernel

- Use two register pairs (load one pair while multiplying the other) and move the frame loop into the assembly.
- Add a `selftest` matrix to find the root cause of the fused `ld.ip` failure: interrupts on/off × SRAM/PSRAM × what the other core is doing.
- **Gate:** the two-core `selftest` shows 0 mismatches, and the output is bit-exact.
- Result: the two-register-pair loop is correct but slower (kernel benchmark 773 → 690 MMAC/s). The fused `ld.ip` form, rewritten with no load past the last block, is correct in the whole `fusetest` matrix (memory × cores × interrupts), so the old failure was in the old kernel. It is 8–12% faster per kernel but about 1% end to end, so the plain loop stays the default (`vtts_s3_kernel = 1` selects the fused one). The S3 kernel is bound by load latency, not by instruction count or PSRAM bandwidth (SRAM and PSRAM give the same speed).

## Task 5: Build

- Add a `VTTS_HOT` macro that places hot functions in IRAM on the S3.
- Try `-O3` and the PSRAM options. Keep only the changes that measure better.
- Result so far: `-O3` gives no gain on the S3. The S3 already uses a 64 KB data cache with 64-byte lines and octal PSRAM at 80 MHz.
