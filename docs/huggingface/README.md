---
license: apache-2.0
language:
  - vi
  - ko
  - zh
  - ja
  - pt
  - id
  - hi
  - es
  - th
  - en
pipeline_tag: text-to-speech
tags:
  - text-to-speech
  - tts
  - vietnamese
  - korean
  - chinese
  - mandarin
  - japanese
  - portuguese
  - brazilian-portuguese
  - indonesian
  - hindi
  - spanish
  - thai
  - english
  - bilingual
  - american-english
  - code-switching
  - esp32
  - esp32-p4
  - esp32-s3
  - microcontroller
  - embedded
  - on-device
  - int8
  - vits
  - vocos
  - distillation
---

# vtts: English and bilingual text-to-speech models for ESP32 microcontrollers

Tiny int8 voices for [vtts](https://github.com/tuanpmt/vtts), a text-to-speech engine that runs entirely on ESP32 chips: text normalization, grapheme-to-phoneme, the acoustic model and the iSTFT vocoder all run on the microcontroller, with no network. Listen to samples generated on the chip on the [website](https://tuanpmt.github.io/vtts/).

vtts has an **English-only voice**, `nu-en` (American English, v0.9.0; M and S updated in v0.10.1), and **bilingual voices: one main language + English**. A bilingual voice reads the main language, English, and sentences that mix both ("Đã kết nối Bluetooth với AirPods", "스마트폰을 Wi-Fi에 연결했어요", "已经通过Bluetooth连接到AirPods", "このWi-Fiはpasswordが必要ですか？", "O sinal do Wi-Fi está fraco", "Sinyal Wi-Fi lemah sekali", "Wi-Fi का signal बहुत कमज़ोर है", "El deadline del proyecto", "สัญญาณ Wi-Fi อ่อนมาก"); the on-device front-end picks the language per word. Released: English (v0.9.0; `nu-en` M and S updated in v0.10.1), Vietnamese + English (v0.4.0; `nu-10` M updated in v0.9.1, S in v0.10.2), Korean + English and Chinese (Mandarin) + English (v0.5.0; `nu-ko` S and `nu-zh` M updated in v0.10.3), Japanese + English (v0.6.0), Portuguese (Brazil) + English (v0.7.0), Indonesian + English, Hindi + English and Spanish + English (v0.8.0), Thai + English (v0.10.0).

> These files are not PyTorch or Transformers checkpoints. They are `.vtts` files for the vtts C runtime ([format](https://github.com/tuanpmt/vtts/blob/main/docs/model-format.md)), meant to be flashed with the [ESP32 firmware](https://github.com/tuanpmt/vtts/tree/main/firmware/esp32) or run with the host tools.

## Repository layout

One folder per voice. Each voice comes in two sizes, and both run on the ESP32-P4 and the ESP32-S3: a **quality** model (M) for the best sound and a **lite** model (S) that is faster and uses less CPU and flash.

| Folder | Voice | Languages | Files | Release |
|---|---|---|---|---|
| `en-nu-en/` | `nu-en` (female, American English) | English only | **`vtts-en-nuen-m-v0.10.1.q8.vtts`**, **`vtts-en-nuen-s-v0.10.1.q8.vtts`** (recommended); the older `vtts-en-nuen-m-v0.9.q8.vtts` and `vtts-en-nuen-s-v0.9.q8.vtts` stay in the folder | v0.9.0, M and S updated in v0.10.1 |
| `vi-en-nam-1/` | `nam-1` (male) | Vietnamese + English, code-switching | `vtts-vien-nam1-m-v0.4.q8.vtts`, `vtts-vien-nam1-s-v0.4.q8.vtts` | v0.4.0 |
| `vi-en-nu-10/` | `nu-10` (female) | Vietnamese + English, code-switching | **`vtts-vien-nu10-m-v0.9.1.q8.vtts`** (recommended M), **`vtts-vien-nu10-s-v0.10.2.q8.vtts`** (recommended S); the older `vtts-vien-nu10-m-v0.4.q8.vtts` and `vtts-vien-nu10-s-v0.4.q8.vtts` stay in the folder | v0.4.0, M updated in v0.9.1, S in v0.10.2 |
| `ko-en-nu-ko/` | `nu-ko` (female, about 40, Seoul) | Korean + English, code-switching | `vtts-koen-nuko-m-v0.5.q8.vtts`, **`vtts-koen-nuko-s-v0.10.3.q8.vtts`** (recommended S); the older `vtts-koen-nuko-s-v0.5.q8.vtts` stays in the folder | v0.5.0, S updated in v0.10.3 |
| `zh-en-nu-zh/` | `nu-zh` (female, about 40, Beijing Mandarin) | Chinese (Mandarin) + English, code-switching | **`vtts-zhen-nuzh-m-v0.10.3.q8.vtts`** (recommended M), `vtts-zhen-nuzh-s-v0.5.q8.vtts`; the older `vtts-zhen-nuzh-m-v0.5.q8.vtts` stays in the folder | v0.5.0, M updated in v0.10.3 |
| `ja-en-nu-ja/` | `nu-ja` (female, about 40, Tokyo) | Japanese + English, code-switching | `vtts-jaen-nuja-m-v0.6.q8.vtts`, `vtts-jaen-nuja-s-v0.6.q8.vtts` | v0.6.0 |
| `pt-en-nu-pt/` | `nu-pt` (female, about 40, Brazilian Portuguese) | Portuguese (Brazil) + English, code-switching | `vtts-pten-nupt-m-v0.7.q8.vtts`, `vtts-pten-nupt-s-v0.7.q8.vtts` | v0.7.0 |
| `id-en-nu-id/` | `nu-id` (female, about 40, Indonesian) | Indonesian + English, code-switching | `vtts-iden-nuid-m-v0.8.q8.vtts`, `vtts-iden-nuid-s-v0.8.q8.vtts` | v0.8.0 |
| `hi-en-nu-hi/` | `nu-hi` (female, about 40, Hindi) | Hindi + English, code-switching (Devanagari and Latin) | `vtts-hien-nuhi-m-v0.8.q8.vtts`, `vtts-hien-nuhi-s-v0.8.q8.vtts` | v0.8.0 |
| `es-en-nu-es/` | `nu-es` (female, about 40, Spanish) | Spanish + English, code-switching | `vtts-esen-nues-m-v0.8.q8.vtts`, `vtts-esen-nues-s-v0.8.q8.vtts` | v0.8.0 |
| `th-en-nu-th/` | `nu-th` (female, Thai) | Thai + English, code-switching | `vtts-then-nuth-m-v0.10.q8.vtts`, `vtts-then-nuth-s-v0.10.q8.vtts` | v0.10.0 |

Each folder has a `SHA256SUMS` file. More pairs (French, German and others, each + English) will follow in their own folders.

## Models

| File | Tier | Params | Size | ESP32-P4 RTF | ESP32-S3 RTF |
|---|---|---:|---:|---:|---:|
| **`vtts-en-nuen-m-v0.10.1.q8.vtts`** (recommended) | Quality (M) | 1.83M | 2.6 MB | 0.28 | 0.57 |
| **`vtts-en-nuen-s-v0.10.1.q8.vtts`** (recommended) | Lite (S) | 0.82M | 1.2 MB | 0.19 | 0.33 |
| `vtts-en-nuen-m-v0.9.q8.vtts` (superseded) | Quality (M) | 1.83M | 2.6 MB | 0.28 | 0.57 |
| `vtts-en-nuen-s-v0.9.q8.vtts` (superseded) | Lite (S) | 0.82M | 1.2 MB | 0.19 | 0.32 |
| `vtts-vien-nam1-m-v0.4.q8.vtts` | Quality (M) | 1.83M | 2.6 MB | 0.26 | 0.57 |
| `vtts-vien-nam1-s-v0.4.q8.vtts` | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.32 |
| **`vtts-vien-nu10-m-v0.9.1.q8.vtts`** (recommended) | Quality (M) | 1.83M | 2.6 MB | 0.27 | 0.55 |
| `vtts-vien-nu10-m-v0.4.q8.vtts` (superseded) | Quality (M) | 1.83M | 2.6 MB | 0.26 | 0.57 |
| **`vtts-vien-nu10-s-v0.10.2.q8.vtts`** (recommended) | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.31 |
| `vtts-vien-nu10-s-v0.4.q8.vtts` (superseded) | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.32 |
| `vtts-koen-nuko-m-v0.5.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.26 | 0.57 |
| **`vtts-koen-nuko-s-v0.10.3.q8.vtts`** (recommended) | Lite (S) | 0.83M | 1.2 MB | 0.18 | 0.32 |
| `vtts-koen-nuko-s-v0.5.q8.vtts` (superseded) | Lite (S) | 0.83M | 1.2 MB | 0.17 | 0.32 |
| **`vtts-zhen-nuzh-m-v0.10.3.q8.vtts`** (recommended) | Quality (M) | 1.84M | 2.6 MB | 0.27 | 0.56 |
| `vtts-zhen-nuzh-m-v0.5.q8.vtts` (superseded) | Quality (M) | 1.84M | 2.6 MB | 0.26 | 0.57 |
| `vtts-zhen-nuzh-s-v0.5.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.18 | 0.32 |
| `vtts-jaen-nuja-m-v0.6.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.26 | 0.55 |
| `vtts-jaen-nuja-s-v0.6.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.17 | 0.31 |
| `vtts-pten-nupt-m-v0.7.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.28 | 0.57 |
| `vtts-pten-nupt-s-v0.7.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.19 | 0.32 |
| `vtts-iden-nuid-m-v0.8.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.27 | 0.56 |
| `vtts-iden-nuid-s-v0.8.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.18 | 0.32 |
| `vtts-hien-nuhi-m-v0.8.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.27 | 0.58 |
| `vtts-hien-nuhi-s-v0.8.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.19 | 0.32 |
| `vtts-esen-nues-m-v0.8.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.28 | 0.58 |
| `vtts-esen-nues-s-v0.8.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.19 | 0.32 |
| `vtts-then-nuth-m-v0.10.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.27 | 0.56 |
| `vtts-then-nuth-s-v0.10.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.18 | 0.32 |

Token set `vi-en` (107 tokens: Vietnamese spelling-based phonemes with 6 tones, English ARPAbet with stress; also used by the English-only `nu-en`, whose files record the start mode `en`), `ko-en` (153 tokens: the same 107 plus 46 Korean onset, vowel and coda tokens) `zh-en` (171 tokens: the vi-en set plus Mandarin initials, finals and tones) `ja-en` (144 tokens: the v2 set plus 37 Japanese phonemes), `pt-en` (150 tokens: the v2 set plus 43 Brazilian Portuguese phonemes), `id-en` (141: plus 34 Indonesian tokens), `hi-en` (157: plus 50 Hindi phonemes), `es-en` (138: plus 31 Spanish tokens) or `th-en` (162: plus 55 Thai initials, vowels, finals and tones), 22.05 kHz output. RTF (`bench`) below 1 is faster than real time; with streaming, speech starts after 0.06–0.15 s (S) / 0.13–0.34 s (M) on the ESP32-P4 and 0.16–0.27 s (S) / 0.26–0.50 s (M) on the ESP32-S3, for all pairs. Measured on a Waveshare ESP32-P4-86-Panel-ETH-2RO and an ESP32-S3-Touch-LCD-2.8 (8 MB PSRAM required on the S3). Details: [performance report](https://github.com/tuanpmt/vtts/blob/main/docs/reports/performance.md).

Quality on three out-of-domain sets of 50 sentences per pair (not in the training text), audio from the int8 C runtime. CER is the character error rate of an ASR transcript (PhoWhisper-large for Vietnamese, tones included; Whisper large-v3 for English, Korean, Mandarin, Japanese, Portuguese, Indonesian, Hindi, Spanish, Thai and mixed sentences); UTMOS predicts naturalness.

English only (`nu-en`), `ood_en` and `ood_en2` (numbers, dates and times, commands, units, abbreviations), Whisper large-v3:

| Model | `ood_en` CER | `ood_en2` CER | UTMOS (ood_en / ood_en2) |
|---|---:|---:|---|
| `nu-en` M (v0.10.1, recommended) | 0.012 | 0.024 | 3.56 / 3.56 |
| `nu-en` S (v0.10.1, recommended) | 0.015 | 0.021 | 3.68 / 3.67 |
| `nu-en` M (v0.9.0) | 0.014 | 0.034 | 2.88 / 3.00 |
| `nu-en` S (v0.9.0) | 0.015 | 0.027 | 3.00 / 3.08 |
| `nu-10` M v0.4.0 (English of the vi-en voice) | 0.008 | 0.033 | 3.44 / 3.59 |
| VoxCPM2 `nu-en` (reference voice) | 0.010 | 0.045 | 4.24 / 4.24 |

Vietnamese + English:

| Model | Vietnamese CER | English CER | Mixed CER | UTMOS (vi / en / mixed) |
|---|---:|---:|---:|---|
| `nam-1` M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M (v0.9.1, recommended) | 0.014 | 0.008 | 0.015 | 3.11 / 3.87 / 3.12 |
| `nu-10` M (v0.4.0) | 0.014 | 0.008 | 0.015 | 2.72 / 3.44 / 2.70 |
| `nu-10` S (v0.10.2, recommended) | 0.010 | 0.008 | 0.016 | 2.90 / 3.73 / 2.92 |
| `nu-10` S (v0.4.0) | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

Korean + English (Korean CER counts Hangul syllables; the mixed CER counts only the Korean characters, because Whisper writes most English words in Hangul, "Google Drive" → 구글 드라이브, which gives every system a plain CER of 0.30–0.37 on that set, the reference voice included):

| Model | Korean CER | English CER | Mixed CER (Hangul only) | UTMOS (ko / en / mixed) |
|---|---:|---:|---:|---|
| `nu-ko` M | 0.021 | 0.023 | 0.024 | 2.75 / 3.39 / 2.75 |
| `nu-ko` S (v0.10.3, recommended) | 0.026 | 0.018 | 0.044 | 3.18 / 3.54 / 3.06 |
| `nu-ko` S (v0.5.0) | 0.045 | 0.023 | 0.055 | 2.68 / 3.18 / 2.65 |
| VoxCPM2 `nu-ko` (reference voice) | — | — | 0.016 | — / — / 3.92 |

Chinese + English (`nu-zh`), Whisper large-v3 for all three sets (CER per Han character for Mandarin):

| Model | Mandarin CER | English CER | Mixed CER | UTMOS (zh / en / mixed) |
|---|---:|---:|---:|---|
| `nu-zh` M (v0.10.3, recommended) | 0.024 | 0.018 | 0.030 | 3.36 / 3.76 / 3.44 |
| `nu-zh` M (v0.5.0) | 0.020 | 0.021 | 0.047 | 3.16 / 3.64 / 3.23 |
| `nu-zh` S | 0.042 | 0.034 | 0.032 | 2.89 / 3.35 / 2.96 |

Whisper sometimes writes an English word of a mixed sentence in Chinese characters (Samsung → 三星), so the mixed CER is an upper bound.

Japanese + English (`nu-ja`). Japanese CER on readings: reference and transcript are converted to kana by the ja front-end, because the references write some numbers in kanji (十五分) where Whisper writes digits; the mixed CER counts only the kana and kanji, because Whisper writes most English words in katakana (password → パスワード):

| Model | Japanese CER (reading) | English CER | Mixed CER (kana and kanji only) | UTMOS (ja / en / mixed) |
|---|---:|---:|---:|---|
| `nu-ja` M | 0.050 | 0.023 | 0.054 | 2.57 / 3.22 / 2.61 |
| `nu-ja` S | 0.053 | 0.019 | 0.049 | 2.30 / 2.76 / 2.28 |
| VoxCPM2 `nu-ja` (reference voice) | 0.023 | — | 0.049 | 3.45 / — / 3.43 |

Portuguese (Brazil) + English (`nu-pt`), Whisper large-v3 for all three sets:

| Model | Portuguese CER | English CER | Mixed CER | UTMOS (pt / en / mixed) |
|---|---:|---:|---:|---|
| `nu-pt` M | 0.008 | 0.089 | 0.026 | 2.36 / 2.71 / 2.54 |
| `nu-pt` S | 0.019 | 0.080 | 0.022 | 2.63 / 2.69 / 2.69 |
| VoxCPM2 `nu-pt` (reference voice) | 0.044 | — | 0.044 | 3.99 / — / 3.93 |

The reference voice misreads raw digits ("R$ 1.250,00"); without the numbers group it scores 0.001 / 0.016 against 0.005 / 0.027 (M) and 0.013 / 0.023 (S). The English CER is higher than for the other pairs because the pt mode tags each Latin word by spelling, and short or common English words that fit Portuguese spelling (I, a, an, time, temperature) are read as Portuguese in whole English sentences; Portuguese sentences with English words are not affected. With the v0.8.0 runtime and firmware, which read whole English sentences in English, the same files score 0.012 (M) and 0.014 (S) on English.

Indonesian + English (`nu-id`), Spanish + English (`nu-es`) and Hindi + English (`nu-hi`), Whisper large-v3, English sentences read in English by the sentence-level language decision (id, es):

| Model | Main-language CER | English CER | Mixed CER | UTMOS (main / en / mixed) |
|---|---:|---:|---:|---|
| `nu-id` M | 0.011 | 0.022 | 0.018 | 2.42 / 3.05 / 2.57 |
| `nu-id` S | 0.011 | 0.059 | 0.015 | 2.14 / 2.63 / 2.25 |
| VoxCPM2 `nu-id` (reference voice) | 0.023 | — | 0.042 | 3.07 / — / 3.22 |
| `nu-es` M | 0.019 | 0.020 | 0.006 | 2.83 / 3.07 / 2.87 |
| `nu-es` S | 0.017 | 0.019 | 0.009 | 2.54 / 2.81 / 2.50 |
| VoxCPM2 `nu-es` (reference voice) | 0.020 | — | 0.037 | 3.50 / — / 3.57 |
| `nu-hi` M | 0.094 | 0.053 | 0.054 (Devanagari only) | 2.84 / 3.09 / 2.91 |
| `nu-hi` S | 0.092 | 0.028 | 0.056 (Devanagari only) | 2.84 / 3.03 / 2.88 |
| VoxCPM2 `nu-hi` (reference voice) | 0.069 | — | 0.065 (Devanagari only) | 3.41 / — / 3.55 |

The reference voices misread raw digits; without the numbers group Indonesian is at 0.002–0.003 and Spanish at 0.006–0.008. Hindi CER includes Whisper's spelling variants (nukta, chandrabindu); merged and without numbers it is 0.081 / 0.085 against 0.035 for the reference voice. Whisper writes the English words of Hinglish sentences in Devanagari, so the Hindi mixed CER counts only the Devanagari of the text.

Thai + English (`nu-th`), Whisper large-v3; Thai is written without spaces, so the CER counts Thai characters with spaces removed, and the mixed CER counts only the Thai characters (Whisper writes most English words of a Thai sentence in Thai script):

| Model | Thai CER | English CER | Mixed CER (Thai only) | UTMOS (th / en / mixed) |
|---|---:|---:|---:|---|
| `nu-th` M | 0.044 | 0.018 | 0.043 | 2.88 / 3.51 / 2.95 |
| `nu-th` S | 0.053 | 0.030 | 0.044 | 2.55 / 3.06 / 2.58 |
| VoxCPM2 `nu-th` (reference voice) | 0.076 | — | 0.022 | 3.97 / — / 4.00 |

The reference voice misreads raw digits and dates; without the numbers group it scores 0.039 against 0.054 (M) and 0.050 (S).

Reports: [en-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/en-student-eval.md) (en), [bilingual-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/bilingual-student-eval.md) (vi-en), [ko-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/ko-student-eval.md) (ko-en), [zh-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/zh-student-eval.md) (zh-en), [ja-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/ja-student-eval.md) (ja-en), [pt-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/pt-student-eval.md) (pt-en), [id-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/id-student-eval.md) (id-en), [hi-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/hi-student-eval.md) (hi-en), [es-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/es-student-eval.md) (es-en), [th-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/th-student-eval.md) (th-en).

## Usage

```bash
# download one voice (here nu-10)
huggingface-cli download tuanpm/vtts --include "vi-en-nu-10/*" --local-dir models

# flash a board (ESP-IDF v6.1); BOARD is esp32-p4-86-panel-eth-2ro, esp32-p4-nano, esp32-s3-touch-lcd-2.8 or echoear
git clone https://github.com/tuanpmt/vtts && cd vtts/firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../../models/vi-en-nu-10/vtts-vien-nu10-s-v0.10.2.q8.vtts \
  ../../../models/vi-en-nu-10/vtts-vien-nu10-m-v0.9.1.q8.vtts -p PORT flash monitor
```

For the English-only voice download `en-nu-en/*` and pass `vtts-en-nuen-s-v0.10.1.q8.vtts` and `vtts-en-nuen-m-v0.10.1.q8.vtts` (no blob beyond the English lexicon; the firmware starts these models in English). For the Korean + English voice download `ko-en-nu-ko/*` and pass `vtts-koen-nuko-s-v0.10.3.q8.vtts` and `vtts-koen-nuko-m-v0.5.q8.vtts` instead; for Chinese + English download `zh-en-nu-zh/*` and pass `vtts-zhen-nuzh-s-v0.5.q8.vtts` and `vtts-zhen-nuzh-m-v0.10.3.q8.vtts` (`build.sh` embeds the 116 KB Mandarin reading table they need); for Japanese + English download `ja-en-nu-ja/*` and pass `vtts-jaen-nuja-s-v0.6.q8.vtts` and `vtts-jaen-nuja-m-v0.6.q8.vtts` (`build.sh` embeds the 721 KB Japanese reading table they need); for Portuguese (Brazil) + English download `pt-en-nu-pt/*` and pass `vtts-pten-nupt-s-v0.7.q8.vtts` and `vtts-pten-nupt-m-v0.7.q8.vtts` (no blob beyond the English lexicon); likewise `id-en-nu-id/*`, `hi-en-nu-hi/*` and `es-en-nu-es/*` with their `-s-` and `-m-` files (v0.8.0, no blob beyond the English lexicon) and `th-en-nu-th/*` (v0.10.0, no blob beyond the English lexicon).

Type a sentence on the serial console (main language, English or mixed; English for `nu-en`) and the board speaks it; `model s` / `model m` switch between the two sizes and `lang vi|en|auto` sets the text mode of vi-en models (ko-en, zh-en, ja-en, pt-en, id-en, hi-en, es-en and th-en models have one mode each, `ko`, `zh`, `ja`, `pt`, `id`, `hi`, `es` and `th`, which also read English). The same files are attached to the GitHub releases [v0.4.0](https://github.com/tuanpmt/vtts/releases/tag/v0.4.0) (vi-en), [v0.5.0](https://github.com/tuanpmt/vtts/releases/tag/v0.5.0) (ko-en and zh-en), [v0.6.0](https://github.com/tuanpmt/vtts/releases/tag/v0.6.0) (ja-en) [v0.7.0](https://github.com/tuanpmt/vtts/releases/tag/v0.7.0) (pt-en) [v0.8.0](https://github.com/tuanpmt/vtts/releases/tag/v0.8.0) (id-en, hi-en and es-en), [v0.9.0](https://github.com/tuanpmt/vtts/releases/tag/v0.9.0) (en), [v0.9.1](https://github.com/tuanpmt/vtts/releases/tag/v0.9.1) (the updated `nu-10` M), [v0.10.0](https://github.com/tuanpmt/vtts/releases/tag/v0.10.0) (th-en), [v0.10.1](https://github.com/tuanpmt/vtts/releases/tag/v0.10.1) (the updated `nu-en` M and S), [v0.10.2](https://github.com/tuanpmt/vtts/releases/tag/v0.10.2) (the updated `nu-10` S) and [v0.10.3](https://github.com/tuanpmt/vtts/releases/tag/v0.10.3) (the updated `nu-ko` S and `nu-zh` M).

## How the models are made

- **Training data:** speech synthesized with [VoxCPM2](https://github.com/OpenBMB/VoxCPM) (Apache-2.0) from designed voices (not cloned from real people): about 98 h per Vietnamese + English voice, with sentences chosen to cover rare Vietnamese syllables, numbers, English and code-switched text; about 43,600 sentences (Korean, Korean with English words, English) for `nu-ko`; 54,636 sentences (Mandarin, Mandarin with English terms, English) for `nu-zh`; 49,591 sentences (Japanese, Japanese with English words, English) for `nu-ja`; 45,191 sentences (Brazilian Portuguese, Portuguese with English words, English) for `nu-pt`; 45,857 for `nu-id`, 48,296 for `nu-hi`, 48,336 for `nu-es` and 55,555 for `nu-th` (main language, main language with English words, English); 19,241 English sentences (about 30 h) for `nu-en`. No recorded corpus is used.
- **Teacher:** a VITS model (~24M parameters) per voice, trained from random initialization on that synthetic audio only (`nu-en`: 60k steps starting from the `nu-10` teacher, which was itself trained from random initialization on VoxCPM2 audio).
- **Distillation:** the teacher produces durations, latents and audio; a small student (duration + acoustic model with a pitch/energy predictor + Vocos-style ConvNeXt/iSTFT decoder) learns from it in three stages (front 10k, decoder 30k, joint 20k steps; the updated `nu-10` M of v0.9.1, `nu-en` M and S of v0.10.1, `nu-10` S of v0.10.2 and `nu-ko` S and `nu-zh` M of v0.10.3 use a joint stage of 80k steps, which raises UTMOS at the same CER) and is quantized to int8.
- **Front-end:** rule-based, in Python (training) and C (device) with identical output: a spelling-based Vietnamese G2P, a Korean G2P (Hangul decomposition, the standard pronunciation rules, Sino-Korean and native numbers), a Mandarin front-end (pinyin readings with a polyphone phrase table, tones, Chinese number reading), a Japanese front-end (kana and kanji readings by longest match over a word table, numbers with counters), a Brazilian Portuguese front-end (spelling rules with stress, nasal vowels and the two r sounds; Latin words tagged Portuguese or English per word), Indonesian and Spanish spelling-rule front-ends, a Hindi front-end (Devanagari letters, schwa deletion, nasals, Hindi number reading), a Thai front-end (word segmentation over a word list, syllables by the spelling rules, tones from consonant class, tone mark and syllable type, Thai number reading), a sentence-level English decision for the Latin-script pairs, an English front-end (CMU Pronouncing Dictionary, learned letter-to-sound rules, normalizer) and per-word language tagging. The English lexicon (1.9 MB) is embedded in the firmware, for zh-en also the Mandarin reading table (116 KB), for ja-en the Japanese reading table (721 KB).

## License and limitations

- **Apache-2.0** for these model files and for the vtts code.
- Naturalness is below the teacher (about one UTMOS point), the usual gap for models this small. Brand names inside Vietnamese sentences and unusual names are the hardest cases.
- English (`nu-en`): the v0.10.1 models (longer joint distillation stage) raise UTMOS from 2.9–3.1 to 3.6–3.7, about 0.6 below the reference voice; use them instead of the v0.9.0 files. All-capital words that are not in the lexicon ("NASA") are spelled. A short first sentence ("Hello!") is quiet. Use it in `lang en` only (the files start in English).
- Korean + English: "Bluetooth" and "Google Meet" are read poorly (write 블루투스); numbers are always read in Korean, also inside English sentences.
- Chinese + English: digits inside English sentences are read in Mandarin (write those numbers as words).
- Japanese + English: word-initial *r* is weak (リビング can sound like イビング); digits inside English sentences are read in Japanese and kanji numerals before 分 are read ぶん (write digits: 30分); "Bluetooth" is read poorly (write ブルートゥース).
- Portuguese (Brazil) + English: with runtimes and firmware before v0.8.0, whole English sentences are partly read as Portuguese (English CER about 0.08–0.09); v0.8.0 reads them in English. Acronyms such as ESP32 inside Portuguese sentences are spelled with Portuguese letter names.
- Hindi + English: the first consonant of a sentence is often weak ("बैठक" can sound like "वैटक"); Hindi is understandable but the weakest of the released pairs. Numbers and acronyms inside English sentences are read in Hindi.
- Thai + English: the question particle ไหม can sound like ใหม่ (tone), and กรุณา is read kru-naa instead of ka-ru-naa; numbers inside English sentences are read in Thai.
- With firmware up to v0.8.0 the ESP32-S3 output now and then had a short burst or a changed duration; fixed after v0.8.0 (the S3 output now matches the ESP32-P4).
- Label audio produced with these models as AI-generated, and do not use them to impersonate real people.

## Links

- Code, firmware and documentation: [github.com/tuanpmt/vtts](https://github.com/tuanpmt/vtts)
- Website with on-chip samples: [tuanpmt.github.io/vtts](https://tuanpmt.github.io/vtts/)
- Changelog: [CHANGELOG.md](https://github.com/tuanpmt/vtts/blob/main/CHANGELOG.md)
- Built with [Claude Code](https://claude.com/claude-code) (Anthropic): the runtime, training pipeline and documentation were written with it, directed and reviewed by the maintainer.
