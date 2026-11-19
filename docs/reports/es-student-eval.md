# Spanish + English student evaluation (v0.8.0)

The two models released in v0.8.0 for Spanish: the Spanish + English voice `nu-es` (female, about 40, Spanish) as a quality model M (preset `M-vocos-p-es-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-es-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `es-en` (vocabulary 138: the 107 tokens of v2 plus 31 Spanish tokens: vowels, stressed vowels, glides and consonants, dialect-neutral: `th` and `s`, `ll` and `y` stay distinct). The teacher `es_nues` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-es` only (48,336 sentences: 21,940 Spanish, 7,155 Spanish with English words and 19,241 English, read by the same voice), so the models are Apache-2.0. The students were distilled with the standard chain (front 10k, decoder 30k, joint 20k steps on a pack of 20,000 teacher renders).

Each int8 file renders three out-of-domain sets of 50 sentences (none in the training text: no sentence of either set, and no run of 8 words, occurs in it) with the C runtime on a PC (`runtime/build/vtts_say --lang es` with the English lexicon; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_es` | Spanish (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `es` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_es` | Spanish with English terms and names ("El deadline del proyecto es el 20/11/2026.") | Whisper large-v3, `es` |

An es-en model has one text mode, `es`. Since v0.8.0 the front-end decides the language of each sentence first ([pronunciation rules](../frontend/pronunciation-rules.md#language-of-a-sentence)): a whole English sentence is read in English (numbers included), and inside a Spanish sentence each Latin word is tagged Spanish or English. `ood_en` is rendered with `--lang es`.

The same 50 Spanish and 50 mixed sentences were also synthesized by VoxCPM2 with the voice `nu-es` (`scripts/data/synth_voxcpm.py --voice nu-es`) and scored the same way.

## Results

| Model | Spanish CER / WER | English CER / WER | Mixed CER / WER | UTMOS (es / en / mixed) |
|---|---|---|---|---|
| `nu-es` M | 0.019 / **0.034** | 0.020 / **0.031** | **0.006** / **0.023** | **2.83 / 3.07 / 2.87** |
| `nu-es` S | **0.017** / **0.034** | **0.019** / **0.031** | 0.009 / 0.040 | 2.54 / 2.81 / 2.50 |
| VoxCPM2 `nu-es` (reference voice) | 0.020 / 0.028 | — | 0.037 / 0.064 | 3.50 / — / 3.57 |

Without the `numbers` group (10 of the 50 sentences per set):

| System | `ood_es` CER | `mixed_es` CER |
|---|---:|---:|
| VoxCPM2 `nu-es` (reference) | 0.000 | 0.005 |
| `nu-es` M | 0.008 | 0.005 |
| `nu-es` S | 0.006 | 0.010 |

- **Spanish:** both models are at the level of the reference voice (0.017–0.019 against 0.020). The numbers group is the reference's weak spot again (raw digits: "3.er piso" → "3. Puntuer Piso", "15/12/2026" written with dashes); for the students the errors there are the ASR's grouping of a phone number ("600 123 456" → "6001-23456", CER 0.49 for that clip). Without numbers, a few words: "noche" → "noción", "coche" → "COSIC" (M), "llame a mi madre" → "ya me animaré" (S).
- **Mixed:** 0.006 (M) and 0.009 (S), below the reference voice (0.037, numbers again). The English terms are read correctly (deadline, Wi-Fi, YouTube, livestream, laptop); the only clear error is "TikTok" heard as "KiteTop" (M).
- **English:** 0.019–0.020, the same as the other pairs. Most of the remaining CER is "9:30" written "9.30" by the ASR, plus names (WhatsApp, Nguyen).
- **UTMOS:** M is about 0.3 above S, 0.7 below the reference voice.

## English sentences: sentence-level language decision

Word by word, 21% of the words of `ood_en` fit Spanish spelling and were read as Spanish. The same int8 files, `vtts_say --lang es`, Whisper large-v3, word tags only (the v0.7.0 runtime) → sentence decision (v0.8.0):

| Model | English CER | English WER |
|---|---|---|
| `nu-es` M | 0.056 → **0.020** | 0.104 → **0.031** |
| `nu-es` S | 0.064 → **0.019** | 0.123 → **0.031** |

No Spanish or mixed sentence changes (same ids, so the same audio).

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang es`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Spanish, mixed and English) were decoded again and transcribed with Whisper large-v3: CER 0 for 12 of them, the others 0.010–0.021 ("ESP32" heard as "SP32" in the Spanish intro, "envía" as "envíe" with S, "light" as "lights" with M). None is broken. The ESP32-P4 output matches `vtts_say` on a PC (correlation ≥ 0.998, SNR 24–67 dB).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.21 / 0.06–0.11 s | 0.26–0.29 / 0.15–0.28 s |
| ESP32-S3 | 0.41–0.46 / 0.20–0.39 s | 0.68–0.73 / 0.32–0.71 s |

The ESP32-S3 with two cores gave the ESP32-P4 output for 12 of the 16 clips; see [performance.md](performance.md#indonesian--english-hindi--english-and-spanish--english-v080).

Raw results: `reports/eval/esen-es-{M,S}-{ood_es,ood_en,mixed_es}.json`, `reports/eval/esen-es-{M,S}-ood_en-wordtags.json` and `reports/eval/voxcpm2-nu-es-{ood_es,mixed_es}.json` (not in the repository).
