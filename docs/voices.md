# Voices

Every vtts model except the English-only voice `nu-en` is **bilingual: one main language + English**, with code-switching. One voice reads single-language sentences and mixed sentences such as "Đã kết nối Bluetooth với AirPods", "스마트폰을 Wi-Fi에 연결했어요" or "このWi-Fiはpasswordが必要ですか？"; the front-end picks the language per word. The English front-end runs on the device too (C, parity-tested against Python), so mixed text is handled on the chip.

Each voice comes as a quality model (M) and a lite model (S, about 1.5× faster, with less CPU load and flash). Both run faster than real time on the ESP32-P4 and the ESP32-S3; pick by sound versus headroom, not by chip.

## Catalog

<!-- BEGIN:voices -->
| Voice | Languages | Quality model (M) | Lite model (S) | Status |
|---|---|---|---|---|
| `nu-en` (female) | 🇬🇧 en | M (1.83M params, 2.6 MB) | S (0.82M params, 1.2 MB) | **Released in v0.9.0, M and S updated in v0.10.1 (Apache-2.0)** |
| `nam-1` (male) | 🇻🇳 vi + 🇬🇧 en, code-switching | M (1.83M params, 2.6 MB) | S (0.82M params, 1.2 MB) | **Released in v0.4.0 (Apache-2.0)** |
| `nu-10` (female) | 🇻🇳 vi + 🇬🇧 en, code-switching | M (1.83M params, 2.6 MB) | S (0.82M params, 1.2 MB) | **Released in v0.4.0, M updated in v0.9.1 (Apache-2.0)** |
| `nu-ko` (female) | 🇰🇷 ko + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.5.0 (Apache-2.0)** |
| `nu-zh` (female) | 🇨🇳 zh + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.5.0 (Apache-2.0)** |
| `nu-ja` (female) | 🇯🇵 ja + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.6.0 (Apache-2.0)** |
| `nu-pt` (female) | 🇧🇷 pt + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.7.0 (Apache-2.0)** |
| `nu-id` (female) | 🇮🇩 id + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.8.0 (Apache-2.0)** |
| `nu-hi` (female) | 🇮🇳 hi + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.8.0 (Apache-2.0)** |
| `nu-es` (female) | 🇪🇸 es + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.8.0 (Apache-2.0)** |
| `nu-th` (female) | 🇹🇭 th + 🇬🇧 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.10.0 (Apache-2.0)** |
| Dutch + English | 🇳🇱 nl + 🇬🇧 en, code-switching | M | S | Planned |
| Swedish + English | 🇸🇪 sv + 🇬🇧 en, code-switching | M | S | Planned |
| Norwegian + English | 🇳🇴 no + 🇬🇧 en, code-switching | M | S | Planned |
<!-- END:voices -->

Model files are attached to [GitHub Releases](https://github.com/tuanpmt/vtts/releases) and mirrored on [Hugging Face](https://huggingface.co/tuanpm/vtts), one folder per voice (`en-nu-en/`, `vi-en-nam-1/`, `vi-en-nu-10/`, `ko-en-nu-ko/`, `zh-en-nu-zh/`, `ja-en-nu-ja/`, `pt-en-nu-pt/`, `id-en-nu-id/`, `hi-en-nu-hi/`, `es-en-nu-es/`, `th-en-nu-th/`):

| Voice | Files (lite S, quality M) | Release | Notes |
|---|---|---|---|
| `nu-en` | `vtts-en-nuen-{s,m}-v0.9.q8.vtts` | v0.9.0 | English only. Token set vi-en; the files record the text mode `en` (dim `text_mode`), so the firmware and `vtts_say` start in English; use only `lang en` |
| `nu-en` update | `vtts-en-nuen-{s,m}-v0.10.1.q8.vtts` | v0.10.1 | Replace the v0.9.0 `nu-en` M and S (longer joint distillation stage, UTMOS +0.6–0.7); same size, speed and start mode `en` |
| `nam-1`, `nu-10` | `vtts-vien-{nam1,nu10}-{s,m}-v0.4.q8.vtts` | v0.4.0 | Text modes `vi`, `en`, `auto` |
| `nu-10` M update | `vtts-vien-nu10-m-v0.9.1.q8.vtts` | v0.9.1 | Replaces the v0.4.0 `nu-10` M (longer joint distillation stage, UTMOS +0.4); same size, speed and text modes; use it with the v0.4.0 S |
| `nu-ko` | `vtts-koen-nuko-{s,m}-v0.5.q8.vtts` | v0.5.0 | Text mode `ko`; no blob beyond the English lexicon |
| `nu-zh` | `vtts-zhen-nuzh-{s,m}-v0.5.q8.vtts` | v0.5.0 | Text mode `zh`; embeds the 116 KB `ZLEX` blob (`main/lex_zh.bin`) |
| `nu-ja` | `vtts-jaen-nuja-{s,m}-v0.6.q8.vtts` | v0.6.0 | Text mode `ja`; embeds the 721 KB `JLEX` blob (`main/lex_ja.bin`) |
| `nu-pt` | `vtts-pten-nupt-{s,m}-v0.7.q8.vtts` | v0.7.0 | Text mode `pt`; no blob beyond the English lexicon |
| `nu-id` | `vtts-iden-nuid-{s,m}-v0.8.q8.vtts` | v0.8.0 | Text mode `id`; no blob beyond the English lexicon |
| `nu-hi` | `vtts-hien-nuhi-{s,m}-v0.8.q8.vtts` | v0.8.0 | Text mode `hi` (Devanagari, English in Latin letters); no blob beyond the English lexicon |
| `nu-es` | `vtts-esen-nues-{s,m}-v0.8.q8.vtts` | v0.8.0 | Text mode `es`; no blob beyond the English lexicon |
| `nu-th` | `vtts-then-nuth-{s,m}-v0.10.q8.vtts` | v0.10.0 | Text mode `th` (Thai script, English in Latin letters); no blob beyond the English lexicon (the Thai tables are compiled in) |

`build.sh` builds and embeds the blobs a model needs. In the single-mode pairs (ko, zh, ja, pt, id, hi, es, th) English words and English sentences go through the English front-end. In the Latin-script pairs (pt, id, es) a whole English sentence is read in English, numbers included; otherwise digits are read in the main language.

## Quality

Three out-of-domain sets of 50 sentences per language pair (main language, English, mixed; device prompts, numbers, names, questions, long sentences), none of them in the training text. CER is the character error rate when an ASR model transcribes the audio: PhoWhisper-large for Vietnamese (tones included), Whisper large-v3 for English and the other languages. UTMOS predicts naturalness. Audio comes from the int8 C runtime, which gives the same output as the chip.

**English** (`nu-en`, English only, [report](reports/en-student-eval.md)): `ood_en` and the new `ood_en2` (numbers, dates and times, short commands, units and money, abbreviations), against the English of the bilingual `nu-10` voice and the VoxCPM2 `nu-en` voice it was trained from:

| Model | Params | `ood_en` CER ↓ | `ood_en2` CER ↓ | UTMOS ↑ (ood_en / ood_en2) |
|---|---:|---:|---:|---|
| `nu-en` M (v0.10.1) | 1.83M | 0.012 | 0.024 | 3.56 / 3.56 |
| `nu-en` S (v0.10.1) | 0.82M | 0.015 | **0.021** | **3.68 / 3.67** |
| `nu-en` M (v0.9.0) | 1.83M | 0.014 | 0.034 | 2.88 / 3.00 |
| `nu-en` S (v0.9.0) | 0.82M | 0.015 | 0.027 | 3.00 / 3.08 |
| `nu-10` M v0.4.0 (vi-en, `lang en`) | 1.83M | **0.008** | 0.033 | 3.44 / 3.59 |
| `nu-10` S v0.4.0 (vi-en, `lang en`) | 0.82M | 0.011 | 0.035 | 3.26 / 3.35 |
| VoxCPM2 `nu-en` (reference voice) | — | 0.010 | 0.045 | 4.24 / 4.24 |

Most of the remaining CER is how Whisper writes times ("9:30" as "9.30") and spaced digits; intelligibility is at the level of the reference voice. The models of v0.10.1 come from the improved distillation recipe (joint stage 80k steps instead of 20k): UTMOS +0.6–0.7 at the same or lower CER, above the English of the v0.4.0 `nu-10` M and about 0.6 below the reference voice ([report](reports/en-student-eval.md#nu-en-update-v0101)).

**Vietnamese + English** ([report](reports/bilingual-student-eval.md)):

| Model | Params | Vietnamese CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (vi / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nam-1` M | 1.83M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.82M | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M (v0.9.1) | 1.83M | **0.014** | **0.008** | **0.015** | **3.11 / 3.87 / 3.12** |
| `nu-10` M (v0.4.0) | 1.83M | **0.014** | **0.008** | **0.015** | 2.72 / 3.44 / 2.70 |
| `nu-10` S | 0.82M | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

Most remaining errors are numbers written differently by the ASR ("9:30" as "9.30") and brand names inside Vietnamese sentences. The `nu-10` M of v0.9.1 comes from the improved distillation recipe (joint stage 80k steps instead of 20k): same intelligibility, UTMOS +0.4 on all three sets ([report](reports/bilingual-student-eval.md#nu-10-m-update-v091)).

**Korean + English** ([report](reports/ko-student-eval.md); Korean CER counts Hangul syllables):

| Model | Params | Korean CER ↓ | English CER ↓ | Mixed CER ↓ (Hangul only) | UTMOS ↑ (ko / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-ko` M | 1.84M | **0.021** | 0.023 | **0.024** | **2.75 / 3.39 / 2.75** |
| `nu-ko` S | 0.83M | 0.045 | 0.023 | 0.055 | 2.68 / 3.18 / 2.65 |
| VoxCPM2 `nu-ko` (reference voice) | — | — | — | 0.016 | — / — / 3.92 |

Whisper writes most English words in Hangul ("Google Drive" → 구글 드라이브), so the plain CER of the mixed Korean set is 0.30–0.37 for every system, the reference voice included; the mixed column counts only the errors on the Korean characters.

**Chinese + English** ([report](reports/zh-student-eval.md); Mandarin CER counts Han characters):

| Model | Params | Mandarin CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (zh / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-zh` M | 1.84M | **0.020** | **0.021** | 0.047 | **3.16 / 3.64 / 3.23** |
| `nu-zh` S | 0.83M | 0.042 | 0.034 | **0.032** | 2.89 / 3.35 / 2.96 |

Whisper sometimes writes an English word of a mixed sentence in Chinese characters (Samsung → 三星), so the mixed CER is an upper bound.

**Japanese + English** ([report](reports/ja-student-eval.md); Japanese CER on readings, both sides converted to kana):

| Model | Params | Japanese CER ↓ (reading) | English CER ↓ | Mixed CER ↓ (kana and kanji only) | UTMOS ↑ (ja / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-ja` M | 1.84M | **0.050** | 0.023 | 0.054 | **2.57 / 3.22 / 2.61** |
| `nu-ja` S | 0.83M | 0.053 | **0.019** | **0.049** | 2.30 / 2.76 / 2.28 |
| VoxCPM2 `nu-ja` (reference voice) | — | 0.023 | — | 0.049 | 3.45 / — / 3.43 |

The Japanese references write some numbers in kanji (十五分) and Whisper writes digits, so the orthographic CER (0.097 M, 0.110 S, 0.064 for the reference voice) counts spelling, not speech; the reading CER compares kana readings and is counted in kana. On the mixed set Whisper writes most English words in katakana (password → パスワード), so the plain CER is 0.20–0.24 for every system. The main remaining error is a weak word-initial *r* (リビング heard as イビング).

**Portuguese (Brazil) + English** ([report](reports/pt-student-eval.md)):

| Model | Params | Portuguese CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (pt / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-pt` M | 1.84M | **0.008** | 0.089 | 0.026 | 2.36 / **2.71** / 2.54 |
| `nu-pt` S | 0.83M | 0.019 | **0.080** | **0.022** | **2.63** / 2.69 / **2.69** |
| VoxCPM2 `nu-pt` (reference voice) | — | 0.044 | — | 0.044 | 3.99 / — / 3.93 |

The reference voice reads raw digits poorly ("R$ 1.250,00", "15h45"); without the numbers group it scores 0.001 (Portuguese) and 0.016 (mixed), M 0.005 and 0.027, S 0.013 and 0.023. The English CER is about four times that of the other pairs because the pt mode tags each Latin word by spelling, and 17% of the words of whole English sentences (I, a, an, time, temperature, minutes) fit Portuguese spelling and are read as Portuguese; Portuguese sentences with English words are not affected. Since v0.8.0 the runtime and firmware decide the language of each sentence first, and the same v0.7.0 models score 0.012 (M) and 0.014 (S) on English ([report](reports/pt-student-eval.md#english-sentences-in-the-pt-mode)).

**Indonesian + English** ([report](reports/id-student-eval.md)):

| Model | Params | Indonesian CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (id / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-id` M | 1.84M | **0.011** | **0.022** | 0.018 | **2.42 / 3.05 / 2.57** |
| `nu-id` S | 0.83M | **0.011** | 0.059 | **0.015** | 2.14 / 2.63 / 2.25 |
| VoxCPM2 `nu-id` (reference voice) | — | 0.023 | — | 0.042 | 3.07 / — / 3.22 |

Without the numbers group: reference 0.000 / 0.009, M 0.002 / 0.018, S 0.003 / 0.014 (Indonesian / mixed); the reference voice misreads raw digits ("Rp1.250.000"). English sentences are read in English by the sentence-level decision (word tags alone: 0.070 M, 0.106 S); the S score is raised by two clips that Whisper, forced to English, wrote as Indonesian translations of the accented audio.

**Hindi + English** ([report](reports/hi-student-eval.md)):

| Model | Params | Hindi CER ↓ | English CER ↓ | Mixed CER (Devanagari only) ↓ | UTMOS ↑ (hi / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-hi` M | 1.84M | 0.094 | 0.053 | **0.054** | **2.84 / 3.09 / 2.91** |
| `nu-hi` S | 0.83M | **0.092** | **0.028** | 0.056 | **2.84** / 3.03 / 2.88 |
| VoxCPM2 `nu-hi` (reference voice) | — | 0.069 | — | 0.065 | 3.41 / — / 3.55 |

Whisper's Hindi spelling (nukta, chandrabindu, ये/ए) costs every system; merged, and without the numbers group, `ood_hi` scores 0.035 for the reference voice, 0.081 (M) and 0.085 (S). The main remaining error is a weak first consonant at the start of a sentence ("बैठक" heard as "वैटक"). Whisper writes the English words of Hinglish sentences in Devanagari, so the mixed CER counts only the Devanagari of the text (plain CER 0.28–0.29 for every system, the reference included).

**Spanish + English** ([report](reports/es-student-eval.md)):

| Model | Params | Spanish CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (es / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-es` M | 1.84M | 0.019 | 0.020 | **0.006** | **2.83 / 3.07 / 2.87** |
| `nu-es` S | 0.83M | **0.017** | **0.019** | 0.009 | 2.54 / 2.81 / 2.50 |
| VoxCPM2 `nu-es` (reference voice) | — | 0.020 | — | 0.037 | 3.50 / — / 3.57 |

Without the numbers group: reference 0.000 / 0.005, M 0.008 / 0.005, S 0.006 / 0.010 (Spanish / mixed). English sentences are read in English by the sentence-level decision (word tags alone: 0.056 M, 0.064 S).

**Thai + English** ([report](reports/th-student-eval.md)):

| Model | Params | Thai CER ↓ | English CER ↓ | Mixed CER (Thai only) ↓ | UTMOS ↑ (th / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-th` M | 1.84M | **0.044** | **0.018** | **0.043** | **2.88 / 3.51 / 2.95** |
| `nu-th` S | 0.83M | 0.053 | 0.030 | 0.044 | 2.55 / 3.06 / 2.58 |
| VoxCPM2 `nu-th` (reference voice) | — | 0.076 | — | 0.022 | 3.97 / — / 4.00 |

Thai is written without spaces between words, so the CER counts Thai characters with spaces removed. Without the numbers group (the reference voice misreads raw digits and sometimes adds words at the end): reference 0.039, M 0.054, S 0.050. Whisper writes most English words of a Thai sentence in Thai script (Liverpool → ลิเวอร์พูล), so the mixed CER counts only the Thai characters of the text (plain CER 0.100 M, 0.116 S, 0.086 reference).

## Speed

<!-- BEGIN:hardware -->
| Board | Chip | Lite model RTF | Quality model RTF |
|---|---|---|---|
| Waveshare ESP32-P4-86-Panel-ETH-2RO, ESP32-P4-NANO | ESP32-P4, 360 MHz, PIE SIMD | 0.17–0.19 | 0.26–0.28 |
| EchoEar 2.0, Waveshare ESP32-S3-Touch-LCD-2.8 | ESP32-S3, 240 MHz, 8 MB PSRAM | 0.31–0.32 | 0.55–0.58 |

Both models run on both chips. RTF below 1 means faster than real time.
<!-- END:hardware -->

Both chips use two cores and int8 SIMD kernels; all released pairs run at the same speed within about 0.02 RTF. Audio generated on the ESP32-P4 matches the C runtime on a PC. The ESP32-S3 needs at least 8 MB of PSRAM. Details, speech start, CPU load and memory: [reports/performance.md](reports/performance.md).

## Listen (generated on an ESP32-P4)

Audio is produced on the chip with the firmware's `dump` command (`lang en` for `nu-en`, `lang auto` for vi-en, `lang ko`, `lang zh`, `lang ja`, `lang pt`, `lang id`, `lang hi`, `lang es`, `lang th` for the other pairs), sent to a PC over serial and only compressed to MP3; every clip was checked with ASR before publishing. The same clips are on the [website](https://tuanpmt.github.io/vtts/).

<!-- BEGIN:samples -->
🇬🇧 **English**

| Sentence | nu-en Quality | nu-en Lite |
|---|---|---|
| Hello! I am a text-to-speech voice running entirely on the ESP32 microcontroller, with no internet connection. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-intro.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-intro.mp3) |
| Okay, I have turned off the living room lights and locked the front door. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-lights.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-lights.mp3) |
| The thermostat is now set to 22 degrees, and the fan will run on low speed. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-thermostat.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-thermostat.mp3) |
| Your battery is at 15 percent, and the total comes to $42.50. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-numbers.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-numbers.mp3) |
| Your dentist appointment is on Tuesday, November 18, at 9:30 in the morning. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-dates.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-dates.mp3) |
| It is 6:45 p.m. Dinner will be ready in about 20 minutes. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-time.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-time.mp3) |
| Would you like me to play some music in the kitchen? | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-question.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-question.mp3) |
| Heavy rain is expected across the city tonight, so the morning commute may take longer than usual, and several bus routes will start later. | [▶ nu-en Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-m-news.mp3) | [▶ nu-en Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuen-s-news.mp3) |

🇻🇳 🇬🇧 **Việt–English**

| Sentence | nam-1 Quality | nam-1 Lite | nu-10 Quality | nu-10 Lite |
|---|---|---|---|---|
| Xin chào, tôi là giọng đọc tiếng Việt và tiếng Anh chạy hoàn toàn trên chip ESP32. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-intro.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-intro.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-intro.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-intro.mp3) |
| Đã kết nối Bluetooth với AirPods, bạn có thể mở Spotify hoặc YouTube Music. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-bluetooth.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-bluetooth.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-bluetooth.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-bluetooth.mp3) |
| Cuộc họp trên Google Meet sẽ bắt đầu lúc 9 giờ, nhớ chuẩn bị file PowerPoint nhé. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-meeting.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-meeting.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-meeting.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-meeting.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on an ESP32 microcontroller. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-en-intro.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-en-intro.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-en-intro.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-en-intro.mp3) |
| Your package will arrive on Tuesday, November 18, between 2 and 4 p.m. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-en-package.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-en-package.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-en-package.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-en-package.mp3) |
| Mưa kéo dài hơn hai giờ khiến nhiều đường ở Long Thành, Nhơn Trạch ngập gần nửa mét, xe chết máy, người dân phải dắt bộ, sáng 15/11. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-news.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-news.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-news.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-news.mp3) |
| Pin còn 15%, nhiệt độ phòng là 28°C. Báo thức đã được đặt lúc 6 giờ 30 sáng mai. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-numbers.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-numbers.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-numbers.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-numbers.mp3) |
| Bạn có muốn bật đèn phòng khách không? | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-question.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-question.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-question.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-question.mp3) |

🇰🇷 🇬🇧 **한국어–English**

| Sentence | nu-ko Quality | nu-ko Lite |
|---|---|---|
| 안녕하세요, 저는 ESP32 칩에서 완전히 실행되는 한국어와 영어 음성입니다. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-intro.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-intro.mp3) |
| 오늘 오후 3시에 Zoom 회의가 있어요. PowerPoint 파일을 미리 보내 주세요. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-zoom.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-zoom.mp3) |
| 스마트폰을 Wi-Fi에 연결했어요. 이제 Netflix를 볼 수 있어요. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-wifi.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-wifi.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on an ESP32 microcontroller. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-en-intro.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-en-package.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-en-package.mp3) |
| 서울은 오늘 오후부터 비가 내리고, 내일 아침 기온은 영하 3도까지 떨어지겠습니다. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-news.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-news.mp3) |
| 배터리가 15% 남았고, 실내 온도는 28도입니다. 알람은 내일 아침 6시 30분에 맞춰져 있어요. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-numbers.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-numbers.mp3) |
| 거실 불을 켜 드릴까요? | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-question.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-question.mp3) |

🇨🇳 🇬🇧 **中文–English**

| Sentence | nu-zh Quality | nu-zh Lite |
|---|---|---|
| 你好，我是完全运行在ESP32芯片上的中文和英文语音。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-intro.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-intro.mp3) |
| 已经通过Bluetooth连接到AirPods，你可以打开Spotify或者YouTube Music。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-bluetooth.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-bluetooth.mp3) |
| 下午三点有一个Zoom会议，请提前把PowerPoint文件发给我。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-meeting.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-meeting.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on a tiny microcontroller. | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-en-intro.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-en-package.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-en-package.mp3) |
| 北京今天下午有小雨，明天早上最低气温零下三度，出门请注意保暖。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-news.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-news.mp3) |
| 电池还剩15%，室内温度是28度。闹钟已经设在明天早上6点30分。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-numbers.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-numbers.mp3) |
| 要帮你打开客厅的灯吗？ | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-question.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-question.mp3) |

🇯🇵 🇬🇧 **日本語–English**

| Sentence | nu-ja Quality | nu-ja Lite |
|---|---|---|
| こんにちは。私はESP32チップの上だけで動く、日本語と英語の音声です。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-intro.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-intro.mp3) |
| 今日の午後3時からZoomの会議があります。PowerPointのファイルを先に送ってください。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-zoom.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-zoom.mp3) |
| スマートフォンをWi-Fiに接続しました。これでNetflixが見られます。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-wifi.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-wifi.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on an ESP32 microcontroller. | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-en-intro.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-en-package.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-en-package.mp3) |
| 東京は今日の午後から雨が降り、明日の朝の気温は2度まで下がる見込みです。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-news.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-news.mp3) |
| バッテリーの残りは15%で、室温は28度です。アラームは明日の朝6時30分にセットされています。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-numbers.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-numbers.mp3) |
| 部屋の電気をつけましょうか？ | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-question.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-question.mp3) |

🇧🇷 🇬🇧 **Português (Brasil)–English**

| Sentence | nu-pt Quality | nu-pt Lite |
|---|---|---|
| Olá! Eu sou uma voz que funciona inteiramente em um chip ESP32 e falo português e inglês. | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-intro.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-intro.mp3) |
| A reunião no Zoom começa às 3 da tarde. Por favor, mande o arquivo do PowerPoint antes. | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-zoom.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-zoom.mp3) |
| O celular já está conectado ao Wi-Fi. Agora dá para assistir à Netflix. | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-wifi.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-wifi.mp3) |
| This text-to-speech voice runs entirely on the ESP32 microcontroller. | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-en-intro.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-en-package.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-en-package.mp3) |
| Em São Paulo vai chover a partir da tarde, e amanhã cedo a temperatura deve cair para 12 graus. | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-news.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-news.mp3) |
| A bateria está em 15% e a temperatura da sala é de 28 graus. O alarme está marcado para as 6:30 da manhã. | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-numbers.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-numbers.mp3) |
| Quer que eu acenda a luz do quarto? | [▶ nu-pt Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-m-question.mp3) | [▶ nu-pt Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nupt-s-question.mp3) |

🇮🇩 🇬🇧 **Indonesia–English**

| Sentence | nu-id Quality | nu-id Lite |
|---|---|---|
| Halo! Saya adalah suara yang berjalan sepenuhnya di chip ESP32 dan bisa berbicara bahasa Indonesia dan Inggris. | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-intro.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-intro.mp3) |
| Rapat di Zoom dimulai pukul tiga sore. Tolong kirim file PowerPoint-nya sebelum rapat. | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-zoom.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-zoom.mp3) |
| Ponselnya sudah tersambung ke Wi-Fi. Sekarang kita bisa menonton Netflix. | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-wifi.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-wifi.mp3) |
| Hello! I am a text-to-speech voice running entirely on the ESP32 microcontroller. | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-en-intro.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-en-package.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-en-package.mp3) |
| Jakarta diperkirakan hujan mulai sore ini, dan besok pagi suhu akan turun menjadi 24 derajat. | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-news.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-news.mp3) |
| Baterai tinggal 15% dan suhu ruangan 28 derajat. Alarm sudah diatur pukul 06.30 pagi. | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-numbers.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-numbers.mp3) |
| Mau saya nyalakan lampu kamar? | [▶ nu-id Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-m-question.mp3) | [▶ nu-id Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuid-s-question.mp3) |

🇮🇳 🇬🇧 **हिन्दी–English**

| Sentence | nu-hi Quality | nu-hi Lite |
|---|---|---|
| नमस्ते! मैं एक आवाज़ हूँ जो पूरी तरह ESP32 चिप पर चलती है और हिंदी और अंग्रेज़ी बोलती है। | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-intro.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-intro.mp3) |
| Zoom पर मीटिंग दोपहर तीन बजे शुरू होगी। कृपया उससे पहले PowerPoint फ़ाइल भेज दीजिए। | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-zoom.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-zoom.mp3) |
| फ़ोन Wi-Fi से जुड़ गया है। अब हम Netflix देख सकते हैं। | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-wifi.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-wifi.mp3) |
| Hello! I am a text-to-speech voice running entirely on the ESP32 microcontroller. | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-en-intro.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-en-package.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-en-package.mp3) |
| दिल्ली में आज शाम से बारिश होने की संभावना है, और कल सुबह तापमान गिरकर 18 डिग्री तक पहुँच जाएगा। | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-news.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-news.mp3) |
| बैटरी 15% बची है और कमरे का तापमान 28 डिग्री है। अलार्म सुबह 6:30 बजे का लगा है। | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-numbers.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-numbers.mp3) |
| क्या मैं कमरे की बत्ती जला दूँ? | [▶ nu-hi Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-m-question.mp3) | [▶ nu-hi Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuhi-s-question.mp3) |

🇪🇸 🇬🇧 **Español–English**

| Sentence | nu-es Quality | nu-es Lite |
|---|---|---|
| ¡Hola! Soy una voz que funciona completamente en un chip ESP32 y hablo español e inglés. | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-intro.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-intro.mp3) |
| La reunión en Zoom empieza a las tres de la tarde. Por favor, envía el archivo de PowerPoint antes. | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-zoom.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-zoom.mp3) |
| El móvil ya está conectado al Wi-Fi. Ahora podemos ver Netflix. | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-wifi.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-wifi.mp3) |
| Hello! I am a text-to-speech voice running entirely on the ESP32 microcontroller. | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-en-intro.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-en-package.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-en-package.mp3) |
| En Madrid va a llover a partir de esta tarde, y mañana temprano la temperatura bajará a 8 grados. | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-news.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-news.mp3) |
| La batería está al 15% y la temperatura de la habitación es de 28 grados. La alarma está puesta a las 6:30 de la mañana. | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-numbers.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-numbers.mp3) |
| ¿Quieres que encienda la luz del dormitorio? | [▶ nu-es Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-m-question.mp3) | [▶ nu-es Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nues-s-question.mp3) |

🇹🇭 🇬🇧 **ไทย–English**

| Sentence | nu-th Quality | nu-th Lite |
|---|---|---|
| สวัสดีค่ะ ฉันเป็นเสียงพูดที่ทำงานบนชิป ESP32 ทั้งหมด และพูดได้ทั้งภาษาไทยและภาษาอังกฤษ | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-intro.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-intro.mp3) |
| ประชุมผ่าน Zoom จะเริ่มตอนบ่ายสามโมง กรุณาส่งไฟล์ PowerPoint มาก่อนนะคะ | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-zoom.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-zoom.mp3) |
| โทรศัพท์เชื่อมต่อ Wi-Fi แล้ว ตอนนี้เราดู Netflix ได้เลย | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-wifi.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-wifi.mp3) |
| Hello! I am a text-to-speech voice running entirely on the ESP32 microcontroller. | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-en-intro.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-en-package.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-en-package.mp3) |
| กรุงเทพฯ มีโอกาสฝนตกตั้งแต่เย็นวันนี้ และพรุ่งนี้เช้าอุณหภูมิจะลดลงเหลือ 18 องศา | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-news.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-news.mp3) |
| แบตเตอรี่เหลือ 15% และอุณหภูมิในห้องคือ 28 องศา ตั้งนาฬิกาปลุกไว้ตอน 6.30 น. | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-numbers.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-numbers.mp3) |
| ให้เปิดไฟในห้องนอนไหมคะ | [▶ nu-th Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-m-question.mp3) | [▶ nu-th Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuth-s-question.mp3) |
<!-- END:samples -->
