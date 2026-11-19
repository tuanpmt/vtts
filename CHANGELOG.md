# Changelog

All notable changes to this project are documented here. Model files for each release are attached to [GitHub Releases](https://github.com/tuanpmt/vtts/releases) and mirrored on [Hugging Face](https://huggingface.co/tuanpm/vtts).

## Unreleased

### In progress
- Chinese + English and the other pairs: one designed VoxCPM2 voice per language, then data, teachers and students.
- User pronunciation dictionary.

## v0.4.0 (2026-11-19)

First bilingual release: two Vietnamese + English voices, `nam-1` (male) and `nu-10` (female), each as a quality model (M) and a lite model (S), all **Apache-2.0**. One voice reads Vietnamese, English and sentences that mix both ("Đã kết nối Bluetooth với AirPods"); the language is chosen per word on the chip. The teachers were trained from random initialization on speech synthesized with VoxCPM2 (Apache-2.0) from designed voices, about 98 h per voice, with no recorded corpus and no warm start from another model. Every released model is now bilingual (one main language + English); the Vietnamese-only prototype of v0.1–v0.3 is retired (its files stay on those GitHub releases).

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-vien-nam1-m-v0.4.q8.vtts` | `nam-1` (male) | Quality (M) | 1.83M | 2.6 MB |
| `vtts-vien-nam1-s-v0.4.q8.vtts` | `nam-1` (male) | Lite (S) | 0.82M | 1.2 MB |
| `vtts-vien-nu10-m-v0.4.q8.vtts` | `nu-10` (female) | Quality (M) | 1.83M | 2.6 MB |
| `vtts-vien-nu10-s-v0.4.q8.vtts` | `nu-10` (female) | Lite (S) | 0.82M | 1.2 MB |

Int8, token set `vi-en` (recorded in the file, format revision 1.1), 22.05 kHz.

### Quality

Three out-of-domain sets of 50 sentences (CER from PhoWhisper-large for Vietnamese, Whisper large-v3 for English and mixed; audio from the int8 C runtime). Report: [docs/reports/bilingual-student-eval.md](docs/reports/bilingual-student-eval.md).

| Model | Vietnamese CER | English CER | Mixed CER | UTMOS (vi / en / mixed) |
|---|---:|---:|---:|---|
| `nam-1` M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M | 0.014 | 0.008 | 0.015 | 2.72 / 3.44 / 2.70 |
| `nu-10` S | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

The earlier (warm-started) teachers scored CER 0.002–0.005 (vi), 0.012 (en) and 0.018–0.019 (mixed) with UTMOS 3.4–4.4; the first, unreleased `nam-1` M student 0.021 / 0.014 / 0.035 with UTMOS 2.40 / 3.23 / 2.49, so the clean `nam-1` M is as intelligible and slightly more natural.

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 (86-Panel, NANO) | 0.17–0.19 / 0.06–0.15 s | 0.25–0.27 / 0.17–0.34 s |
| ESP32-S3 (Touch-LCD-2.8, EchoEar 2.0) | 0.29–0.31 / 0.17–0.32 s | 0.50–0.52 / 0.31–0.61 s |

RTF from `bench` and `dump` (no playback), speech start from playing eight Vietnamese, English and mixed sentences; the same for both voices. Measured on an ESP32-P4-86-Panel-ETH-2RO and an ESP32-S3-Touch-LCD-2.8. The S model is larger than the old prototype S (0.82M vs 0.77M parameters), so S is a little slower than in v0.3.2. Details: [docs/reports/performance.md](docs/reports/performance.md).

### Flash a board

```bash
gh release download v0.4.0 -R tuanpmt/vtts -p '*.vtts' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-vien-nu10-s-v0.4.q8.vtts ../../models/vtts-vien-nu10-m-v0.4.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`; use the `nam1` files for the male voice. The firmware embeds the English lexicon (1.9 MB). With two vi-en models and only that lexicon the image is 6.35 MB on the ESP32-P4 (86-Panel, 2.03 MB free) and 6.24 MB on the ESP32-S3 (Touch-LCD-2.8, 2.15 MB free) in the 8 MB app partition; `build.sh` also builds and embeds the Chinese and Japanese blobs, which vi-en models do not use (about 0.85 MB more, still within the partition). On the console: `model s|m`, `lang vi|en|auto`.

### Added
- **Bilingual device front-end (C):** `vtts_text_to_ids_ex` with modes vi, en and auto (phoneme set v2): English normalization and G2P, per-word language tagging and chunk packing, exactly matching Python (2,018 fixture cases, 13,023 in a larger run, fuzz clean). The English lexicon and letter-to-sound rules ship as a 1.9 MB `VLEX` blob read in place (`scripts/frontend/build_lexicon.py`, `vtts_lex_*`).
- **Language modules** in Python (`src/vtts/frontend/languages.py`) and C (`LANGS`): a new language plugs in a normalizer, a word-to-token function and a tagging rule; see docs/frontend/pronunciation-rules.md.
- **Evaluation of bilingual teachers:** English and mixed out-of-domain sets, language-aware CER/WER, Whisper with a forced language; `nam-1` at 100k: CER 0.005 (vi), 0.015 (en), 0.033 (mixed).
- **Bilingual distillation:** v2 distill packs from a `{text, lang}` corpus, presets `M-vocos-p-bi`, `S-vocos-p-bi` and `M-vocos-p-bi-s3`, `run_bilingual_chain.sh`.
- Firmware command `ids ...` and `say.py --lang` to play token ids from a host front-end.
- **On-device bilingual text:** the firmware embeds the VLEX lexicon (read in place from flash) and uses the bilingual front-end for models with token set v2; `lang vi|en|auto` sets the mode. Same audio as the host front-end on ESP32-P4.
- `render_student_c.py --lang` renders bilingual models through the C runtime for evaluation.
- **Token set in the model file:** optional dim `token_set` (format revision 1.1: v1, vi-en, zh-en, ko-en, ja-en), written by `write_model` / `write_model_int8` and `export_student.py --token-set` (default: from the checkpoint or the vocab size), read with `vtts_token_set()` in C and `token_set_of()` in Python. Files without it map by vocab as before, and older runtimes ignore it.

### Added (front-ends for the next pairs; no released models yet)
- **Chinese front-end (Python):** token set `zh-en` (v2 ids 0–106 unchanged, Mandarin initials, finals and tones from id 107), `text_to_ids(text, "zh")` for Chinese with English words, readings from a default-per-character table plus a polyphone phrase table generated from pypinyin (`scripts/frontend/build_zh_lexicon.py`), Chinese number, date, time and percentage reading; teacher rows with lang `zh` use it.
- **Chinese device front-end (C):** mode `VTTS_LANG_ZH` of `vtts_text_to_ids_ex` (token set zh-en) with Chinese normalization, forward-maximum-matching readings and English words, exactly matching `text_to_ids(text, "zh")` (9,397 fixture cases, 78,017 in a larger run, fuzz clean). The reading tables ship as a 116 KB `ZLEX` blob read in place (`scripts/frontend/build_zh_blob.py`, `vtts_zlex_*`); the text workspace grows by 2 KB. `make -C runtime test` runs all text front-end tests.
- **Chinese on the device:** the firmware picks the text front-end from each model's token set instead of its vocab size, embeds the 116 KB ZLEX blob next to the English lexicon (`build.sh` builds `main/lex_zh.bin`), and accepts `lang zh` for zh-en models (`lang` refuses modes of other token sets; ko-en and ja-en models take `ids` only). `bench` uses Mandarin sentences for zh-en models. Host tool `vtts_say` runs the same text → ids → audio path on a PC.
- **Korean device front-end (C):** mode `VTTS_LANG_KO` of `vtts_text_to_ids_ex` (token set ko-en) with Korean normalization (Sino-Korean and native numbers with counters, dates with 유월/시월, times, decimals, percent, ranges, phone numbers, money, units, product codes in English), the exception table and the ordered pronunciation rules, exactly matching `text_to_ids(text, "ko")` (11,369 fixture cases, 126,277 in a larger run, fuzz clean). The tables are generated into `vtts_text_tables.h` (about 4 KB, no blob); the text workspace grows by 2 KB. The firmware accepts `lang ko` (default for ko-en models), `bench` has Korean sentences, and `vtts_say` runs ko-en models.
- **Hindi device front-end (C):** mode `VTTS_LANG_HI` of `vtts_text_to_ids_ex` (token set hi-en, model header code 10) with Hindi normalization (numbers 0–99 from the table with sau, hazaar, lakh and crore, decimals, dates, years, times with बजे, rupees and paise, percent, units, ordinals, ranges, phone numbers, product codes, Devanagari digits, the danda as a sentence end), the Devanagari letter, anusvara and schwa-deletion rules and the exception table, exactly matching `text_to_ids(text, "hi")` (10,951 fixture cases, 143,285 more in larger random runs, fuzz clean). The tables are generated into `vtts_text_tables.h` (no blob); the runtime knows token set hi-en (`VTTS_TOKSET_HI_EN`). The firmware accepts `lang hi` (default for hi-en models), `bench` has Hindi sentences, and `vtts_say` runs hi-en models; the front-end adds about 25 KB to the ESP32-P4 image.
- **Japanese device front-end (C):** mode `VTTS_LANG_JA` of `vtts_text_to_ids_ex` (token set ja-en) with Japanese normalization (NFKC, numbers with counters and their sound changes, 万/億/兆, dates, times, money, percent, ranges, phone numbers, units, product codes in English), forward-longest-match readings with the context tables, kanji defaults and 々, kana to phonemes and English words, exactly matching `text_to_ids(text, "ja")` (12,238 fixture cases, 322,134 in a larger run, fuzz clean). The reading tables and the NFKC data ship as a 721 KB `JLEX` blob read in place (`scripts/frontend/build_ja_blob.py`, `vtts_jlex_*`; about 150 ns per lookup on the host); the text workspace is unchanged. The firmware embeds it (`build.sh` builds `main/lex_ja.bin`) and accepts `lang ja` (default for ja-en models), `bench` has Japanese sentences, and `vtts_say --ja` runs ja-en models.
- **Korean front-end (Python):** token set `ko-en` (v2 ids 0–106 unchanged, 46 Korean onset, vowel and coda tokens from id 107), `text_to_ids(text, "ko")` for Korean with English words: Hangul decomposition, the standard pronunciation rules (liaison, neutralization, nasalization, liquidization, aspiration, tensification, palatalization) as an ordered rule table plus an exception table, Sino-Korean and native number reading with counters, dates, times and units; teacher rows with lang `ko` use it. Korean corpus builder `scripts/data/build_ko_corpus.py` (Korean Wikipedia).
- **Japanese front-end (Python):** token set `ja-en` (v2 ids 0–106 unchanged, 37 Japanese phonemes in the style of Open JTalk from id 107; long vowels as repeated vowels, `N` and `cl` as tokens), `text_to_ids(text, "ja")` for Japanese with English words: kana rules, kanji readings by longest match over word, context (after kanji / katakana) and per-kanji tables generated from Open JTalk's dictionary with pyopenjtalk (60,000 entries, 1.3 MB TSV; 98.2% mora agreement with pyopenjtalk on held-out Wikipedia sentences), Japanese numbers with counters and sound changes, dates and times; teacher rows with lang `ja` use it. Japanese corpus builder `scripts/data/build_ja_corpus.py` (Japanese Wikipedia).
- **Spanish front-end (Python):** token set `es-en` (code 6; v2 ids 0–106 unchanged, 31 Spanish tokens from id 107: 5 vowels, the same vowels stressed, glides j/w, 19 consonants; vocabulary 138), `text_to_ids(text, "es")` for Spanish with English words: spelling rules (c/z, g/j, qu/gu, ll/y, r/rr, x, silent h), diphthongs and hiatus, stress from the written accent or the default rules, unstressed function words, an exception table; Spanish numbers (apocope un/veintiún), ordinals, dates, times, money, percentages, units, phone numbers, product codes and acronyms. Code-switching for Latin-script pairs (`frontend/latin.py`): own letters, word lists (`lexicons/es/native.txt`, `lexicons/latin/english.txt`), CamelCase, acronyms, then a Spanish spelling check. Eval sets `ood_es` and `mixed_es`; teacher rows, distill packs, presets and CER with lang `es`.
- **Indonesian front-end (Python):** token set `id-en` (code 7; 34 Indonesian tokens from id 107: six vowels with the schwa `@` and the e of "enak", five stressed vowels, 23 consonants with the glottal stop `?`; vocabulary 141), `text_to_ids(text, "id")` for Indonesian with English words: digraphs ng/ny/sy/kh, final k and apostrophe as a glottal stop, final diphthongs, the two e's by default rules plus an exception table that also covers affixed forms (`lexicons/id/overrides.tsv`, 94 entries), penultimate stress moving off the schwa; Indonesian numbers (sebelas, seratus, seribu, juta), ordinals (ke-3), dates, times (pukul 14.30), rupiah, percentages, units, phone numbers, reduplication (anak2), product codes and acronyms. Code-switching by the Latin-script rules with `lexicons/id/native.txt`. Eval sets `ood_id` and `mixed_id`.
- **Brazilian Portuguese front-end (Python):** token set `pt-en` (code 8; 43 Portuguese tokens from id 107: oral and nasal vowels, stressed vowels with open `E`/`O`, glides j/w, 19 consonants with the tap `r` and the strong `rr`; vocabulary 150), `text_to_ids(text, "pt")` for Portuguese with English words: spelling rules (c/ç, g/j, qu/gu, ch/lh/nh, r/rr, s/z between vowels, x by position), nasal vowels and nasal diphthongs (ão, ãe, õe, -am, -em), falling diphthongs, stress from accents or the default rules, open/closed e/o (accents, -el/-ol, -ela, -osa, exception table), final unstressed e/o read i/u; `lexicons/pt/overrides.tsv` (99 entries). Portuguese numbers (mil e duzentos, dois mil e vinte e seis), ordinals, dates (primeiro de maio), times (14h30), reais with centavos, percentages, units, phone numbers, product codes, acronyms and chat abbreviations (vc, pq). Eval sets `ood_pt` and `mixed_pt`. Latin-script tagging: units and abbreviations of a language's normalizer (kWh, etc) and single letters belong to the language; Latin-script pairs fold other letters with NFKD (º, ª).
- **Spanish, Indonesian and Portuguese device front-ends (C):** modes `VTTS_LANG_ES`, `VTTS_LANG_ID`, `VTTS_LANG_PT` of `vtts_text_to_ids_ex` (token sets es-en, id-en, pt-en, header codes 6–8) with the Latin-script tagging rules, the three normalizers pass by pass (abbreviations, dates, times, phone numbers, money, percent, units, ordinals, ranges, product codes, numbers, reduplication, acronyms), the spelling, stress, nasal and vowel-quality rules and the exception tables, exactly matching `text_to_ids(text, "es" | "id" | "pt")` (11,896 / 11,870 / 11,872 fixture cases; 205,614 in a larger run and 120,000 character-level random strings, all exact; fuzz clean). All tables, including Python's `\w`, `\d`, `isspace` and `lower` classes, are generated into `vtts_text_tables.h` (no blob, about 62 KB of code and tables in the ESP32-P4 firmware); the text workspace is unchanged. The C runtime knows the token sets es-en, id-en and pt-en (they loaded as `unknown` before); the firmware defaults to `es`, `id`, `pt` for these models, `lang es|id|pt` works and `bench` has sentences in each language. C whitespace now matches Python's `str.isspace()` in every mode (U+001C–U+001F, U+0085).
- **Hindi front-end (Python):** token set `hi-en` (code 10; 50 Hindi tokens from id 107: 10 vowels, a nasalization mark `~`, 39 consonants with retroflex, aspirated, flap and nukta consonants; vocabulary 157), `text_to_ids(text, "hi")` for Hindi with English words: Devanagari letters, matras, conjuncts with virama, nukta consonants, anusvara as a homorganic nasal or nasalization, chandrabindu, visarga; schwa deletion (word-final and the medial VC_CV rule, right to left) with `lexicons/hi/overrides.tsv` (27 entries); Hindi numbers from a 0-99 table (`lexicons/hi/numbers.tsv`) with सौ, हज़ार, लाख, करोड़, decimals (दशमलव), dates, times (बजे / बजकर), years (उन्नीस सौ सैंतालीस), rupees with paise, percentages, units, phone numbers, ordinals (10वीं), product codes, Devanagari digits, the danda । and ॥ as sentence ends. Latin words are English; teacher rows, distill packs, presets, the unreadable filter and CER with lang `hi`.
- **Thai front-end (Python):** token set `th-en` (code 9; 55 Thai tokens from id 107: 21 initials with the glottal stop `?`, 21 vowels (nine short/long pairs and the diphthongs ia, uea, ua), 8 finals (k p t m n ng w j), 5 tones; vocabulary 162), `text_to_ids(text, "th")` for Thai with English words: word segmentation over a 16,377-word list made from PyThaiNLP's CC0 word list (`lexicons/th/words.txt`, `scripts/frontend/build_th_lexicon.py`), syllables by a cost-based split over the spelling patterns (preposed vowels, clusters, silent ร, ห and leading consonants, unwritten o/a, ์, ฤ, linking finals ฐ ษ ศ ธ), tones from consonant class, tone mark and live/dead syllables, `lexicons/th/overrides.tsv` (116 respellings), ๆ and ฯ; Thai numbers (เอ็ด, ยี่สิบ, ล้าน), Thai digits, dates, times (14.30 น.), money, percentages, units, phone numbers; spaces between Thai runs read as pauses. 90.4% syllable agreement and 99.4% tone agreement with TLTK's g2p (PyThaiNLP `tltk_g2p`) on 1,193 held-out Wikipedia sentences (`scripts/frontend/eval_th_g2p.py`). Eval sets `ood_th` and `mixed_th`; teacher rows, distill packs, presets, CER with lang `th`.
- **Thai device front-end (C):** mode `VTTS_LANG_TH` of `vtts_text_to_ids_ex` (token set th-en, code 9; vocab 162 maps to it too) with Thai normalization (Thai digits, abbreviations, numbers, dates, times with น., money, percent, units, phone numbers, product codes, pauses between Thai runs), word segmentation over the word list, the lowest-cost syllable split, silent letters, linking finals, leading consonants, respellings and tones, exactly matching `text_to_ids(text, "th")` (12,997 fixture cases with both Thai eval sets and the Thai unit-test strings, 70,000 more in a larger run, fuzz clean). `gen_text_tables.py` writes the tables into `vtts_text_th_tables.h` (no blob): the 16,493 words front coded in 68 KB plus a 4 KB block index, about 80 KB in all; the text workspace does not grow. A dot after a Thai letter no longer ends a sentence in any mode (as in Python). The firmware accepts `lang th` (default for th-en models), `bench` has Thai sentences, and `vtts_say` runs th-en models.
- **Pair data and evaluation tools:** Korean and Japanese code-switching templates and `scripts/data/build_mixed.py --lang zh|ko|ja` (replaces `build_zh_mixed.py`); `scripts/data/pair_train_list.py` joins several synthesis runs into one teacher list (optional audio-path column in `train.csv`, per-source hour caps); out-of-domain and mixed evaluation sets for zh, ko and ja with character-level CER (`--lang zh|ko|ja` in `render_teacher.py` and `eval_dir.py`).
- **Mandarin corpus builder** (`scripts/data/build_zh_corpus.py`): plain Simplified Chinese sentences from Chinese Wikipedia for the planned Chinese + English voice.

### Changed
- **Direction:** vtts now targets bilingual voices (main language + English): Vietnamese, Chinese, Korean and Japanese first, then more pairs by ESP32 market. Single-language models are retired once the Vietnamese + English voices are released. See the [roadmap](docs/design/plans/2026-11-18-roadmap-bilingual.md).
- Docs, website and Hugging Face card list only the bilingual voices; all audio samples are the ESP32-P4's own output from the v0.4.0 models.

### Known issues
- ESP32-S3, model M with two cores (the default): the output is not deterministic and some sentences contain short bursts a few frames long; `cores 1` avoids it at the cost of speed. S on the S3 and both models on the ESP32-P4 are not affected. See [docs/reports/performance.md](docs/reports/performance.md#chip-output-against-the-pc-runtime).
- A very short first sentence followed by a long one ("Hello! I am ...") can cause one playback underrun (a short gap).

### Removed
- The Vietnamese prototype (S-vocos v0.1, M-vocos v0.2, CC BY-NC 4.0) from the voice catalog, website samples and Hugging Face card. The firmware and runtime still read its v1 files for one more release.

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
