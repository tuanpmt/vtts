# ESP32-P4 and ESP32-S3 firmware

Runs the whole chain on the chip: text → token ids (C front-end) → streaming synthesis (C int8 runtime) → speaker. Type a sentence on the serial console and the board speaks it; `bench` prints RTF, RMS and memory use.

Supported boards:

| Board | Chip | Flash / PSRAM | Speaker path | `BOARD=` |
|---|---|---|---|---|
| Waveshare ESP32-P4-86-Panel-ETH-2RO | ESP32-P4 | 32 MB / 32 MB | ES8311 | `esp32-p4-86-panel-eth-2ro` (default) |
| Waveshare ESP32-P4-NANO | ESP32-P4 | 16 MB / 32 MB | ES8311 | `esp32-p4-nano` |
| Waveshare ESP32-S3-Touch-LCD-2.8 | ESP32-S3R8 | 16 MB / 8 MB (octal) | PCM5101 | `esp32-s3-touch-lcd-2.8` |

## Source layout

| Path | Contents |
|---|---|
| `main/main.c` | Start-up: models, memory (PSRAM first, internal RAM left for DMA), tasks |
| `main/synth.c` | Text or token ids to PCM, `SAID` / `DUMPED` / `REPORT` lines |
| `main/speaker.c` | Playback: soft limiter, stream buffer, prebuffer and chunk size from the measured RTF |
| `main/console.c` | Serial input and commands (`esp_console`; `help` lists them) |
| `main/selftest.c` | SIMD kernel checks (`selftest`, `fusetest`) |
| `components/bsp/` | Board support: speaker drivers and one folder per board ([README](components/bsp/README.md)) |

## Build and flash

```bash
# needs ESP-IDF v6.1; build.sh sources the IDF environment and copies both models into main/
./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor             # 86-Panel
BOARD=esp32-p4-nano ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor  # NANO
BOARD=esp32-s3-touch-lcd-2.8 ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor    # S3-Touch-LCD-2.8
```

The model files come from the [GitHub releases](https://github.com/tuanpmt/vtts/releases) or [Hugging Face](https://huggingface.co/tuanpm/vtts) (folder `vi/`). The serial console commands are listed in the [main README](../../README.md#serial-console).

`build.sh` also builds the front-end blobs once, from the Python tables: `main/lex_en.bin` (VLEX, English lexicon, ~1.9 MB), `main/lex_zh.bin` (ZLEX, Mandarin readings, ~116 KB) and `main/lex_ja.bin` (JLEX, Japanese readings and NFKC data, ~721 KB). They are embedded in the app image and read in place from flash. `lex_zh.bin` and `lex_ja.bin` are optional: when one is missing at configure time the firmware builds without it and zh-en (ja-en) models skip Han characters (kana and kanji); the console prints a warning at start-up. Delete `main/lex_ja.bin` before building to save its flash when no ja-en model is used.

Each board has its own build directory and `sdkconfig`. Shared configuration lives in `sdkconfig.defaults`; chip-specific settings live in `sdkconfig.defaults.esp32p4` and `sdkconfig.defaults.esp32s3`.

## Languages and text modes

The firmware chooses the text front-end from the token set recorded in each model file (`token_set`, [docs/model-format.md](../../docs/model-format.md#token_set-added-in-format-revision-11)); files exported before the field existed map by vocabulary size (65 → v1, 107 → vi-en, 171 → zh-en, ...). Start-up prints `model S: ..., token set zh-en (header), lang zh` per model. Each model keeps its own mode; `lang <mode>` changes the current model's mode and refuses modes of other token sets.

| Token set | `lang` modes | Default | Text on the device |
|---|---|---|---|
| `v1` | `vi` | `vi` | Vietnamese |
| `vi-en` | `vi`, `en`, `auto` | `vi` | Vietnamese + English (`vi` also reads English words; `auto` decides per sentence) |
| `zh-en` | `zh` | `zh` | Mandarin + English: Han characters in Mandarin, Latin words in English, numbers in Mandarin (same as `text_to_ids(text, "zh")` in Python) |
| `ko-en` | `ko` | `ko` | Korean + English: Hangul in Korean (standard pronunciation rules and the exception table), Latin words in English, numbers in Korean with counters (same as `text_to_ids(text, "ko")` in Python). No extra blob: the Korean tables are compiled into the firmware |
| `hi-en` | `hi` | `hi` | Hindi + English: Devanagari in Hindi (letter rules, anusvara, schwa deletion and the exception table), Latin words in English, numbers in Hindi with lakh and crore, the danda ends a sentence (same as `text_to_ids(text, "hi")` in Python). No extra blob: the Hindi tables are compiled into the firmware |
| `ja-en` | `ja` | `ja` | Japanese + English: kana and kanji in Japanese (longest match over the JLEX tables, kanji defaults), Latin words in English, numbers in Japanese with counters and their sound changes (same as `text_to_ids(text, "ja")` in Python) |
| `es-en`, `id-en`, `pt-en` | `es`, `id`, `pt` | `es`, `id`, `pt` | Spanish, Indonesian, Brazilian Portuguese + English: plain Latin words by the Latin-script rules (own letters, word lists, CamelCase, acronyms, spelling), numbers, dates, times, money and units in the language (same as `text_to_ids` in Python with mode `es`, `id` or `pt`). No extra blob |
| `th-en` | `th` | `th` | Thai + English: Thai words from the word list, syllables by the spelling rules, tones from class, mark and syllable type, Latin words in English, numbers in Thai (same as `text_to_ids(text, "th")` in Python). No extra blob: the Thai tables (about 80 KB, mostly the word list) are compiled into the firmware; `bench` uses four Thai sentences |

`ids <ids;ids...>` is unchanged and works with every model (ids must be below the model's vocabulary size). `bench` uses four sentences in the model's language (Mandarin, Korean, Hindi, Japanese, Spanish, Indonesian, Portuguese or Thai) and the Vietnamese ones otherwise.

## Flash budget

The app partition (`partitions.csv`, `factory`, 8 MB) holds the code, both models, `lex_en.bin`, `lex_zh.bin` and `lex_ja.bin`. With the largest models (zh-en M 2.62 MB + S 1.23 MB, int8) the image is 6.30 MB on the ESP32-P4 (2.09 MB, 25%, free) and 6.18 MB on the ESP32-S3 (2.21 MB, 26%, free); with two ko-en models (2.61 + 1.22 MB) the images are 6.29 MB (P4, 2.10 MB, 25%, free) and 6.18 MB (S3, 2.21 MB, 26%, free). The Korean front-end adds about 15 KB of code and tables and no blob, the Hindi front-end about 25 KB and no blob; the Spanish, Indonesian and Portuguese front-ends together add about 62 KB (35 KB code, 27 KB tables) and no blob: with two es-en models (2.60 + 1.22 MB) the ESP32-P4 image is 6.35 MB (2.04 MB, 24%, free). The Japanese front-end adds `lex_ja.bin` (721 KB) and about 29 KB of code and tables: with two ja-en models (2.60 + 1.22 MB, int8) the ESP32-P4 image (86-Panel) is 7.03 MB (1.36 MB, 16%, free); every image that embeds `lex_ja.bin` grows by about 0.75 MB. The Thai front-end adds about 100 KB (code and tables, mostly the word list) and no blob. With every front-end built in (vi, en, zh, ko, hi, ja, es, id, pt, th) and two ja-en models, the ESP32-P4 image (86-Panel) is 7.23 MB (1.15 MB, 14%, free). The build prints the exact numbers.

## Output

Each sentence prints a `REPORT` line: audio duration, synthesis time and RTF (below 1.0 is faster than real time).

## Self-test

`selftest` checks the SIMD kernels against results computed in plain C: one row, many rows, weights read from the model, and both cores running the kernel at the same time. On the S3 the kernel does not use the fused multiply-accumulate-and-load instruction (`ee.vmulas.s8.accx.ld.ip`). An earlier kernel with that instruction gave wrong sums on two cores; a rewritten one is correct (`fusetest` checks it) but barely faster, so the default kernel loads first and then multiply-accumulates.

## Adding a board

Board support is the ESP-IDF component [`components/bsp/`](components/bsp/README.md): one folder per board in `boards/<id>/` (`board.h` with pins and defaults, `board.cmake` with the chip and speaker driver, `sdkconfig.defaults`) and shared speaker drivers in `drivers/`. A new board is a new folder; see [components/bsp/README.md](components/bsp/README.md).
