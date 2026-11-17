---
license: cc-by-nc-4.0
language:
  - vi
pipeline_tag: text-to-speech
tags:
  - text-to-speech
  - tts
  - vietnamese
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

# vtts: text-to-speech models for ESP32 microcontrollers

Tiny int8 voices for [vtts](https://github.com/tuanpmt/vtts), a text-to-speech engine that runs entirely on ESP32 chips: text normalization, grapheme-to-phoneme, the acoustic model and the iSTFT vocoder all run on the microcontroller, with no network. Listen to samples generated on the chip on the [website](https://tuanpmt.github.io/vtts/).

> These files are not PyTorch or Transformers checkpoints. They are `.vtts` files for the vtts C runtime ([format](https://github.com/tuanpmt/vtts/blob/main/docs/model-format.md)), meant to be flashed with the [ESP32 firmware](https://github.com/tuanpmt/vtts/tree/main/firmware/esp32) or run with the host CLI.

## Repository layout

One folder per voice. Each voice comes in two sizes, and both run on the ESP32-P4 and the ESP32-S3: a **quality** model (M) for the best sound and a **lite** model (S) that is about 1.7× faster and uses less CPU and flash.

| Folder | Voice | Languages | Status |
|---|---|---|---|
| `vi/` | Vietnamese prototype | Vietnamese | **Released** (v0.3.1): `vtts-vi-m-v0.2.q8.vtts`, `vtts-vi-s-v0.1.q8.vtts` |
| `vi-en-nam-1/` | `nam-1` (male) | Vietnamese + English, code-switching | Training (teacher in progress); not uploaded yet |
| `vi-en-nu-10/` | `nu-10` (female) | Vietnamese + English, code-switching | Training (teacher in progress); not uploaded yet |
| `en/` | English | English | Planned |
| `zh/` | Mandarin Chinese | Chinese | Planned |
| `zh-en/` | Chinese + English | Chinese + English, code-switching | Planned |

The license above applies to the files released so far (`vi/`). Each future voice will state its own license in its folder.

## Released models (`vi/`)

| File | Tier | Params | Size | ESP32-P4 RTF | ESP32-S3 RTF |
|---|---|---:|---:|---:|---:|
| `vtts-vi-m-v0.2.q8.vtts` | Quality (M-vocos v0.2) | 1.73M | 2.6 MB | 0.34–0.42 | 0.85–0.99 |
| `vtts-vi-s-v0.1.q8.vtts` | Lite (S-vocos v0.1) | 0.77M | 1.1 MB | 0.20–0.24 | 0.42–0.47 |

RTF below 1 is faster than real time; speech starts after 0.3–1.2 s on the ESP32-P4 and 0.8–2.4 s on the ESP32-S3 (streaming). Measured on Waveshare ESP32-P4-NANO / ESP32-P4-86-Panel and ESP32-S3-Touch-LCD-2.8 (8 MB PSRAM required on the S3). Details: [performance report](https://github.com/tuanpmt/vtts/blob/main/docs/reports/performance.md).

Quality on 50 out-of-domain Vietnamese sentences (CER from PhoWhisper-large transcripts, tones included; audio from the int8 C runtime):

| System | Params | CER ↓ | UTMOS ↑ |
|---|---:|---:|---:|
| vtts M-vocos v0.2 | 1.73M | 0.012 | 2.19 |
| vtts S-vocos v0.1 | 0.77M | 0.023 | 1.86 |
| Teacher VITS (not released) | 23.7M | 0.015 | 2.50 |
| sanoTTS `vi` | 1.57M | 0.064 | 1.49 |
| Piper `vi_VN-25hours_single` | — | 0.089 | 2.06 |

## Usage

```bash
# download the released Vietnamese models
huggingface-cli download tuanpm/vtts --include "vi/*" --local-dir models

# flash an ESP32-P4-NANO (ESP-IDF v6.1); BOARD can be panel, nano or s3
git clone https://github.com/tuanpmt/vtts && cd vtts/firmware/esp32
BOARD=nano ./build.sh ../../../models/vi/vtts-vi-s-v0.1.q8.vtts ../../../models/vi/vtts-vi-m-v0.2.q8.vtts -p PORT flash monitor
```

Type a Vietnamese sentence on the serial console and the board speaks it. The same files are attached to the [GitHub release v0.3.1](https://github.com/tuanpmt/vtts/releases/tag/v0.3.1).

## How the models are made

- **Front-end:** rule-based, in Python (training) and C (device) with identical output. Vietnamese uses a spelling-based G2P (token set v1, 65 tokens, 6 tones) and reads numbers, dates, times and abbreviations. Bilingual voices use token set v2 (107 tokens: v1 + English ARPAbet and stress) with an English front-end (CMUdict, learned letter-to-sound rules, normalizer) and per-word language tagging.
- **Distillation:** a VITS teacher (~24M parameters) produces durations, latents and audio; a small student (duration + acoustic model with pitch/energy predictor + Vocos-style ConvNeXt/iSTFT decoder) learns from it in three stages and is quantized to int8.
- **Training data:**
  - `vi/`: InfoRe Technology public dataset No.1 (about 25 h of Vietnamese read speech, one speaker), filtered to 22.2 h for training.
  - `vi-en-nam-1/`, `vi-en-nu-10/`: about 98 h of speech per voice, synthesized with VoxCPM2 (Apache-2.0) from designed voices (not cloned from real people), with sentences chosen to cover rare Vietnamese syllables, numbers, English and code-switched text.

## License and limitations

- **`vi/` models: CC BY-NC 4.0, non-commercial use only.** The teacher was initialized from a Piper checkpoint whose training data allows only non-commercial use, and the commercial terms of the InfoRe1 corpus are unclear.
- The vtts code is Apache-2.0; that license does not apply to the model files.
- The Vietnamese prototype is trained on one speaker reading in a fairly even tone, so intonation is flatter than natural speech. Short device prompts and foreign names are the hardest cases.
- On-device text normalization covers numbers, percent, dates and times; e-mail addresses, URLs, phone numbers, currency and units are handled only by the Python front-end.
- Label audio produced with these models as AI-generated, and do not use them to impersonate real people.

## Links

- Code, firmware and documentation: [github.com/tuanpmt/vtts](https://github.com/tuanpmt/vtts)
- Website with on-chip samples: [tuanpmt.github.io/vtts](https://tuanpmt.github.io/vtts/)
- Changelog: [CHANGELOG.md](https://github.com/tuanpmt/vtts/blob/main/CHANGELOG.md)
- Built with [Claude Code](https://claude.com/claude-code) (Anthropic): the runtime, training pipeline and documentation were written with it, directed and reviewed by the maintainer.
