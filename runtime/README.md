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
make -C runtime resample_test         # streaming resampler of the firmware speaker path (ASan/UBSan)
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
| `VTTS_LANG_ES`, `VTTS_LANG_ID`, `VTTS_LANG_PT` | es-en (138 ids), id-en (141), pt-en (150); ids 0–106 = v2, the language from 107 | `lex` for English words only: normalizers, spelling rules, exception tables, word lists and Python's Unicode classes are compiled in (`src/vtts_text_lt.c`) |
| `VTTS_LANG_IT`, `VTTS_LANG_TR` | it-en (142 ids), tr-en (146); ids 0–106 = v2, the language from 107 | `lex` for English words only: tables compiled in (`src/vtts_text_it_tables.h`, `src/vtts_text_tr_tables.h`, about 51 KB and 44 KB with the code); each built only with `VTTS_ENABLE_IT` / `VTTS_ENABLE_TR` (1 by default) |
| `VTTS_LANG_PL` | pl-en (ids 0–106 = v2, Polish from 107, 151 ids) | `lex` for English words only: the word lists, rules, number words and the normalizer's patterns (parse trees for `src/vtts_re.c`) are compiled in (`src/vtts_text_pl_tables.h`) when `VTTS_ENABLE_PL` is non-zero (default 1) |
| `VTTS_LANG_RU` | ru-en (ids 0–106 = v2, Russian from 107, 154 ids) | `lex` for English words, `ru` (RLEX, `build/ru_lex.bin`, 358 KB) for the stress tables; the rules, number words and the normalizer's patterns (as parse trees for `src/vtts_re.c`) are compiled in (`src/vtts_text_ru_tables.h`) when `VTTS_ENABLE_RU` is non-zero (default 1) |
| `VTTS_LANG_AR` | ar-en (ids 0–106 = v2, Arabic from 107, 149 ids) | `lex` for English words only: the word table (6,920 words, 75 KB, compact encoding), spelling exceptions, word patterns, letter classes and normalizer strings are compiled in (`src/vtts_text_ar_tables.h`; the module with its tables adds 110,448 bytes to the ESP32-P4 app). Compiled only with `VTTS_ENABLE_AR` (default 1; the firmware sets it from the embedded models) |
| `VTTS_LANG_MS` | ms-en (ids 0–106 = v2, Malay from 107, 145 ids) | `lex` for English words only: the Indonesian code paths of `src/vtts_text_lt.c` with the Malay tables of `src/vtts_text_ms_tables.h` (about 9 KB with the code on the ESP32-P4); compiled only with `VTTS_ENABLE_MS` (default 1; with 0 the mode is unsupported) |
| `VTTS_LANG_TL` | tl-en (ids 0–106 = v2, Tagalog from 107, 139 ids) | `lex` for English words only: normalizer, spelling, glottal-stop and stress rules, stress table and word lists are compiled in (`src/vtts_text_tl.c`, `src/vtts_text_tl_tables.h`, about 33 KB on the ESP32-P4); compiled only with `VTTS_ENABLE_TL` (default 1; with 0 the mode is unknown) |
| `VTTS_LANG_SW` | sw-en (ids 0–106 = v2, Swahili from 107, 147 ids) | `lex` for English words only: normalizer, spelling rules, stress table and word lists are compiled in (`src/vtts_text_sw.c`, `src/vtts_text_sw_tables.h`, about 20 KB); only with `VTTS_ENABLE_SW=1` (the default; with 0 the sw-en set loads but has no mode) |
| `VTTS_LANG_NL`, `VTTS_LANG_SV`, `VTTS_LANG_NO` | nl-en, sv-en, no-en (ids 0–106 = v2, the language from 107; 159, 155, 156 ids; header codes 21, 23, 24) | `lex` for English words only: the scanner normalizer, the Dutch and the Swedish / Norwegian rules and their tables are compiled in (`src/vtts_text_nx*.c`, `vtts_text_nx_tables.h`), each language only with `VTTS_ENABLE_NL` / `_SV` / `_NO` (default 1); about 44 KB of flash for one language |
| `VTTS_LANG_MY` | my-en (ids 0–106 = v2, Burmese from 107, 160 ids) | `lex` for English words only; compiled with `VTTS_ENABLE_MY` (`include/vtts_langs.h`, 1 by default): Zawgyi conversion, canonical order and the syllable rules (`src/vtts_text_my_tables.h`, about 16 KB on the ESP32), the normalizer runs on `src/vtts_text_nsp.c` |
| `VTTS_LANG_KM` | km-en (ids 0–106 = v2, Khmer from 107, 176 ids) | `lex` for English words only; compiled with `VTTS_ENABLE_KM` (`include/vtts_langs.h`, 1 by default): the Khmer word list, overrides, rhyme and onset tables are compiled in (`src/vtts_text_km_tables.h`, about 230 KB on the ESP32), the normalizer runs on `src/vtts_text_nsp.c` |
| `VTTS_LANG_TH` | th-en (ids 0–106 = v2, Thai from 107, 162 ids) | `lex` for English words only: the Thai word list (front coded, 68 KB), respellings, spelling patterns and normalizer strings are compiled in (`src/vtts_text_th_tables.h`, about 80 KB) |
| `VTTS_LANG_FR` | fr-en (ids 0–106 = v2, French from 107, 143 ids) | `lex` for English words only: the normalizer strings, liaison lists, `lexicons/fr` tables and spelling-check clusters are compiled in (`src/vtts_text_fr_tables.h`); built only with `VTTS_ENABLE_FR` |
| `VTTS_LANG_DE` | de-en (ids 0–106 = v2, German from 107, 167 ids) | `lex` for English words only: the stem list, exception table, stress and spelling lists and normalizer strings are compiled in (`src/vtts_text_de.c`, `src/vtts_text_de_tables.h`, about 91 KB on RISC-V); built only with `VTTS_ENABLE_DE` |

Every mode except vi, en and auto belongs to an optional language that is compiled only when its switch `VTTS_ENABLE_<L>` is 1 (`include/vtts_langs.h`: `ZH KO JA HI TH ES ID PT FR DE ... DA LO`). Host builds and `make test` default all of them to 1; with a switch at 0 the module (`src/vtts_text_<l>.c`) is an empty unit, its tables are not linked, `vtts_text_lang_for` / `vtts_text_default_lang` do not offer the mode and `vtts_text_to_ids_ex` returns -1 for it. `make langs_test` builds the front-end with every optional language off and with each one alone. The firmware sets the switches from the token sets of the models it embeds (see `firmware/esp32/README.md`).
| `VTTS_LANG_FI` | fi-en (ids 0–106 = v2, Finnish from 107, 142 ids) | `lex` for English words only: normalizer tables, spelling rules, word lists and respellings are compiled in (`src/vtts_text_fi_tables.h`, about 38 KB with the code); built when `VTTS_ENABLE_FI` is not 0 (default 1) |
| `VTTS_LANG_EL` | el-en (ids 0–106 = v2, Greek from 107, 139 ids) | `lex` for English words only: normalizer tables, the Greek decomposition table and the overrides are compiled in (`src/vtts_text_el_tables.h`, about 34 KB with the code); built when `VTTS_ENABLE_EL` is not 0 (default 1) |
| `VTTS_LANG_DA` | da-en (ids 0–106 = v2, Danish from 107, 158 ids) | `lex` for English words only: the 20,000 known words with the NST readings (front coded, 245 KB), the rule, tagging and normalizer tables are compiled in (`src/vtts_text_da_tables.h`); built only with `VTTS_ENABLE_DA` (default 1) |
| `VTTS_LANG_LO` | lo-en (ids 0–106 = v2, Lao from 107, 163 ids) | `lex` for English words only: the Lao word list (front coded, 50 KB), spelling patterns and normalizer strings are compiled in (`src/vtts_text_lo_tables.h`); built only with `VTTS_ENABLE_LO` (default 1) |

The blobs are read in place (flash is fine) and must stay alive while they are used:

```c
static vtts_lex lex;   /* small reader structs; no malloc */
static vtts_zlex zh;
vtts_lex_init(&lex, lex_blob, lex_size);
vtts_zlex_init(&zh, zh_blob, zh_size);          /* < 0: not a ZLEX v1 blob */
vtts_text_opts o = {.lang = VTTS_LANG_ZH, .lex = &lex, .zh = &zh};  /* zh may be NULL for the other modes */
int chunks = vtts_text_to_ids_ex(utf8, ws, &o, on_ids, user);  /* ws: vtts_text_ws, ~145 KB, PSRAM */
```

Japanese: `vtts_jlex_init(&ja, ja_blob, ja_size)` (`static vtts_jlex ja;`, < 0: not a JLEX v1 blob), then `vtts_text_opts o = {.lang = VTTS_LANG_JA, .lex = &lex, .ja = &ja};`. Without `ja`, kana and kanji give no ids (and NFKC is skipped). Without `zh`, Han characters give no ids; without `lex`, English words are not pronounced (acronyms are still spelled). A zh-en model must be fed only zh-mode ids (its embedding has 171 rows), a ko-en model only ko-mode ids (153 rows), a hi-en model only hi-mode ids (157 rows), a ja-en model only ja-mode ids (144 rows), and likewise for es-en, id-en and pt-en. Korean, Hindi, Spanish, Indonesian and Portuguese need no extra blob: `vtts_text_opts o = {.lang = VTTS_LANG_KO, .lex = &lex};` (or `VTTS_LANG_HI`, `_ES`, `_ID`, `_PT`). `make -C runtime test` builds the blobs and runs every text parity test and the fuzz runs (with ASan/UBSan).

### Choosing the front-end from the model

A model file records its token set (dim `token_set`, see [docs/model-format.md](../docs/model-format.md#token_set-added-in-format-revision-11); older files map by `vocab`). Pick the mode from it instead of guessing. `vtts_text_model_lang` starts in the mode the file names in its optional dim `text_mode` (`m.text_mode`; `en` for the English-only voice `nu-en`, which uses the vi-en set) and otherwise in the set's first mode, like `vtts_text_default_lang`:

```c
int ts = vtts_token_set(&m);                    /* VTTS_TOKSET_V1, _VI_EN, _ZH_EN, _KO_EN, _JA_EN, _ES_EN, _ID_EN, _PT_EN, _HI_EN, _FI_EN, _EL_EN, _UNKNOWN */
vtts_lang lang;
if (vtts_text_model_lang(ts, m.text_mode, &lang) < 0) { /* unknown token set: no device front-end, ids only */ }
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
| `es-en`, `id-en`, `pt-en` | `es`, `id`, `pt` (plain Latin words by the `latin.py` rules → the language or English, numbers in the language) | `es`, `id`, `pt` |
| `it-en`, `tr-en` | `it`, `tr` (as es; Italian elision and Turkish suffixes after apostrophes; only when built in) | `it`, `tr` |
| `ar-en` | `ar` (Arabic → Arabic, Latin words → English, numbers in Arabic; the only ar-en mode of the Python front-end; only with `VTTS_ENABLE_AR`) | `ar` |
| `my-en` | `my` (Burmese, Unicode or Zawgyi → Burmese, Latin words → English, numbers in Burmese; the only my-en mode of the Python front-end; needs `VTTS_ENABLE_MY`) | `my` |
| `km-en` | `km` (Khmer → Khmer, Latin words → English, numbers in Khmer; the only km-en mode of the Python front-end; needs `VTTS_ENABLE_KM`) | `km` |
| `th-en` | `th` (Thai → Thai, Latin words → English, numbers in Thai; the only th-en mode of the Python front-end) | `th` |
| `fr-en` | `fr` (plain Latin words by the fr rules → French or English, numbers in French, liaison; with `VTTS_ENABLE_FR`) | `fr` |
| `de-en` | `de` (plain Latin words by the `latin.py` rules → German or English, numbers in German; with `VTTS_ENABLE_DE`) | `de` |
| `pl-en` | `pl` (Latin words by latin.py rules → Polish or English, numbers in Polish; with `VTTS_ENABLE_PL`) | `pl` |
| `ru-en` | `ru` (Cyrillic → Russian, Latin words → English, numbers in Russian; with `VTTS_ENABLE_RU`) | `ru` |
| `fi-en` | `fi` (plain Latin words by the `latin.py` rules → Finnish or English, numbers in Finnish; only with `VTTS_ENABLE_FI`) | `fi` |
| `el-en` | `el` (Greek → Greek, Latin words → English, numbers in Greek; only with `VTTS_ENABLE_EL`) | `el` |
| `tl-en` | `tl` (plain Latin words by the `latin.py` rules → Tagalog or English, numbers with the linker, Spanish-derived clock times and peso prices; with `VTTS_ENABLE_TL`) | `tl` |
| `ms-en` | `ms` (plain Latin words by the `latin.py` rules → Malay or English, numbers, dates, times and ringgit in Malay; with `VTTS_ENABLE_MS`) | `ms` |
| `sw-en` | `sw` (plain Latin words by the `latin.py` rules → Swahili or English, numbers, dates, times, money and units in Swahili; with `VTTS_ENABLE_SW`) | `sw` |
| `lo-en` | `lo` (Lao → Lao, Latin words → English, numbers in Lao; only with `VTTS_ENABLE_LO`) | `lo` |
| `da-en` | `da` (plain Latin words by the `latin.py` rules → Danish or English, numbers in Danish; only with `VTTS_ENABLE_DA`) | `da` |
| unknown | none (Python front-end only) | |

`tools/vtts_say.c` is the host version of this path: `vtts_say MODEL.vtts OUT.wav --lex lex_en.bin --zh zh_lex.bin --ja ja_lex.bin [--lang MODE] "text"` prints the token set, the mode and the ids of each chunk, then writes the audio.

## Porting

A new chip needs an implementation of the kernels in `vtts_port.h` (the reference C versions in `src/vtts_kernels_ref.c` are the fallback) and, for multi-core speedups, a `vtts_par_run`. The ESP32-S31 has the ESP32-P4's PIE vector unit and builds `ports/esp32p4/vtts_port_p4.c`, but only its core 1 has the PIE: there the kernels use plain C on core 0, and `ports/freertos/` runs the caller on core 1 and shares each pass with core 0 from both ends (`vtts_par_run_simd` marks the int8 layers); a target without a port runs the reference kernels. The firmware `selftest` command compares SIMD kernels with the reference C results.
