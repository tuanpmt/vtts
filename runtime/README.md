# vtts C runtime

A C99 runtime that turns token ids into 22.05 kHz PCM, plus the device text front-end. It has no `malloc`: the caller provides one arena whose size is computed up front, so memory use is known before synthesis starts. The same code runs on a PC (tests, CLI) and on ESP32 chips.

## Layout

| Path | Contents |
|---|---|
| `include/vtts.h` | Synthesis API: load a model, size the arena, durations, latent, decode, whole-utterance and streaming synthesis |
| `include/vtts_text.h` | Device text front-end: UTF-8 text → token ids, one callback per sentence chunk |
| `include/vtts_port.h` | Port interface: int8 dot-product kernels and the parallel-for used to split work across cores |
| `src/` | Model loader, synthesis graph, reference C kernels, text front-end and its generated tables |
| `ports/esp32p4/`, `ports/esp32s3/` | SIMD int8 kernels (ESP32-P4 PIE, ESP32-S3 `ee.*` instructions) |
| `ports/freertos/` | Two-core scheduler for `vtts_par_run` on FreeRTOS |
| `tools/` | `vtts_cli` (host synthesizer) and `gen_text_tables.py` (generates `src/vtts_text_tables.h` from the Python front-end) |
| `test/`, `bench/` | Golden, streaming and text parity tests; a host benchmark of the reference kernels (RTF, MMAC/s) |

The model file format is described in [docs/model-format.md](../docs/model-format.md).

## Usage

```c
vtts_model m;
if (vtts_init(&m, blob, blob_bytes) < 0) { /* bad or truncated model file */ }
size_t need = vtts_stream_arena_bytes(&m, n_ids, chunk_frames);
/* arena: `need` bytes provided by the caller (static buffer, PSRAM, ...) */
long n = vtts_synthesize_stream(&m, ids, n_ids, 1.0f /* length_scale */, chunk_frames,
                                on_pcm /* int (*)(const float *pcm, long n, void *user) */,
                                user, arena, need);
```

Streaming (Vocos-style decoder) produces exactly the same output as `vtts_synthesize()`; its working memory depends on the chunk size, not on the utterance length. `vtts_synthesize_stream_ex` adds a small first chunk for low time-to-first-audio. See the comments in `include/vtts.h` for the full API.

## Build and test on a PC

```bash
make -C runtime build/vtts_cli        # host synthesizer: token ids on stdin -> one WAV per line
make -C runtime build/golden_test     # built with ASan/UBSan
uv run pytest -q tests/export         # runs the golden, streaming and text parity tests
```

The Python tests build and run the C tests, so `uv run pytest -q` at the repository root covers the runtime too.

## Device text front-end

`vtts_text_to_ids` mirrors the Python front-end (`src/vtts/frontend`) for the subset that devices need: Vietnamese words, letters and acronyms, product codes (ESP32, S3), loanwords, abbreviations, numbers (integers, decimals, thousands separators, negatives), percent, dates (d/m, d/m/yyyy), times (8:30, 8h30, 8h) and punctuation. E-mail addresses, URLs, phone numbers, ISO dates, currency and units are handled only by the Python front-end. The tables in `src/vtts_text_tables.h` are generated from Python, and `test/text_parity.tsv` checks that both produce identical ids.

The English front-end (token set v2) is currently Python only; its C port is planned.

## Porting

A new chip needs an implementation of the kernels in `vtts_port.h` (the reference C versions in `src/vtts_kernels_ref.c` are the fallback) and, for multi-core speedups, a `vtts_par_run`. The firmware `selftest` command compares SIMD kernels with the reference C results.
