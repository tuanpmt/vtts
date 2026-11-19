---
license: apache-2.0
language:
  - vi
  - ko
  - zh
  - en
pipeline_tag: text-to-speech
tags:
  - text-to-speech
  - tts
  - vietnamese
  - korean
  - chinese
  - mandarin
  - english
  - bilingual
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

# vtts: bilingual text-to-speech models for ESP32 microcontrollers

Tiny int8 voices for [vtts](https://github.com/tuanpmt/vtts), a text-to-speech engine that runs entirely on ESP32 chips: text normalization, grapheme-to-phoneme, the acoustic model and the iSTFT vocoder all run on the microcontroller, with no network. Listen to samples generated on the chip on the [website](https://tuanpmt.github.io/vtts/).

Every vtts model is **bilingual: one main language + English**. One voice reads the main language, English, and sentences that mix both ("Đã kết nối Bluetooth với AirPods", "스마트폰을 Wi-Fi에 연결했어요", "已经通过Bluetooth连接到AirPods"); the on-device front-end picks the language per word. Released pairs: Vietnamese + English (v0.4.0), Korean + English and Chinese (Mandarin) + English (v0.5.0).

> These files are not PyTorch or Transformers checkpoints. They are `.vtts` files for the vtts C runtime ([format](https://github.com/tuanpmt/vtts/blob/main/docs/model-format.md)), meant to be flashed with the [ESP32 firmware](https://github.com/tuanpmt/vtts/tree/main/firmware/esp32) or run with the host tools.

## Repository layout

One folder per voice. Each voice comes in two sizes, and both run on the ESP32-P4 and the ESP32-S3: a **quality** model (M) for the best sound and a **lite** model (S) that is faster and uses less CPU and flash.

| Folder | Voice | Languages | Files | Release |
|---|---|---|---|---|
| `vi-en-nam-1/` | `nam-1` (male) | Vietnamese + English, code-switching | `vtts-vien-nam1-m-v0.4.q8.vtts`, `vtts-vien-nam1-s-v0.4.q8.vtts` | v0.4.0 |
| `vi-en-nu-10/` | `nu-10` (female) | Vietnamese + English, code-switching | `vtts-vien-nu10-m-v0.4.q8.vtts`, `vtts-vien-nu10-s-v0.4.q8.vtts` | v0.4.0 |
| `ko-en-nu-ko/` | `nu-ko` (female, about 40, Seoul) | Korean + English, code-switching | `vtts-koen-nuko-m-v0.5.q8.vtts`, `vtts-koen-nuko-s-v0.5.q8.vtts` | v0.5.0 |
| `zh-en-nu-zh/` | `nu-zh` (female, about 40, Beijing Mandarin) | Chinese (Mandarin) + English, code-switching | `vtts-zhen-nuzh-m-v0.5.q8.vtts`, `vtts-zhen-nuzh-s-v0.5.q8.vtts` | v0.5.0 |

Each folder has a `SHA256SUMS` file. More pairs (Japanese, Spanish, Portuguese, Indonesian, Hindi, Thai, each + English) will follow in their own folders.

## Models

| File | Tier | Params | Size | ESP32-P4 RTF | ESP32-S3 RTF |
|---|---|---:|---:|---:|---:|
| `vtts-vien-nam1-m-v0.4.q8.vtts` | Quality (M) | 1.83M | 2.6 MB | 0.26 | 0.51 |
| `vtts-vien-nam1-s-v0.4.q8.vtts` | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.30 |
| `vtts-vien-nu10-m-v0.4.q8.vtts` | Quality (M) | 1.83M | 2.6 MB | 0.26 | 0.51 |
| `vtts-vien-nu10-s-v0.4.q8.vtts` | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.30 |
| `vtts-koen-nuko-m-v0.5.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.26 | 0.49 |
| `vtts-koen-nuko-s-v0.5.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.17 | 0.29 |
| `vtts-zhen-nuzh-m-v0.5.q8.vtts` | Quality (M) | 1.84M | 2.6 MB | 0.26 | 0.51 |
| `vtts-zhen-nuzh-s-v0.5.q8.vtts` | Lite (S) | 0.83M | 1.2 MB | 0.18 | 0.30 |

Token set `vi-en` (107 tokens: Vietnamese spelling-based phonemes with 6 tones, English ARPAbet with stress), `ko-en` (153 tokens: the same 107 plus 46 Korean onset, vowel and coda tokens) or `zh-en` (171 tokens: the vi-en set plus Mandarin initials, finals and tones), 22.05 kHz output. RTF (`bench`) below 1 is faster than real time; with streaming, speech starts after 0.06–0.15 s (S) / 0.16–0.34 s (M) on the ESP32-P4 and 0.17–0.32 s (S) / 0.27–0.61 s (M) on the ESP32-S3, for all three pairs. Measured on a Waveshare ESP32-P4-86-Panel-ETH-2RO and an ESP32-S3-Touch-LCD-2.8 (8 MB PSRAM required on the S3). Details: [performance report](https://github.com/tuanpmt/vtts/blob/main/docs/reports/performance.md).

Quality on three out-of-domain sets of 50 sentences per pair (not in the training text), audio from the int8 C runtime. CER is the character error rate of an ASR transcript (PhoWhisper-large for Vietnamese, tones included; Whisper large-v3 for English, Korean, Mandarin and mixed sentences); UTMOS predicts naturalness.

Vietnamese + English:

| Model | Vietnamese CER | English CER | Mixed CER | UTMOS (vi / en / mixed) |
|---|---:|---:|---:|---|
| `nam-1` M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M | 0.014 | 0.008 | 0.015 | 2.72 / 3.44 / 2.70 |
| `nu-10` S | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

Korean + English (Korean CER counts Hangul syllables; the mixed CER counts only the Korean characters, because Whisper writes most English words in Hangul, "Google Drive" → 구글 드라이브, which gives every system a plain CER of 0.30–0.37 on that set, the reference voice included):

| Model | Korean CER | English CER | Mixed CER (Hangul only) | UTMOS (ko / en / mixed) |
|---|---:|---:|---:|---|
| `nu-ko` M | 0.021 | 0.023 | 0.024 | 2.75 / 3.39 / 2.75 |
| `nu-ko` S | 0.045 | 0.023 | 0.055 | 2.68 / 3.18 / 2.65 |
| VoxCPM2 `nu-ko` (reference voice) | — | — | 0.016 | — / — / 3.92 |

Chinese + English (`nu-zh`), Whisper large-v3 for all three sets (CER per Han character for Mandarin):

| Model | Mandarin CER | English CER | Mixed CER | UTMOS (zh / en / mixed) |
|---|---:|---:|---:|---|
| `nu-zh` M | 0.020 | 0.021 | 0.047 | 3.16 / 3.64 / 3.23 |
| `nu-zh` S | 0.042 | 0.034 | 0.032 | 2.89 / 3.35 / 2.96 |

Whisper sometimes writes an English word of a mixed sentence in Chinese characters (Samsung → 三星), so the mixed CER is an upper bound.

Reports: [bilingual-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/bilingual-student-eval.md) (vi-en), [ko-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/ko-student-eval.md) (ko-en), [zh-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/zh-student-eval.md) (zh-en).

## Usage

```bash
# download one voice (here nu-10)
huggingface-cli download tuanpm/vtts --include "vi-en-nu-10/*" --local-dir models

# flash a board (ESP-IDF v6.1); BOARD is esp32-p4-86-panel-eth-2ro, esp32-p4-nano, esp32-s3-touch-lcd-2.8 or echoear
git clone https://github.com/tuanpmt/vtts && cd vtts/firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../../models/vi-en-nu-10/vtts-vien-nu10-s-v0.4.q8.vtts \
  ../../../models/vi-en-nu-10/vtts-vien-nu10-m-v0.4.q8.vtts -p PORT flash monitor
```

For the Korean + English voice download `ko-en-nu-ko/*` and pass `vtts-koen-nuko-s-v0.5.q8.vtts` and `vtts-koen-nuko-m-v0.5.q8.vtts` instead; for Chinese + English download `zh-en-nu-zh/*` and pass `vtts-zhen-nuzh-s-v0.5.q8.vtts` and `vtts-zhen-nuzh-m-v0.5.q8.vtts` (`build.sh` embeds the 116 KB Mandarin reading table they need).

Type a sentence on the serial console (main language, English or mixed) and the board speaks it; `model s` / `model m` switch between the two sizes and `lang vi|en|auto` sets the text mode of vi-en models (ko-en models have one mode, `ko`, and zh-en models one, `zh`; both also read English). The same files are attached to the GitHub releases [v0.4.0](https://github.com/tuanpmt/vtts/releases/tag/v0.4.0) (vi-en) and [v0.5.0](https://github.com/tuanpmt/vtts/releases/tag/v0.5.0) (ko-en and zh-en).

## How the models are made

- **Training data:** speech synthesized with [VoxCPM2](https://github.com/OpenBMB/VoxCPM) (Apache-2.0) from designed voices (not cloned from real people): about 98 h per Vietnamese + English voice, with sentences chosen to cover rare Vietnamese syllables, numbers, English and code-switched text; about 43,600 sentences (Korean, Korean with English words, English) for `nu-ko`; 54,636 sentences (Mandarin, Mandarin with English terms, English) for `nu-zh`. No recorded corpus is used.
- **Teacher:** a VITS model (~24M parameters) per voice, trained from random initialization on that synthetic audio only.
- **Distillation:** the teacher produces durations, latents and audio; a small student (duration + acoustic model with a pitch/energy predictor + Vocos-style ConvNeXt/iSTFT decoder) learns from it in three stages and is quantized to int8.
- **Front-end:** rule-based, in Python (training) and C (device) with identical output: a spelling-based Vietnamese G2P, a Korean G2P (Hangul decomposition, the standard pronunciation rules, Sino-Korean and native numbers), a Mandarin front-end (pinyin readings with a polyphone phrase table, tones, Chinese number reading), an English front-end (CMU Pronouncing Dictionary, learned letter-to-sound rules, normalizer) and per-word language tagging. The English lexicon (1.9 MB) is embedded in the firmware, and for zh-en also the Mandarin reading table (116 KB).

## License and limitations

- **Apache-2.0** for these model files and for the vtts code.
- Naturalness is below the teacher (about one UTMOS point), the usual gap for models this small. Brand names inside Vietnamese sentences and unusual names are the hardest cases.
- Korean + English: "Bluetooth" and "Google Meet" are read poorly (write 블루투스); numbers are always read in Korean, also inside English sentences; on the ESP32-S3 with two cores the output of both ko-en models is not deterministic (`cores 1` avoids it).
- Chinese + English: digits inside English sentences are read in Mandarin (write those numbers as words); on the ESP32-S3 with two cores both zh-en models are not deterministic (`cores 1` avoids it).
- Label audio produced with these models as AI-generated, and do not use them to impersonate real people.

## Links

- Code, firmware and documentation: [github.com/tuanpmt/vtts](https://github.com/tuanpmt/vtts)
- Website with on-chip samples: [tuanpmt.github.io/vtts](https://tuanpmt.github.io/vtts/)
- Changelog: [CHANGELOG.md](https://github.com/tuanpmt/vtts/blob/main/CHANGELOG.md)
- Built with [Claude Code](https://claude.com/claude-code) (Anthropic): the runtime, training pipeline and documentation were written with it, directed and reviewed by the maintainer.
