# vtts documentation

Start with the [project README](../README.md) for the voice catalog, hardware support and quick start. This page indexes everything else.

## Using vtts

| Document | Contents |
|---|---|
| [Firmware for ESP32-P4 and ESP32-S3](../firmware/esp32/README.md) | Supported boards, build and flash, self-test, adding a board |
| [C runtime](../runtime/README.md) | API, memory model, host build and tests, device text front-end, porting |
| [Model file format](model-format.md) | Binary layout of `.vtts` files, required dims, load-time checks |
| [Pronunciation rules and dictionaries](frontend/pronunciation-rules.md) | How text is read (product codes, loanwords, abbreviations), the per-language data files, and how to change them |
| [Website](https://tuanpmt.github.io/vtts/) ([source](index.html)) | Audio samples generated on the chip, voice catalog, hardware table |
| [Hugging Face model card](huggingface/README.md) | Source of the model card for [huggingface.co/tuanpm/vtts](https://huggingface.co/tuanpm/vtts) |

## Reports

| Report | Contents |
|---|---|
| [On-chip performance](reports/performance.md) | RTF, latency, CPU load and memory on ESP32-P4 and ESP32-S3, and how the runtime got there |
| [Bilingual student evaluation](reports/bilingual-student-eval.md) | CER/WER and UTMOS of the released Vietnamese + English models (v0.4.0), quality and lite, against their teachers |
| [Bilingual teacher evaluation](reports/bilingual-teacher-eval.md) | CER/WER and UTMOS of the bilingual teachers on Vietnamese, English and mixed sentences, per checkpoint |
| [Runtime optimization research](reports/runtime-optimization-research.md) | Compute budget, bottlenecks and a prioritized optimization plan for both chips (in progress) |
| [Baselines](reports/baseline.md) | sanoTTS and Piper Vietnamese voices on the out-of-domain set; the derived teacher gate |
| [InfoRe1 dataset](reports/dataset-infore1.md) | Preparation and filtering of the recorded corpus used in early development (v0.1–v0.3) |

Raw baseline scores: [`piper-25h-ood.json`](reports/piper-25h-ood.json), [`sanotts-vi-ood.json`](reports/sanotts-vi-ood.json).

## Design

Design documents record the decisions as they were made. Each one starts with a status line; the README and the reports above describe the current state.

| Document | Status |
|---|---|
| [Spec: Vietnamese TTS on ESP32-P4](design/specs/2026-11-14-vietnamese-tts-p4-design.md) | Implemented (v0.1.0–v0.3.0), with changes noted |
| [Plan 1: foundation](design/plans/2026-11-14-p1-foundation.md) | Completed |
| [Plan 2: VITS teacher](design/plans/2026-11-14-p2-teacher.md) | Completed |
| [Plan 3: student, exporter, C runtime](design/plans/2026-11-14-p3-student-runtime.md) | Completed |
| [Plan 4: ESP32-P4](design/plans/2026-11-14-p4-esp32p4.md) | Completed, with changes noted |
| [Spec: bilingual Vietnamese–English](design/specs/2026-11-16-bilingual-vi-en-design.md) | In progress |
| [Plan: bilingual Vietnamese–English](design/plans/2026-11-16-bilingual-vi-en.md) | In progress |
| [Plan: runtime optimization for ESP32-S3 and ESP32-P4](design/plans/2026-11-17-runtime-optimization.md) | Closed (S3 limit reached; smaller vocoder next) |
| [Roadmap: bilingual voices (X + English)](design/plans/2026-11-18-roadmap-bilingual.md) | Adopted |

## Project

- [CHANGELOG](../CHANGELOG.md): release history.
- [CONTRIBUTING](../CONTRIBUTING.md): tests, adding a language or a board, code style.
- [NOTICE](../NOTICE): third-party code and data.
