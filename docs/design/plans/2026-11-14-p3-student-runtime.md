# Plan 3: Distilled student, exporter and C runtime

> **Status:** completed. Historical plan, kept for reference. The selected decoder became the Vocos-style ConvNeXt + iSTFT decoder (`decoder = 2` in the [model format](../../model-format.md)); the released students are S-vocos v0.1 (0.77M parameters) and M-vocos v0.2 (1.73M). Current numbers: [README](../../../README.md) and [performance report](../../reports/performance.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** S and M students distilled from the teacher, running on a hand-written C99 runtime (fp32 and int8) on the host and passing the golden gate; choose the decoder by measured quality versus compute so that it fits the ESP32-P4 real-time budget.

**Architecture:** The student has 3 blocks: duration (token-level conv), acoustic (token-level conv → expansion by duration + relative position within the token → frame-level conv → 192-channel latent), and decoder. The decoder is a configurable family: `hifigan` (upsample 8×8×4 straight to the waveform) and `istft` (less upsampling followed by a small iSTFT, e.g. upsample 8×8 + iSTFT n_fft 16 hop 4). Fixed operator set: Embedding, Conv1d (with dilation), ConvTranspose1d, LeakyReLU, ReLU, channel-wise LayerNorm, Linear, tanh, small iDFT, expansion by duration. The C runtime implements exactly this set and reads a self-describing model file. Distillation: the teacher generates data for every sentence in the text corpus; the targets are the teacher's durations and latent `z` (prior noise fixed to 0 so the targets are deterministic) plus the audio the teacher decoder produces from `z`.

**Tech Stack:** PyTorch (training), C99 + Make (runtime, host tests), numpy (golden).

**Spec:** `docs/design/specs/2026-11-14-vietnamese-tts-p4-design.md` (sections 5.5, 5.6)

## Global Constraints

- The global constraints of Plans 1 and 2 still apply.
- C runtime: C99, no `malloc`; the caller provides an arena, and a function computes the arena size up front; no hard-coded shapes.
- Model file format: magic `VTTS`, version `1`, a tensor table (name, dtype `f32`/`i8`, shape, offset, per-channel scale), dims as key/value pairs. The Python exporter and the C parser both follow one format description in `docs/model-format.md`.
- Golden gate: C fp32 vs PyTorch correlation ≥ 0.9999 with exactly matching durations; int8 vs fp32 correlation > 0.98 and 0.80 < RMS ratio < 1.25; int8 durations off by at most 1 frame per token and at most 1% of the total frame count.
- Compute budget (measured by the exporter's MAC counter): **S ≤ 120 MMAC per second of audio**, **M ≤ 300 MMAC per second of audio**. A decoder over budget is not selected, even if it sounds better.

## Review Focus

1. A sentence with only 1 token, or a duration clamped to 1 frame: no arena overflow, no division by zero.
2. A 40-syllable sentence (the front-end's maximum chunk): the arena is large enough and its size is computed correctly before running.
3. A malformed or truncated model file (wrong magic, different version, offset beyond the file size): `init` returns a negative error code and never reads out of bounds.
4. Saturated int8 activations in the last layer must show up in the RMS ratio and not be masked by a high correlation.
5. Chunk boundaries when sentences are joined: no clicks (5 ms fade at the boundary).

---

### Task 1: PyTorch student model + MAC counter
`src/vtts/student/{config,model,macs}.py`. `StudentConfig(size="S"|"M", decoder="hifigan"|"istft", ...)`; `Student.forward_duration(ids) -> log_dur`; `Student.forward_latent(ids, durations) -> z[192, T]`; `Student.decode(z) -> wav`; `count_macs(cfg) -> {"duration","acoustic","decoder","per_second"}`. Tests: shapes; each preset's MACs are within budget; S has 0.4–0.8M parameters, M has 1.2–2.0M.

### Task 2: Generate the distillation dataset
`src/vtts/student/distill_data.py`, `scripts/student/build_distill_pack.py`. For each sentence in the text corpus (InfoRe1 train + synthetic sentences; target ≥ 50k sentences), the teacher (`best.pt`, noise 0) produces `ids`, `durations` (integers), `z` (fp16) and `audio` (int16). Written as `.npz` shards of 1000 sentences each. Tests: shards read back with the right shapes; the sum of durations × 256 equals the audio length.

### Task 3: Train the student (3 stages)
`src/vtts/student/train.py`. (a) duration: MSE on log-duration; (b) acoustic: L1 + cosine on `z`, with teacher-forced durations; (c) decoder: multi-resolution STFT + mel L1 + MPD/MRD adversarial + feature matching, with the teacher's `z` as input; (d) joint fine-tuning with the student's predicted `z`. Resume and NaN-skip as in Plan 2. Tests: one CPU step per stage gives a finite loss.

### Task 4: Model format + fp32 exporter + golden
`docs/model-format.md`, `src/vtts/export/format.py`, `src/vtts/export/export.py`, `scripts/student/export_student.py`. Golden: `ids`, `durations`, `z`, `pcm` for 5 sentences. Tests: model file write/read round trip in Python.

### Task 5: fp32 C runtime
`runtime/include/vtts.h`, `runtime/src/{model,ops,frontend_ids,synth}.c`, `runtime/test/golden_test.c`, `runtime/Makefile`. API: `vtts_init`, `vtts_arena_bytes(model, n_tokens, max_frames)`, `vtts_durations`, `vtts_synthesize`. Tests (`make test`): fp32 golden passes the gate; malformed model files return negative error codes (run under ASan/UBSan).

### Task 6: int8 quantization + int8 runtime
Per-channel int8 weights, int16-lane activations keeping 12 bits, static scales calibrated on 200 sentences; the last layer before tanh and the log-duration head stay fp32. Port API `vtts_port.h` (s8 and s16×s8 dot/matvec, `weights_resident`, `now_us`) with a reference C implementation. Tests: int8 golden passes the gate.

### Task 7: Decoder search + evaluation + optimization
Train 2–4 decoder configurations (hifigan-S, istft-S, istft-M, …) on 2 GPUs. Evaluate with `eval_dir` (CER, UTMOS, whistle index) on fp32 and int8 students on the host. Selection rule: within the MAC budget, CER ≤ 1.3 × teacher, least whistle. Write `docs/reports/student.md`.

**Exit gate for Plan 3:** at least one student passes the CER gate and the int8 golden gate on the host, with MMAC/s within budget. Then on to Plan 4 (P4 port, on-chip measurement, final evaluation and optimization loop).
