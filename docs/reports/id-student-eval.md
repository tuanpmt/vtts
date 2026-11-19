# Indonesian + English student evaluation (v0.8.0)

The two models released in v0.8.0 for Indonesian: the Indonesian + English voice `nu-id` (female, about 40, Indonesian) as a quality model M (preset `M-vocos-p-id-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-id-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `id-en` (vocabulary 141: the 107 tokens of v2 plus 34 Indonesian tokens: vowels with the schwa, stressed vowels and consonants with the glottal stop). The teacher `id_nuid` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-id` only (45,857 sentences: 20,025 Indonesian, 6,591 Indonesian with English words and 19,241 English, read by the same voice), so the models are Apache-2.0. The students were distilled with the standard chain (front 10k, decoder 30k, joint 20k steps on a pack of 20,000 teacher renders).

Each int8 file renders three out-of-domain sets of 50 sentences (none in the training text: no sentence of either set, and no run of 8 words, occurs in it) with the C runtime on a PC (`runtime/build/vtts_say --lang id` with the English lexicon; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_id` | Indonesian (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `id` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_id` | Indonesian with English terms and names ("Sinyal Wi-Fi lemah sekali, coba dekatkan router-nya.") | Whisper large-v3, `id` |

An id-en model has one text mode, `id`. Since v0.8.0 the front-end decides the language of each sentence first ([pronunciation rules](../frontend/pronunciation-rules.md#language-of-a-sentence)): a whole English sentence is read in English (numbers included), and inside an Indonesian sentence each Latin word is tagged Indonesian or English. `ood_en` is therefore rendered with `--lang id`, as a user would type it.

The same 50 Indonesian and 50 mixed sentences were also synthesized by VoxCPM2 with the voice `nu-id` (the audio the teacher learned from; `scripts/data/synth_voxcpm.py --voice nu-id`) and scored the same way.

## Results

| Model | Indonesian CER / WER | English CER / WER | Mixed CER / WER | UTMOS (id / en / mixed) |
|---|---|---|---|---|
| `nu-id` M | **0.011** / 0.023 | **0.022** / **0.031** | 0.018 / 0.077 | **2.42 / 3.05 / 2.57** |
| `nu-id` S | **0.011** / **0.021** | 0.059 / 0.074 | **0.015** / **0.063** | 2.14 / 2.63 / 2.25 |
| VoxCPM2 `nu-id` (reference voice) | 0.023 / 0.034 | — | 0.042 / 0.105 | 3.07 / — / 3.22 |

Without the `numbers` group (10 of the 50 sentences per set):

| System | `ood_id` CER | `mixed_id` CER |
|---|---:|---:|
| VoxCPM2 `nu-id` (reference) | 0.000 | 0.009 |
| `nu-id` M | 0.002 | 0.018 |
| `nu-id` S | 0.003 | 0.014 |

- **Indonesian:** 0.011 for both models, and 0.002–0.003 without the numbers. What is left in the numbers group is mostly spelling: Whisper writes "Rp 1.250.000" for "Rp1.250.000" (CER 0.17 for one space) and "15 Desember 2020 6.30" for "15/12/2026 pukul 09.30". The reference voice scores lower only because VoxCPM2 misreads raw digits ("Rp1.250.000", "2.500.000" heard as "2.500. Sol kosong ..."; numbers group CER 0.10), while the students read them through the id normalizer.
- **Mixed:** below the reference voice, which again loses on raw numbers (0.009 without them). The English words are read correctly (Bluetooth, Spotify, WhatsApp, TikTok, PowerPoint, smart home); most remaining errors are spelling choices of the ASR (notifikasi, manajer, tim, piknik, Macbook) and a few first consonants ("Speaker" heard as "Stiker", "Putar" as "Kutar", "Rina" as "Prina", M).
- **English:** M 0.022 (0.003 without the numbers group), close to the other pairs; S 0.059. Two S clips explain most of it: Whisper, forced to English, wrote an Indonesian translation of the accented audio ("Your coffee will be ready in a moment." → "Coffee Anda akan siap sebentar.", and one long sentence), as it did once for M ("Your package will arrive on Tuesday" → "Package Anda akan tiba pada hari ..."). The words themselves are read in English (next section); the accent is the voice's.
- **UTMOS:** M is 0.3–0.4 above S on all three sets; both are 0.6–0.9 below the reference voice, a smaller gap than for most pairs.

## English sentences: sentence-level language decision

Indonesian is written in the same letters as English, so word by word 18% of the words of `ood_en` (I, a, am, time, minutes, ...) fit Indonesian spelling and were read as Indonesian. The sentence-level decision added after v0.7.0 reads such sentences in English. The same int8 files, `vtts_say --lang id`, Whisper large-v3, word tags only (the v0.7.0 runtime) → sentence decision (v0.8.0):

| Model | English CER | English WER | `long` group CER |
|---|---|---|---|
| `nu-id` M | 0.070 → **0.022** | 0.110 → **0.031** | 0.088 → 0.000 |
| `nu-id` S | 0.106 → **0.059** | 0.153 → **0.074** | 0.178 → 0.097 |

No Indonesian or mixed sentence changes (same ids, so the same audio).

## Where the errors are

- **Numbers in the ASR's spelling:** "Rp1.250.000" → "Rp 1.250.000", "pukul 09.30" written differently; "9:30" in English sentences is written "9.30" (CER 0.28 for that clip).
- **First consonants of a few words**, more on M than S in the mixed set: "Speaker" → "Stiker", "Putar" → "Kutar", "Rina" → "Prina", "Sri" → "Si".
- **English words with Indonesian spellings:** "notification" → notifikasi, "picnic" → piknik, "stroberi" → strawberry: the ASR's choice, the reading is right.

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang id`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Indonesian, mixed and English) were decoded again and transcribed with Whisper large-v3: CER 0 for 15 of them; the M intro scores 0.008 ("ESP32" heard as "ISP32"). None is broken. The English samples ("Hello! I am a text-to-speech voice ...") are read in English by the sentence decision. The ESP32-P4 output matches `vtts_say` on a PC (correlation ≥ 0.9997, SNR 32–78 dB); the ESP32-S3 with two cores gave the ESP32-P4 output for 15 of the 16 clips (the 16th differs for 0.25 s; see performance.md).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.20 / 0.07–0.12 s | 0.26–0.28 / 0.17–0.28 s |
| ESP32-S3 | 0.40–0.44 / 0.23–0.39 s | 0.67–0.70 / 0.38–0.72 s |

Details in [performance.md](performance.md#indonesian--english-hindi--english-and-spanish--english-v080).

Raw results: `reports/eval/iden-id-{M,S}-{ood_id,ood_en,mixed_id}.json`, `reports/eval/iden-id-{M,S}-ood_en-wordtags.json` and `reports/eval/voxcpm2-nu-id-{ood_id,mixed_id}.json` (not in the repository).
