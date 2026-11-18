# Changelog

All notable changes to this project are documented here. Model files for each release are attached to [GitHub Releases](https://github.com/tuanpmt/vtts/releases) and mirrored on [Hugging Face](https://huggingface.co/tuanpm/vtts).

## Unreleased

### Added
- **Bilingual device front-end (C):** `vtts_text_to_ids_ex` with modes vi, en and auto (phoneme set v2): English normalization and G2P, per-word language tagging and chunk packing, exactly matching Python (2,018 fixture cases, 13,023 in a larger run, fuzz clean). The English lexicon and letter-to-sound rules ship as a 1.9 MB `VLEX` blob read in place (`scripts/frontend/build_lexicon.py`, `vtts_lex_*`).
- **Language modules** in Python (`src/vtts/frontend/languages.py`) and C (`LANGS`): a new language plugs in a normalizer, a word-to-token function and a tagging rule; see docs/frontend/pronunciation-rules.md.
- **Evaluation of bilingual teachers:** English and mixed out-of-domain sets, language-aware CER/WER, Whisper with a forced language; `nam-1` at 100k: CER 0.005 (vi), 0.015 (en), 0.033 (mixed).
- **Bilingual distillation:** v2 distill packs from a `{text, lang}` corpus, presets `M-vocos-p-bi`, `S-vocos-p-bi` and `M-vocos-p-bi-s3`, `run_bilingual_chain.sh`.
- Firmware command `ids ...` and `say.py --lang` to play token ids from a host front-end.
- **On-device bilingual text:** the firmware embeds the VLEX lexicon (read in place from flash) and uses the bilingual front-end for models with token set v2; `lang vi|en|auto` sets the mode. Same audio as the host front-end on ESP32-P4.

- **Bilingual teacher results at 200k:** `nam-1` CER 0.005 / 0.012 / 0.018 (vi / en / mixed), UTMOS 3.41 / 4.04 / 3.47; `nu-10` CER 0.002 / 0.012 / 0.019, UTMOS 3.67 / 4.38 / 3.83 ([report](docs/reports/bilingual-teacher-eval.md)).
- **First bilingual student** (`nam-1` M, 1.83M params, 2.6 MB): CER 0.021 / 0.014 / 0.035, RTF 0.26–0.28 on the ESP32-P4 with the on-device front-end. Not released (see below).
- `render_student_c.py --lang` renders bilingual models through the C runtime for evaluation.
- **Chinese front-end (Python):** token set `zh-en` (v2 ids 0–106 unchanged, Mandarin initials, finals and tones from id 107), `text_to_ids(text, "zh")` for Chinese with English words, readings from a default-per-character table plus a polyphone phrase table generated from pypinyin (`scripts/frontend/build_zh_lexicon.py`), Chinese number, date, time and percentage reading; teacher rows with lang `zh` use it.
- **Chinese device front-end (C):** mode `VTTS_LANG_ZH` of `vtts_text_to_ids_ex` (token set zh-en) with Chinese normalization, forward-maximum-matching readings and English words, exactly matching `text_to_ids(text, "zh")` (9,397 fixture cases, 78,017 in a larger run, fuzz clean). The reading tables ship as a 116 KB `ZLEX` blob read in place (`scripts/frontend/build_zh_blob.py`, `vtts_zlex_*`); the text workspace grows by 2 KB. `make -C runtime test` runs all text front-end tests.
- **Token set in the model file:** optional dim `token_set` (format revision 1.1: v1, vi-en, zh-en, ko-en, ja-en), written by `write_model` / `write_model_int8` and `export_student.py --token-set` (default: from the checkpoint or the vocab size), read with `vtts_token_set()` in C and `token_set_of()` in Python. Files without it map by vocab as before, and older runtimes ignore it.
- **Chinese on the device:** the firmware picks the text front-end from each model's token set instead of its vocab size, embeds the 116 KB ZLEX blob next to the English lexicon (`build.sh` builds `main/lex_zh.bin`), and accepts `lang zh` for zh-en models (`lang` refuses modes of other token sets; ko-en and ja-en models take `ids` only). `bench` uses Mandarin sentences for zh-en models. Host tool `vtts_say` runs the same text → ids → audio path on a PC.
- **Korean device front-end (C):** mode `VTTS_LANG_KO` of `vtts_text_to_ids_ex` (token set ko-en) with Korean normalization (Sino-Korean and native numbers with counters, dates with 유월/시월, times, decimals, percent, ranges, phone numbers, money, units, product codes in English), the exception table and the ordered pronunciation rules, exactly matching `text_to_ids(text, "ko")` (11,369 fixture cases, 126,277 in a larger run, fuzz clean). The tables are generated into `vtts_text_tables.h` (about 4 KB, no blob); the text workspace grows by 2 KB. The firmware accepts `lang ko` (default for ko-en models), `bench` has Korean sentences, and `vtts_say` runs ko-en models.
- **Korean front-end (Python):** token set `ko-en` (v2 ids 0–106 unchanged, 46 Korean onset, vowel and coda tokens from id 107), `text_to_ids(text, "ko")` for Korean with English words: Hangul decomposition, the standard pronunciation rules (liaison, neutralization, nasalization, liquidization, aspiration, tensification, palatalization) as an ordered rule table plus an exception table, Sino-Korean and native number reading with counters, dates, times and units; teacher rows with lang `ko` use it. Korean corpus builder `scripts/data/build_ko_corpus.py` (Korean Wikipedia).
- **Japanese front-end (Python):** token set `ja-en` (v2 ids 0–106 unchanged, 37 Japanese phonemes in the style of Open JTalk from id 107; long vowels as repeated vowels, `N` and `cl` as tokens), `text_to_ids(text, "ja")` for Japanese with English words: kana rules, kanji readings by longest match over word, context (after kanji / katakana) and per-kanji tables generated from Open JTalk's dictionary with pyopenjtalk (60,000 entries, 1.3 MB TSV; 98.2% mora agreement with pyopenjtalk on held-out Wikipedia sentences), Japanese numbers with counters and sound changes, dates and times; teacher rows with lang `ja` use it. Japanese corpus builder `scripts/data/build_ja_corpus.py` (Japanese Wikipedia).
- **Pair data and evaluation tools:** Korean and Japanese code-switching templates and `scripts/data/build_mixed.py --lang zh|ko|ja` (replaces `build_zh_mixed.py`); `scripts/data/pair_train_list.py` joins several synthesis runs into one teacher list (optional audio-path column in `train.csv`, per-source hour caps); out-of-domain and mixed evaluation sets for zh, ko and ja with character-level CER (`--lang zh|ko|ja` in `render_teacher.py` and `eval_dir.py`).
- **Mandarin corpus builder** (`scripts/data/build_zh_corpus.py`): plain Simplified Chinese sentences from Chinese Wikipedia for the planned Chinese + English voice; synthesis with the `nu-10` voice has started.

### Changed
- **Direction:** vtts now targets bilingual voices (main language + English): Vietnamese, Chinese, Korean and Japanese first, then more pairs by ESP32 market. Single-language models are retired once the Vietnamese + English voices are released. See the [roadmap](docs/design/plans/2026-11-18-roadmap-bilingual.md).

### In progress
- Retraining the `nam-1` and `nu-10` teachers from random initialization on the synthetic audio only (the first teachers were warm-started from a model trained on another corpus), so the bilingual voices can be released under Apache-2.0.
- Chinese + English voice: front-end (pinyin, polyphones, number reading) and data.
- User pronunciation dictionary.

## v0.3.2 (2026-11-17)

Same model files; faster start of speech and a faster runtime on both chips.

### Changed
- Firmware: playback starts as soon as the next chunks are sure to be ready, based on each model's measured RTF, and a slower model streams in smaller chunks. ESP32-S3: M starts speaking after 0.40–0.43 s (was 1.2–1.3 s), S after 0.21–0.27 s. ESP32-P4: M after 0.23–0.27 s (was 0.74–0.90 s), S after 0.08–0.09 s.
- Runtime: register-tiled fp32 conv for the token and duration blocks (about 40% faster), lighter int8 epilogue; bit-exact. ESP32-S3 RTF: S 0.28 → 0.26, M 0.51 → 0.49; ESP32-P4: S 0.17 → 0.15, M 0.27 → 0.24.
- `prof` splits the vocoder into input conv, depthwise + LayerNorm, MLP (pw1, GELU + quantization, pw2), head and iSTFT.

## v0.3.1 (2026-11-17)

Same model files as v0.3.0; faster runtime, new board, front-end and documentation updates.

### Added
- **Bilingual Vietnamese + English front-end (Python):** token set v2 (v1 + English ARPAbet phonemes and stress, 107 tokens; v1 ids unchanged), CMU Pronouncing Dictionary lexicon, letter-to-sound rules learned from CMUdict for out-of-vocabulary words, English text normalization, and per-word language tagging (modes `vi`, `en`, `auto`).
- **Synthetic training data:** VoxCPM2 synthesis client and bilingual corpus builder (sentences chosen to cover rare Vietnamese syllables, English and code-switched text). About 98 h of speech per voice for `nam-1` (male) and `nu-10` (female).
- **Teacher:** bilingual training lists (`lang` column, token set v2), FLAC input resampled on load, warm-start from project checkpoints, a frame budget per batch for long utterances.
- **Website and documentation:** language dropdown with one table per language (model size and RTF per chip), shared content in `docs/site.json` synced into the READMEs, self-hosted fonts; English README with a multilingual voice catalog (Vietnamese translation in `README.vi.md`), [website](https://tuanpmt.github.io/vtts/) with on-chip audio samples, Hugging Face model repository with one folder per voice, runtime optimization research for ESP32-S3 and ESP32-P4, documentation index, runtime README, this changelog and contributing guide. All design documents and reports translated to English.
- **Pronunciation data per language:** Vietnamese tables moved from code to `src/vtts/frontend/lexicons/vi/*.tsv`, with a data test and [docs/frontend/pronunciation-rules.md](docs/frontend/pronunciation-rules.md) (layout, precedence, how to change a reading or add a language).
- **Runtime speedups (everything in PSRAM):** exact streaming with per-layer state; fused depthwise conv + LayerNorm + quantization and GELU + quantization; 64-frame MLP blocks; cached iSTFT window and two-core overlap-add. ESP32-P4: S 0.21–0.24 → 0.17, M 0.38–0.40 → 0.27. ESP32-S3: S 0.42–0.47 → 0.28, M 0.86–0.96 → 0.51, so the quality model is practical on the S3 too. Optional `vtts_set_fast_scratch()` for internal SRAM (off in the firmware). A correct fused `ld.ip` kernel for the S3 behind `vtts_s3_kernel`, with a `fusetest` command.
- **EchoEar 2.0** board support (`BOARD=echoear`).

### Changed
- Product codes (upper-case letters + digits such as ESP32, S3, U23, VN123) read their digits one by one: "ESP32-P4" → "e ét pê ba hai pê bốn" / "E S P three two P four" (Python and C).
- Vietnamese letter `s` reads "ét" (was "ét xì"); `smartphone` → "sờ mát phôn"; added `smarthome` → "sờ mát hôm".
- `firmware/esp32p4/` renamed to `firmware/esp32/` (it builds for both chips); `scripts/device/p4_say.py` renamed to `say.py`.

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
