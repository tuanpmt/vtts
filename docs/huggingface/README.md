---
license: apache-2.0
language:
  - vi
  - en
pipeline_tag: text-to-speech
tags:
  - text-to-speech
  - tts
  - vietnamese
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

Every vtts model is **bilingual: one main language + English**. One voice reads the main language, English, and sentences that mix both ("Đã kết nối Bluetooth với AirPods"); the on-device front-end picks the language per word.

> These files are not PyTorch or Transformers checkpoints. They are `.vtts` files for the vtts C runtime ([format](https://github.com/tuanpmt/vtts/blob/main/docs/model-format.md)), meant to be flashed with the [ESP32 firmware](https://github.com/tuanpmt/vtts/tree/main/firmware/esp32) or run with the host tools.

## Repository layout

One folder per voice. Each voice comes in two sizes, and both run on the ESP32-P4 and the ESP32-S3: a **quality** model (M) for the best sound and a **lite** model (S) that is faster and uses less CPU and flash.

| Folder | Voice | Languages | Files (v0.4.0) |
|---|---|---|---|
| `vi-en-nam-1/` | `nam-1` (male) | Vietnamese + English, code-switching | `vtts-vien-nam1-m-v0.4.q8.vtts`, `vtts-vien-nam1-s-v0.4.q8.vtts` |
| `vi-en-nu-10/` | `nu-10` (female) | Vietnamese + English, code-switching | `vtts-vien-nu10-m-v0.4.q8.vtts`, `vtts-vien-nu10-s-v0.4.q8.vtts` |

Each folder has a `SHA256SUMS` file. More pairs (Chinese, Korean, Japanese, Spanish, Portuguese, Indonesian, Hindi, Thai, each + English) will follow in their own folders.

## Models

| File | Tier | Params | Size | ESP32-P4 RTF | ESP32-S3 RTF |
|---|---|---:|---:|---:|---:|
| `vtts-vien-nam1-m-v0.4.q8.vtts` | Quality (M) | 1.83M | 2.6 MB | 0.26 | 0.51 |
| `vtts-vien-nam1-s-v0.4.q8.vtts` | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.30 |
| `vtts-vien-nu10-m-v0.4.q8.vtts` | Quality (M) | 1.83M | 2.6 MB | 0.26 | 0.51 |
| `vtts-vien-nu10-s-v0.4.q8.vtts` | Lite (S) | 0.82M | 1.2 MB | 0.18 | 0.30 |

Token set `vi-en` (107 tokens: Vietnamese spelling-based phonemes with 6 tones, English ARPAbet with stress), 22.05 kHz output. RTF (`bench`) below 1 is faster than real time; with streaming, speech starts after 0.06–0.15 s (S) / 0.17–0.34 s (M) on the ESP32-P4 and 0.17–0.32 s (S) / 0.31–0.61 s (M) on the ESP32-S3. Measured on a Waveshare ESP32-P4-86-Panel-ETH-2RO and an ESP32-S3-Touch-LCD-2.8 (8 MB PSRAM required on the S3). Details: [performance report](https://github.com/tuanpmt/vtts/blob/main/docs/reports/performance.md).

Quality on three out-of-domain sets of 50 sentences each (not in the training text), audio from the int8 C runtime. CER is the character error rate of an ASR transcript (PhoWhisper-large for Vietnamese, tones included; Whisper large-v3 for English and mixed sentences); UTMOS predicts naturalness:

| Model | Vietnamese CER | English CER | Mixed CER | UTMOS (vi / en / mixed) |
|---|---:|---:|---:|---|
| `nam-1` M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M | 0.014 | 0.008 | 0.015 | 2.72 / 3.44 / 2.70 |
| `nu-10` S | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

Report: [bilingual-student-eval.md](https://github.com/tuanpmt/vtts/blob/main/docs/reports/bilingual-student-eval.md).

## Usage

```bash
# download one voice (here nu-10)
huggingface-cli download tuanpm/vtts --include "vi-en-nu-10/*" --local-dir models

# flash a board (ESP-IDF v6.1); BOARD is esp32-p4-86-panel-eth-2ro, esp32-p4-nano, esp32-s3-touch-lcd-2.8 or echoear
git clone https://github.com/tuanpmt/vtts && cd vtts/firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../../models/vi-en-nu-10/vtts-vien-nu10-s-v0.4.q8.vtts \
  ../../../models/vi-en-nu-10/vtts-vien-nu10-m-v0.4.q8.vtts -p PORT flash monitor
```

Type a sentence on the serial console (Vietnamese, English or mixed) and the board speaks it; `model s` / `model m` switch between the two sizes and `lang vi|en|auto` sets the text mode. The same files are attached to the [GitHub release v0.4.0](https://github.com/tuanpmt/vtts/releases/tag/v0.4.0).

## How the models are made

- **Training data:** about 98 h of speech per voice, synthesized with [VoxCPM2](https://github.com/OpenBMB/VoxCPM) (Apache-2.0) from designed voices (not cloned from real people), with sentences chosen to cover rare Vietnamese syllables, numbers, English and code-switched text. No recorded corpus is used.
- **Teacher:** a VITS model (~24M parameters) per voice, trained from random initialization on that synthetic audio only.
- **Distillation:** the teacher produces durations, latents and audio; a small student (duration + acoustic model with a pitch/energy predictor + Vocos-style ConvNeXt/iSTFT decoder) learns from it in three stages and is quantized to int8.
- **Front-end:** rule-based, in Python (training) and C (device) with identical output: a spelling-based Vietnamese G2P, an English front-end (CMU Pronouncing Dictionary, learned letter-to-sound rules, normalizer) and per-word language tagging. The English lexicon (1.9 MB) is embedded in the firmware.

## License and limitations

- **Apache-2.0** for these model files and for the vtts code.
- Naturalness is below the teacher (about one UTMOS point), the usual gap for models this small. Brand names inside Vietnamese sentences and unusual names are the hardest cases.
- Label audio produced with these models as AI-generated, and do not use them to impersonate real people.

## Links

- Code, firmware and documentation: [github.com/tuanpmt/vtts](https://github.com/tuanpmt/vtts)
- Website with on-chip samples: [tuanpmt.github.io/vtts](https://tuanpmt.github.io/vtts/)
- Changelog: [CHANGELOG.md](https://github.com/tuanpmt/vtts/blob/main/CHANGELOG.md)
- Built with [Claude Code](https://claude.com/claude-code) (Anthropic): the runtime, training pipeline and documentation were written with it, directed and reviewed by the maintainer.
