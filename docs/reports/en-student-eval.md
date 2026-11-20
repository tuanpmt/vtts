# English student evaluation (v0.9.0)

The two models released in v0.9.0 for the first English-only voice, `nu-en` (female, American English, a VoxCPM2 designed voice): a quality model M (preset `M-vocos-p-bi`, 1.83M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-bi`, 0.82M parameters, 1.2 MB int8). They use the existing token set `vi-en` (107 tokens; only the English ARPAbet part is trained), so no new front-end was needed. The teacher `en_nuen` was trained for 60k steps on speech synthesized with VoxCPM2 from the voice `nu-en` only (19,241 English sentences, about 30 h), starting from the `nu-10` teacher (itself trained from random initialization on VoxCPM2 audio), so the models are Apache-2.0. The students were distilled with the standard chain (front 10k, decoder 30k, joint 20k steps).

The files record the text mode `en` in the optional dim `text_mode` ([model format](../model-format.md#optional-dims)), so the firmware and `runtime/build/vtts_say` start them in English instead of the vi-en default `vi`. Use them in `lang en` only: Vietnamese text was not in the training data.

Each int8 file renders two out-of-domain English sets of 50 sentences with the C runtime on a PC (`runtime/build/vtts_say --lang en` with the English lexicon; the same code path and output as the chip), then `scripts/eval/eval_dir.py --lang en --asr openai/whisper-large-v3` scores them:

| Set | Content |
|---|---|
| `ood_en` | Device prompts, numbers, names, questions, long sentences (the English set of every pair) |
| `ood_en2` (new) | Numbers, dates and times, short commands, units and money, abbreviations ("The ticket costs $19.99.", "Wake me up at 6:20 tomorrow.", "Dr. Brown will see you on Monday.") |

No sentence of either set, and no run of 6 words, occurs in the English training text. The same sets were rendered with the bilingual `nu-10` models (v0.4.0, `--lang en`) and synthesized by VoxCPM2 with the voice `nu-en` (`scripts/data/synth_voxcpm.py --voice nu-en`), the reference voice the students were trained from.

## Results

| Model | `ood_en` CER / WER | `ood_en2` CER / WER | UTMOS (ood_en / ood_en2) |
|---|---|---|---|
| `nu-en` M | 0.014 / 0.018 | 0.034 / 0.053 | 2.88 / 3.00 |
| `nu-en` S | 0.015 / 0.022 | **0.027** / **0.043** | 3.00 / 3.08 |
| `nu-10` M (vi-en, `lang en`) | **0.008** / **0.010** | 0.033 / **0.043** | **3.44 / 3.59** |
| `nu-10` S (vi-en, `lang en`) | 0.011 / 0.018 | 0.035 / 0.046 | 3.26 / 3.35 |
| VoxCPM2 `nu-en` (reference voice) | 0.010 / 0.014 | 0.045 / 0.055 | 4.24 / 4.24 |

CER per group of `ood_en2` (10 sentences each):

| System | numbers | dates and times | commands | units and money | abbreviations |
|---|---:|---:|---:|---:|---:|
| `nu-en` M | 0.022 | 0.086 | 0.000 | 0.014 | 0.027 |
| `nu-en` S | 0.020 | 0.055 | 0.008 | 0.008 | 0.032 |
| `nu-10` M | 0.035 | 0.072 | 0.034 | 0.008 | 0.005 |
| VoxCPM2 `nu-en` | 0.035 | 0.082 | 0.000 | 0.033 | 0.054 |

- **Intelligibility** is at the level of the reference voice and of `nu-10`'s English. Most of the remaining CER is how Whisper writes what was read correctly: "9:30" as "9.30", "6:45" as "6.45", "5:48" as "548", "64 dollars and 20 cents" as "$64.20"; every system, the reference included, pays for these (the dates and times group is 0.06–0.09 for all). Real reading errors are few: "Nguyen" (heard as "me in" / "let me enter"), "NASA", which the front-end spells as letters, "4 degrees" heard as "40 degrees" (M), and an occasional dropped or added short word.
- **Naturalness** is the weak point of this first release: UTMOS 2.88–3.08, about 0.4–0.6 below the English of the bilingual `nu-10` voice and 1.2 below the reference voice. S scores slightly above M here. An improved distillation recipe (a longer joint stage) is being applied, and `nu-en` will get an updated model soon.
- **Short first sentence:** "Hello!" before a longer sentence is short and quiet; Whisper drops it in the intro sentence of the website for both models (CER 0.05–0.06 for that clip).

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command; the models start in `lang en`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models) were decoded again and transcribed with Whisper large-v3: CER 0 for 12 of them; the other four are the intro ("Hello!" not transcribed, and "ESP32" heard as "ESP3 to" with M; CER 0.05–0.06) and the date sentence ("9:30" written "9.30", CER 0.16 for both models). None is broken. The ESP32-P4 output matches `vtts_say` on a PC (same length for all 16 clips, correlation ≥ 0.996, SNR 21–44 dB).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.21 / 0.07–0.14 s | 0.27–0.29 / 0.17–0.35 s |
| ESP32-S3 | 0.41–0.46 / not measured | 0.69–0.73 / not measured |

On the ESP32-S3 only `bench` was run for this release (two cores, the default); its dumps were not compared with the ESP32-P4. See [performance.md](performance.md#english-v090).

Raw results: `reports/eval/nuen-{M,S}-{ood_en,ood_en2}.json`, `reports/eval/nu10-{M,S}-{ood_en,ood_en2}.json` and `reports/eval/voxcpm2-nu-en-{ood_en,ood_en2}.json` (not in the repository).
