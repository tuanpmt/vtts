# Roadmap

vtts ships **bilingual voices: one main language + English**, with code-switching, and an English-only voice (`nu-en`). Every bilingual model covers one pair; each new pair gets one designed voice and its own release. Plan and reasoning: [design/plans/2026-11-18-roadmap-bilingual.md](design/plans/2026-11-18-roadmap-bilingual.md). Release history: [CHANGELOG.md](../CHANGELOG.md).

- [x] English front-end in Python and on the device (C, parity-tested), per-word language tagging
- [x] Synthesized training data for the bilingual voices `nam-1` and `nu-10`
- [x] Faster runtime: the quality model runs on the ESP32-S3 too
- [x] **English (American)** `nu-en` (female), English only, quality and lite, Apache-2.0 (v0.9.0)
- [x] **Vietnamese + English** `nam-1` (male) and `nu-10` (female), quality and lite, Apache-2.0 (v0.4.0)
- [x] **Korean + English** `nu-ko` (female), quality and lite, Apache-2.0 (v0.5.0)
- [x] **Chinese (Mandarin) + English** `nu-zh` (female), quality and lite, Apache-2.0 (v0.5.0)
- [x] **Japanese + English** `nu-ja` (female), quality and lite, Apache-2.0 (v0.6.0)
- [x] **Portuguese (Brazil) + English** `nu-pt` (female), quality and lite, Apache-2.0 (v0.7.0)
- [x] **Indonesian + English** `nu-id` (female), quality and lite, Apache-2.0 (v0.8.0)
- [x] **Hindi + English** `nu-hi` (female), quality and lite, Apache-2.0 (v0.8.0)
- [x] **Spanish + English** `nu-es` (female), quality and lite, Apache-2.0 (v0.8.0)
- [x] **`nu-10` M updated** with the longer joint stage of the distillation (joint 80k steps, UTMOS +0.4), Apache-2.0 (v0.9.1)
- [ ] **Model updates with the longer joint stage** for the other models (`nu-10` S next, then `nu-en` and the other pairs)
- [x] **Thai + English** `nu-th` (female), quality and lite, Apache-2.0 (v0.10.0)
- [ ] **French + English** (Python front-end done)
- [ ] **German + English** (Python front-end done)
- [ ] **Italian + English** (Python front-end done)
- [ ] **Turkish + English** (Python front-end done)
- [ ] **Russian + English** (Python front-end done)
- [ ] **Polish + English** (Python front-end done)
- [ ] **Arabic + English** (Python front-end done; vowel restoration about 86% of words)
- [ ] **Finnish + English** (Python front-end done)
- [ ] **Greek + English** (Python front-end done)
- [ ] **Malay + English** (Python front-end done)
- [ ] **Tagalog (Filipino) + English** (Python front-end done)
- [ ] **Swahili + English** (front-end done in Python and on the device)
- [ ] **Dutch + English** (Python front-end done)
- [ ] **Swedish + English** (Python front-end done)
- [ ] **Norwegian + English** (Python front-end done)
- [ ] User pronunciation dictionary
- [ ] Fix the weak word-initial *r* of the Japanese voice and read digits in English sentences in English (ko, zh, ja)
