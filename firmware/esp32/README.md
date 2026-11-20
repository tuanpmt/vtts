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
| `main/selftest.c` | SIMD kernel checks (`selftest`, `fusetest`, `memtest`) |
| `components/bsp/` | Board support: speaker drivers and one folder per board ([README](components/bsp/README.md)) |

## Build and flash

```bash
# needs ESP-IDF v6.1; build.sh sources the IDF environment and copies both models into main/
./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor             # 86-Panel
BOARD=esp32-p4-nano ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor  # NANO
BOARD=esp32-s3-touch-lcd-2.8 ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor    # S3-Touch-LCD-2.8
```

The model files come from the [GitHub releases](https://github.com/tuanpmt/vtts/releases) or [Hugging Face](https://huggingface.co/tuanpm/vtts) (one folder per voice; the released voices are listed in the [README](../../README.md#released-voices)). The serial console commands are [below](#serial-console).

`build.sh` also builds the front-end blobs once, from the Python tables: `main/lex_en.bin` (VLEX, English lexicon, ~1.9 MB), `main/lex_zh.bin` (ZLEX, Mandarin readings, ~116 KB) and `main/lex_ja.bin` (JLEX, Japanese readings and NFKC data, ~721 KB). They are read in place from flash. `lex_en.bin` is always embedded; `lex_zh.bin`, `lex_ja.bin` and `lex_ru.bin` only when their language is compiled in (below). When a needed blob is missing at configure time the firmware builds without it and zh-en (ja-en) models skip Han characters (kana and kanji); the console prints a warning at start-up.

**Languages compiled in.** Vietnamese and English are always built. Every other language (zh, ko, ja, hi, th, es, id, pt, fr, de, it, tr, ru, pl, ar, fi, el, ms, tl, sw, nl, sv, no, da, lo, km, my) is compiled in only when one of the two models needs it: `main/vtts_langs.cmake` reads the `token_set` dim of `main/model_s.vtts` and `main/model_m.vtts` at configure time (files without the dim: by vocabulary size, only for the sets that existed before it) and sets `VTTS_ENABLE_<L>` (`runtime/include/vtts_langs.h`); the configure step prints the list. So a vi-en image carries no Japanese tables and no `lex_ja.bin`. `VTTS_LANGS=all ./build.sh ...` builds every language, `VTTS_LANGS=zh,ja ./build.sh ...` exactly those. On the ESP32-P4 (86-Panel, ESP-IDF 6.1, two int8 models of about 1.2 + 2.6 MB) the image is 5.82 MB (27% of the 8 MB app partition free) for vi-en, 6.58 MB (18% free) for ja-en with `lex_ja.bin`, 6.29 MB (21% free) for ru-en with `lex_ru.bin`, 5.98 MB (25% free) for ar-en, and 7.91 MB (1% free) with `VTTS_LANGS=all`.

Each board has its own build directory and `sdkconfig`. Shared configuration lives in `sdkconfig.defaults`; chip-specific settings live in `sdkconfig.defaults.esp32p4` and `sdkconfig.defaults.esp32s3`.

Default speaker settings per board (change them at run time with `vol` and `gain`):

<!-- BEGIN:boards -->
| `BOARD=` | Board | Speaker path | Default volume |
|---|---|---|---|
| `esp32-p4-86-panel-eth-2ro` (default) | ESP32-P4-86-Panel-ETH-2RO | ES8311 | `vol 70`, `gain 0` |
| `esp32-p4-nano` | ESP32-P4-NANO | ES8311 | `vol 90`, `gain 12` |
| `esp32-s3-touch-lcd-2.8` | ESP32-S3-Touch-LCD-2.8 | PCM5101 | `vol 80`, `gain 6` |
| `echoear` | EchoEar 2.0 (ESP32-S3) | ES8311 | `vol 75`, `gain 6` |
<!-- END:boards -->

## Serial console

Type a sentence and press Enter; the board speaks it. Other commands:

| Command | Effect |
|---|---|
| `model s` / `model m` | Lite or quality model |
| `lang <mode>` | Text mode; the modes follow the model's token set: `vi` / `en` / `auto` for vi-en (`vi` also reads English words in Vietnamese sentences), `zh` for zh-en, `ko` for ko-en, `ja` for ja-en, and one mode per other pair ([below](#languages-and-text-modes)) |
| `vol 0-100`, `gain dB` | Volume; the digital gain has a soft limiter |
| `speed 0.7-1.6` | Speaking rate (higher is slower) |
| `expr 0.5-2.5` | Intonation range (models with a pitch predictor) |
| `bench`, `prof` | RTF on four fixed sentences; time per stage |
| `selftest` | SIMD kernels against plain C, including both cores at once |
| `dump <text>` | Synthesize and send PCM to the PC: `scripts/device/say.py PORT "dump <text>" --dump-dir out/` |
| `ids <ids;ids...>` | Speak token ids from the PC's front-end: `scripts/device/say.py --lang vi\|en\|mixed PORT "<text>"` |
| `help` | List the commands; `chunk N`, `first N`, `cores 1\|2` and `fusetest` are for experiments |

Any line that is not a command is spoken, and every command ends with a `DONE` line.

## Languages and text modes

The firmware chooses the text front-end from the token set recorded in each model file (`token_set`, [docs/model-format.md](../../docs/model-format.md#token_set-added-in-format-revision-11)); files exported before the field existed map by vocabulary size (65 → v1, 107 → vi-en, 171 → zh-en, ...). Start-up prints `model S: ..., token set zh-en (header), lang zh` per model. A model starts in the first mode of its token set (the Default column), unless its file names another mode in the optional dim `text_mode`: the English-only voice `nu-en` (v0.9.0) uses the vi-en token set and records `en`, so it starts in English (`model S: ..., token set vi-en (header), lang en`). Each model keeps its own mode; `lang <mode>` changes the current model's mode and refuses modes of other token sets.

| Token set | `lang` modes | Default | Text on the device |
|---|---|---|---|
| `v1` | `vi` | `vi` | Vietnamese |
| `vi-en` | `vi`, `en`, `auto` | `vi` (`en` for `nu-en`) | Vietnamese + English (`vi` also reads English words; `auto` decides per sentence). The English-only voice `nu-en` is meant for `en`; `bench` uses four English sentences in `en` (v0.9.0; before, the Vietnamese ones) |
| `zh-en` | `zh` | `zh` | Mandarin + English: Han characters in Mandarin, Latin words in English, numbers in Mandarin (same as `text_to_ids(text, "zh")` in Python) |
| `ko-en` | `ko` | `ko` | Korean + English: Hangul in Korean (standard pronunciation rules and the exception table), Latin words in English, numbers in Korean with counters (same as `text_to_ids(text, "ko")` in Python). No extra blob: the Korean tables are compiled into the firmware |
| `hi-en` | `hi` | `hi` | Hindi + English: Devanagari in Hindi (letter rules, anusvara, schwa deletion and the exception table), Latin words in English, numbers in Hindi with lakh and crore, the danda ends a sentence (same as `text_to_ids(text, "hi")` in Python). No extra blob: the Hindi tables are compiled into the firmware |
| `ja-en` | `ja` | `ja` | Japanese + English: kana and kanji in Japanese (longest match over the JLEX tables, kanji defaults), Latin words in English, numbers in Japanese with counters and their sound changes (same as `text_to_ids(text, "ja")` in Python) |
| `es-en`, `id-en`, `pt-en` | `es`, `id`, `pt` | `es`, `id`, `pt` | Spanish, Indonesian, Brazilian Portuguese + English: plain Latin words by the Latin-script rules (own letters, word lists, CamelCase, acronyms, spelling), numbers, dates, times, money and units in the language (same as `text_to_ids` in Python with mode `es`, `id` or `pt`). No extra blob |
| `it-en`, `tr-en` | `it`, `tr` | `it`, `tr` | Italian, Turkish + English (same as `text_to_ids` in Python with mode `it` or `tr`). No extra blob |
| `ru-en` | `ru` | `ru` | Russian + English: stress from `lex_ru.bin` (RLEX), the reduction, softness and voicing rules, Latin words in English, numbers in Russian (same as `text_to_ids(text, "ru")` in Python). `lex_ru.bin` (358 KB) is embedded only with Russian; the Russian code and tables add about 75 KB; `bench` uses four Russian sentences |
| `pl-en` | `pl` | `pl` | Polish + English: Latin words tagged by the Latin-script rules for Polish, the spelling, nasal-vowel, voicing and stress rules, numbers in Polish (same as `text_to_ids(text, "pl")` in Python). No blob, about 66 KB of code and tables; `bench` uses four Polish sentences |
| `ar-en` | `ar` | `ar` | Arabic + English: vowels restored from the spelling table, the text's own vowel marks, the word table with clitics and endings, word patterns, then the pausal reading and stress; Latin words in English, numbers in Arabic (same as `text_to_ids(text, "ar")` in Python). No extra blob, but the Arabic front-end (about 108 KB of code and tables; the app grows by 110,448 bytes) is compiled in only for an ar-en model (or `VTTS_LANGS` with `ar`). `bench` uses four Arabic sentences |
| `nl-en`, `sv-en`, `no-en` | `nl`, `sv`, `no` | `nl`, `sv`, `no` | Dutch, Swedish, Norwegian (Bokmål) + English: sentence split that keeps abbreviation (and Norwegian ordinal) dots, plain Latin words by the Latin-script rules, the shared scanner normalizer (numbers, ordinals, dates, times, money, units), the Dutch rules or the Swedish / Norwegian rules with word tones (same as `text_to_ids` in Python with mode `nl`, `sv` or `no`). No extra blob; compiled only when an embedded model has that token set, about 44 KB of flash for one language and 89 KB for all three |
| `th-en` | `th` | `th` | Thai + English: Thai words from the word list, syllables by the spelling rules, tones from class, mark and syllable type, Latin words in English, numbers in Thai (same as `text_to_ids(text, "th")` in Python). No extra blob: the Thai tables (about 80 KB, mostly the word list) are compiled into the firmware; `bench` uses four Thai sentences |
| `fr-en` | `fr` | `fr` | French + English: plain Latin words by the French rules (an elided clitic follows its word: l'iPhone), French numbers, dates, times, money and units, liaison and elision, silent letters, e muet (same as `text_to_ids(text, "fr")` in Python). No extra blob. About 70 KB of code and tables at -O2 on the ESP32-P4; `bench` uses four French sentences |
| `de-en` | `de` | `de` | German + English: sentence split that keeps ordinal and abbreviation dots, plain Latin words by the Latin-script rules, the morph split over the stem list, vowel length, stress and the exception table, numbers, ordinals, dates, times, euro amounts and units in German (same as `text_to_ids(text, "de")` in Python). No extra blob |
| `fi-en` | `fi` | `fi` | Finnish + English: spelling, length and stress rules, Latin words by the Latin-script rules, numbers, dates, times, euros and units in Finnish (same as `text_to_ids(text, "fi")` in Python). No extra blob; built only when a model is fi-en (`VTTS_LANGS`, below); `bench` uses four Finnish sentences |
| `el-en` | `el` | `el` | Greek + English: Greek letters, digraphs, synizesis and the tonos, Latin words in English, numbers with gender, dates, times, euros and units in Greek, `;` as the question mark (same as `text_to_ids(text, "el")` in Python). No extra blob; built only when a model is el-en (`VTTS_LANGS`); `bench` uses four Greek sentences |
| `ms-en` | `ms` | `ms` | Malay + English: the Indonesian rules with the Malay digraphs, e table, numbers (lapan, sejuta, perpuluhan), months, times (pukul 8.30 pagi) and ringgit (same as `text_to_ids(text, "ms")` in Python). No extra blob; compiled only when a model is ms-en (see Flash budget); `bench` uses four Malay sentences |
| `tl-en` | `tl` | `tl` | Tagalog + English: plain Latin words by the Latin-script rules (ñ and accent marks, word lists, hyphenated English such as i-share, spelling), glottal stops and the stress table, native numbers with the linker, Spanish-derived clock times and peso prices (same as `text_to_ids(text, "tl")` in Python). No extra blob; compiled only when a model is tl-en (see Flash budget); `bench` uses four Tagalog sentences |
| `my-en` | `my` | `my` | Burmese + English: Zawgyi text converted to Unicode, syllables by the spelling rules with tones, Latin words in English, numbers in Burmese (same as `text_to_ids(text, "my")` in Python). No blob; compiled only when a model of the image has the my-en token set (or `VTTS_LANGS` with `my`): about 16 KB of code and tables plus the 18 KB normalizer engine it shares with Khmer; `bench` uses four Burmese sentences |
| `km-en` | `km` | `km` | Khmer + English: Khmer words from the word list, syllables by the cluster rules, onset, rhyme and override tables, Latin words in English, numbers in Khmer (same as `text_to_ids(text, "km")` in Python). No blob; compiled only when a model of the image has the km-en token set (or `VTTS_LANGS` with `km`): about 230 KB of code and tables; `bench` uses four Khmer sentences |
| `th-en` | `th` | `th` | Thai + English: Thai words from the word list, syllables by the spelling rules, tones from class, mark and syllable type, Latin words in English, numbers in Thai (same as `text_to_ids(text, "th")` in Python). No extra blob: the Thai tables (about 80 KB, mostly the word list) are compiled into the firmware; `bench` uses four Thai sentences |
| `sw-en` | `sw` | `sw` | Swahili + English: plain Latin words by the Latin-script rules (word lists, CamelCase, acronyms, Swahili spelling), numbers in the counting form, dates with tarehe, times with saa, shilingi and units before the number (same as `text_to_ids(text, "sw")` in Python). No extra blob; compiled only when a model is sw-en (below); `bench` uses four Swahili sentences |
| `da-en` | `da` | `da` | Danish + English: plain Latin words by the Latin-script rules (æ ø å é, word lists, known words and compounds, spelling), the NST readings of the 20,000 most frequent words, compounds and the spelling rules with stress and stød, numbers, dates, times, kroner and units in Danish (same as `text_to_ids(text, "da")` in Python). No extra blob; built only when a model is da-en (`VTTS_LANGS`, below; about 280 KB of code and tables, mostly the words with their readings); `bench` uses four Danish sentences |
| `lo-en` | `lo` | `lo` | Lao + English: Lao words from the word list, syllables by the spelling patterns, the six Vientiane tones, Latin words in English, numbers in Lao (same as `text_to_ids(text, "lo")` in Python). No extra blob; built only when a model is lo-en (`VTTS_LANGS`, below; about 70 KB of code and tables); `bench` uses four Lao sentences |

`ids <ids;ids...>` is unchanged and works with every model (ids must be below the model's vocabulary size). `bench` uses four sentences in the model's language (Mandarin, Korean, Hindi, Japanese, Spanish, Indonesian, Portuguese, Thai, Swahili, Danish, Lao, Khmer or Burmese) and the Vietnamese ones otherwise.

## Flash budget

The app partition (`partitions.csv`, `factory`, 8 MB) holds the code, both models, `lex_en.bin`, `lex_zh.bin` and `lex_ja.bin`. With the largest models (zh-en M 2.62 MB + S 1.23 MB, int8) the image is 6.30 MB on the ESP32-P4 (2.09 MB, 25%, free) and 6.18 MB on the ESP32-S3 (2.21 MB, 26%, free); with two ko-en models (2.61 + 1.22 MB) the images are 6.29 MB (P4, 2.10 MB, 25%, free) and 6.18 MB (S3, 2.21 MB, 26%, free). The Korean front-end adds about 15 KB of code and tables and no blob, the Hindi front-end about 25 KB and no blob; the Spanish, Indonesian and Portuguese front-ends together add about 62 KB (35 KB code, 27 KB tables) and no blob: with two es-en models (2.60 + 1.22 MB) the ESP32-P4 image is 6.35 MB (2.04 MB, 24%, free). The Japanese front-end adds `lex_ja.bin` (721 KB) and about 29 KB of code and tables: with two ja-en models (2.60 + 1.22 MB, int8) the ESP32-P4 image (86-Panel) is 7.03 MB (1.36 MB, 16%, free); every image that embeds `lex_ja.bin` grows by about 0.75 MB. The Thai front-end adds about 100 KB (code and tables, mostly the word list) and no blob. The French front-end adds about 70 KB, no blob; the German front-end about 91 KB (41 KB code, 50 KB tables), the Italian and Turkish front-ends about 51 KB and 44 KB (host `-Os` build), no blob. Each front-end is built only into images whose models need it, so an image carries only its own languages. With every front-end built in (vi, en, zh, ko, hi, ja, es, id, pt, th) and two ja-en models, the ESP32-P4 image (86-Panel) is 7.23 MB (1.15 MB, 14%, free). The Lao front-end adds about 72 KB (18 KB code, 55 KB tables), the Danish front-end about 280 KB (27 KB code, 253 KB tables, mostly the 20,000 words with their NST readings), no blob: with two random lo-en models (2.62 + 1.23 MB) the ESP32-P4 image is 7.33 MB (1.06 MB, 13%, free), with two da-en models (2.61 + 1.23 MB) 7.53 MB (0.81 MB, 10%, free), each still with `lex_ja.bin` embedded (measured before the per-language build). The build prints the exact numbers.

## Output

Each sentence prints a `REPORT` line: audio duration, synthesis time and RTF (below 1.0 is faster than real time).

## Self-test

`selftest` checks the SIMD kernels against results computed in plain C: one row, many rows, weights read from the model, and both cores running the kernel at the same time. On the S3 the kernel does not use the fused multiply-accumulate-and-load instruction (`ee.vmulas.s8.accx.ld.ip`). An earlier kernel with that instruction gave wrong sums on two cores; a rewritten one is correct (`fusetest` checks it) but barely faster, so the default kernel loads first and then multiply-accumulates.

`memtest` runs an int8 layer the way synthesis does: both cores, weights streamed from about 1.8 MB of PSRAM, outputs stored to PSRAM and to internal RAM, every value checked against C. On the ESP32-S3 the SIMD kernels used to wrap their 128-bit loads in a zero-overhead loop (`loopnez`), which now and then returned a wrong dot product (heard as short bursts or a changed phoneme duration); the kernels now use branch loops and the S3 output equals the ESP32-P4 output. Details: [performance report](../../docs/reports/performance.md).

Text with several sentences is synthesized one chunk (sentence) at a time with 150 ms of silence between chunks (`VTTS_CHUNK_GAP_MS`, none after the last), exactly like `runtime/build/vtts_say` and the Python renderers, so a `dump` can be compared sample by sample with the host render (`make -C runtime say_parity MODEL=...` checks the streaming path against it). `debuzz N` (default 0, off) adds a gentle high-shelf cut of N dB above about 6 kHz before the speaker: 6 dB takes about 3.3 dB off 5-10 kHz and changes 0-4 kHz by less than 0.05 dB.

## Adding a board

Board support is the ESP-IDF component [`components/bsp/`](components/bsp/README.md): one folder per board in `boards/<id>/` (`board.h` with pins and defaults, `board.cmake` with the chip and speaker driver, `sdkconfig.defaults`) and shared speaker drivers in `drivers/`. A new board is a new folder; see [components/bsp/README.md](components/bsp/README.md).
