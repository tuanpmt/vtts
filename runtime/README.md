# vtts C runtime

A C99 runtime that turns token ids into 22.05 kHz PCM, plus the device text front-end. It has no `malloc`: the caller provides one arena whose size is computed up front, so memory use is known before synthesis starts. The same code runs on a PC (tests, CLI) and on ESP32 chips.

## Layout

| Path | Contents |
|---|---|
| `include/vtts.h` | Synthesis API: load a model, size the arena, durations, latent, decode, whole-utterance and streaming synthesis |
| `include/vtts_text.h` | Device text front-end: UTF-8 text → token ids, one callback per sentence chunk |
| `include/vtts_lex.h`, `include/vtts_zlex.h` | Readers of the English (VLEX) and Mandarin (ZLEX) blobs, read in place |
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
make -C runtime build/vtts_say        # text -> WAV, front-end chosen from the model's token set (like the firmware)
make -C runtime test                  # token set + text front-end tests (no model needed)
make -C runtime build/golden_test     # built with ASan/UBSan
uv run pytest -q tests/export         # runs the golden, streaming and text parity tests
```

The Python tests build and run the C tests, so `uv run pytest -q` at the repository root covers the runtime too.

## Device text front-end

`vtts_text_to_ids` mirrors the Python front-end (`src/vtts/frontend`) for the subset that devices need: Vietnamese words, letters and acronyms, product codes (ESP32, S3), loanwords, abbreviations, numbers (integers, decimals, thousands separators, negatives), percent, dates (d/m, d/m/yyyy), times (8:30, 8h30, 8h) and punctuation. E-mail addresses, URLs, phone numbers, ISO dates, currency and units are handled only by the Python front-end. The tables in `src/vtts_text_tables.h` are generated from Python, and `test/text_parity.tsv` checks that both produce identical ids.

`vtts_text_to_ids_ex` adds the bilingual modes, each matching `text_to_ids(text, mode)` in Python exactly:

| Mode | Token set | Needs |
|---|---|---|
| `VTTS_LANG_VI`, `VTTS_LANG_EN`, `VTTS_LANG_AUTO` | v2 (vi-en) | `lex`: VLEX blob (English lexicon + letter-to-sound, ~1.9 MB, `scripts/frontend/build_lexicon.py`) |
| `VTTS_LANG_ZH` | zh-en (ids 0–106 = v2, Mandarin from 107, 171 ids) | `lex` for English words and `zh`: ZLEX blob (Mandarin readings, ~116 KB, `scripts/frontend/build_zh_blob.py`) |
| `VTTS_LANG_KO` | ko-en (ids 0–106 = v2, Korean from 107, 153 ids) | `lex` for English words only: the Korean rules, exception table and normalizer strings are compiled in (`src/vtts_text_tables.h`) |
| `VTTS_LANG_HI` | hi-en (ids 0–106 = v2, Hindi from 107, 157 ids) | `lex` for English words only: the Devanagari letter tables, exception table, numbers and normalizer strings are compiled in (`src/vtts_text_tables.h`) |
| `VTTS_LANG_JA` | ja-en (ids 0–106 = v2, Japanese from 107, 144 ids) | `lex` for English words and `ja`: JLEX blob (Japanese reading tables and NFKC data, ~721 KB, `scripts/frontend/build_ja_blob.py`) |

The blobs are read in place (flash is fine) and must stay alive while they are used:

```c
static vtts_lex lex;   /* small reader structs; no malloc */
static vtts_zlex zh;
vtts_lex_init(&lex, lex_blob, lex_size);
vtts_zlex_init(&zh, zh_blob, zh_size);          /* < 0: not a ZLEX v1 blob */
vtts_text_opts o = {.lang = VTTS_LANG_ZH, .lex = &lex, .zh = &zh};  /* zh may be NULL for the other modes */
int chunks = vtts_text_to_ids_ex(utf8, ws, &o, on_ids, user);  /* ws: vtts_text_ws, ~145 KB, PSRAM */
```

Japanese: `vtts_jlex_init(&ja, ja_blob, ja_size)` (`static vtts_jlex ja;`, < 0: not a JLEX v1 blob), then `vtts_text_opts o = {.lang = VTTS_LANG_JA, .lex = &lex, .ja = &ja};`. Without `ja`, kana and kanji give no ids (and NFKC is skipped). Without `zh`, Han characters give no ids; without `lex`, English words are not pronounced (acronyms are still spelled). A zh-en model must be fed only zh-mode ids (its embedding has 171 rows), a ko-en model only ko-mode ids (153 rows), a hi-en model only hi-mode ids (157 rows), a ja-en model only ja-mode ids (144 rows). Korean and Hindi need no extra blob: `vtts_text_opts o = {.lang = VTTS_LANG_KO, .lex = &lex};` (or `VTTS_LANG_HI`). `make -C runtime test` builds the blobs and runs every text parity test and the fuzz runs (with ASan/UBSan).

### Choosing the front-end from the model

A model file records its token set (dim `token_set`, see [docs/model-format.md](../docs/model-format.md#token_set-added-in-format-revision-11); older files map by `vocab`). Pick the mode from it instead of guessing:

```c
int ts = vtts_token_set(&m);                    /* VTTS_TOKSET_V1, _VI_EN, _ZH_EN, _KO_EN, _JA_EN, _HI_EN, _UNKNOWN */
vtts_lang lang;
if (vtts_text_default_lang(ts, &lang) < 0) { /* unknown token set: no device front-end, ids only */ }
if (vtts_text_lang_for(ts, "auto", &lang) < 0) { /* not a mode of this token set */ }
```

| Token set | Modes (`vtts_text_modes`) | Default |
|---|---|---|
| `v1` | `vi` (`VTTS_LANG_V1`) | `vi` |
| `vi-en` | `vi`, `en`, `auto` | `vi` |
| `zh-en` | `zh` (Han → Mandarin, Latin words → English, numbers in Mandarin; the only zh-en mode of the Python front-end) | `zh` |
| `ko-en` | `ko` (Hangul → Korean, Latin words → English, numbers in Korean; the only ko-en mode of the Python front-end) | `ko` |
| `hi-en` | `hi` (Devanagari → Hindi, Latin words → English, numbers in Hindi; the only hi-en mode of the Python front-end) | `hi` |
| `ja-en` | `ja` (kana/kanji → Japanese, Latin words → English, numbers in Japanese; the only ja-en mode of the Python front-end) | `ja` |
| `es-en`, `id-en`, `pt-en` (unknown to the runtime), unknown | none (Python front-end only) | |

`tools/vtts_say.c` is the host version of this path: `vtts_say MODEL.vtts OUT.wav --lex lex_en.bin --zh zh_lex.bin --ja ja_lex.bin [--lang MODE] "text"` prints the token set, the mode and the ids of each chunk, then writes the audio.

## Porting

A new chip needs an implementation of the kernels in `vtts_port.h` (the reference C versions in `src/vtts_kernels_ref.c` are the fallback) and, for multi-core speedups, a `vtts_par_run`. The firmware `selftest` command compares SIMD kernels with the reference C results.
