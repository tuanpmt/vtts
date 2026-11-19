# Roadmap

vtts ships **bilingual voices: one main language + English**, with code-switching. Every released model covers one pair; each new pair gets one designed voice and its own release. Plan and reasoning: [design/plans/2026-11-18-roadmap-bilingual.md](design/plans/2026-11-18-roadmap-bilingual.md). Release history: [CHANGELOG.md](../CHANGELOG.md).

- [x] English front-end in Python and on the device (C, parity-tested), per-word language tagging
- [x] Synthesized training data for the bilingual voices `nam-1` and `nu-10`
- [x] Faster runtime: the quality model runs on the ESP32-S3 too
- [x] **Vietnamese + English** `nam-1` (male) and `nu-10` (female), quality and lite, Apache-2.0 (v0.4.0)
- [x] **Korean + English** `nu-ko` (female), quality and lite, Apache-2.0 (v0.5.0)
- [x] **Chinese (Mandarin) + English** `nu-zh` (female), quality and lite, Apache-2.0 (v0.5.0)
- [x] **Japanese + English** `nu-ja` (female), quality and lite, Apache-2.0 (v0.6.0)
- [ ] **Spanish + English** (Python front-end done)
- [ ] **Portuguese (Brazil) + English** (Python front-end done)
- [ ] **Indonesian + English** (Python front-end done)
- [ ] **Hindi + English** (Python front-end done)
- [ ] **Thai + English** (Python front-end done)
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
