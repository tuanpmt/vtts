# Changelog

All notable changes to this project are documented here. Model files for each release are attached to [GitHub Releases](https://github.com/tuanpmt/vtts/releases) and mirrored on [Hugging Face](https://huggingface.co/tuanpm/vtts).

## Unreleased

### Added
- **Bilingual Vietnamese + English front-end (Python):** token set v2 (v1 + English ARPAbet phonemes and stress, 107 tokens; v1 ids unchanged), CMU Pronouncing Dictionary lexicon, letter-to-sound rules learned from CMUdict for out-of-vocabulary words, English text normalization, and per-word language tagging (modes `vi`, `en`, `auto`).
- **Synthetic training data:** VoxCPM2 synthesis client and bilingual corpus builder (sentences chosen to cover rare Vietnamese syllables, English and code-switched text). About 98 h of speech per voice for `nam-1` (male) and `nu-10` (female).
- **Teacher:** bilingual training lists (`lang` column, token set v2), FLAC input resampled on load, warm-start from project checkpoints, a frame budget per batch for long utterances.
- **Documentation:** English README with a multilingual voice catalog (Vietnamese translation in `README.vi.md`), [website](https://tuanpmt.github.io/vtts/) with on-chip audio samples, Hugging Face model repository with one folder per voice, runtime optimization research for ESP32-S3 and ESP32-P4, documentation index, runtime README, this changelog and contributing guide. All design documents and reports translated to English.

### Changed
- `firmware/esp32p4/` renamed to `firmware/esp32/` (it builds for both chips); `scripts/device/p4_say.py` renamed to `say.py`.

### In progress
- Teachers for the bilingual voices `nam-1` and `nu-10`.
- C port of the English front-end for the device.
- Runtime speedups following [docs/reports/runtime-optimization-research.md](docs/reports/runtime-optimization-research.md).

## v0.3.0 (2026-11-16)

Models unchanged from v0.2.0 (S-vocos v0.1, M-vocos v0.2); runtime, firmware and boards.

### Added
- **ESP32-S3 port:** int8 SIMD kernels using `ee.vmulas.s8.accx`, two-core scheduling, and the Waveshare ESP32-S3-Touch-LCD-2.8 board (PCM5101). RTF 0.42–0.47 (S) and 0.85–0.99 (M); needs at least 8 MB of PSRAM.
- **Waveshare ESP32-P4-NANO** board, selected with `BOARD=nano`.
- Per-board default volume and gain, per-core CPU load report after each sentence, a more robust first console command.
- `selftest` also checks the SIMD kernels with both cores running at once.

### Changed
- **Runtime 2.1–2.3× faster on ESP32-P4:** GELU lookup table, multi-frame int8 kernels pipelined with the PIE instruction `esp.vmulas.s8.xacc.ld.ip`, half-size real FFT for the iSTFT, depthwise convolution, LayerNorm, activation quantization and iSTFT split across both cores. RTF 0.20–0.22 (S) and 0.34–0.42 (M); speech starts after 0.3 s (S) and 1.2 s (M). Audio correlation with v0.2.0 is 0.9998.
- Detailed numbers moved to [docs/reports/performance.md](docs/reports/performance.md).

### Fixed
- `M_PI` is defined when strict C99 headers omit it (glibc).

## v0.2.0 (2026-11-15)

### Changed
- **M-vocos v0.2** (1.73M parameters) trained with prosody v2: a frame-level pitch and energy predictor conditions the acoustic model, and an unbiased duration loss fixes the too-fast speaking rate. On 50 held-out sentences the mean duration is 5.80 s per sentence (v0.1: 4.95 s, human reader: 6.08 s) and pitch variation is 2.37 semitones (v0.1: 2.32, human: 2.60). OOD CER 0.012, UTMOS 2.19.
- On-chip audio samples and numbers refreshed.

## v0.1.0 (2026-11-15)

First release: a Vietnamese prototype voice that runs entirely on an ESP32-P4.

### Added
- **Models** (int8 `.vtts`, CC BY-NC 4.0, non-commercial research use): S-vocos v0.1 (0.77M parameters, 1.1 MB) and M-vocos v0.1 (1.73M parameters), distilled from a VITS teacher trained on InfoRe1.
- **Vietnamese front-end** in Python and C with exact parity: spelling-based G2P (65 tokens, 6 tones), normalization of numbers, dates, times and abbreviations.
- **C99 runtime** without `malloc`: fp32 and int8 synthesis, streaming that is bit-exact with whole-utterance synthesis, versioned model file format.
- **Training pipeline:** InfoRe1 preparation and filtering, VITS teacher, three-stage student distillation, int8 export, evaluation tools (CER with PhoWhisper, UTMOS, DNSMOS, whistle index) and black-box baselines.
- **ESP32-P4 firmware** for the Waveshare ESP32-P4-86-Panel: type a sentence on the serial console and the board speaks it; `model`, `vol`, `gain`, `speed`, `expr`, `bench`, `prof`, `selftest` and `dump` commands; ESP32-P4 PIE SIMD int8 kernels and two-core synthesis.
