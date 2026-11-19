# Portuguese (Brazil) + English student evaluation (v0.7.0)

The two models released in v0.7.0: the Brazilian Portuguese + English voice `nu-pt` (female, about 40, Brazilian Portuguese) as a quality model M (preset `M-vocos-p-pt-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-pt-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `pt-en` (vocabulary 150: the 107 tokens of v2 plus 43 Portuguese phoneme tokens: oral, stressed and nasal vowels, glides and consonants). The teacher `pt_nupt` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-pt` only (45,191 sentences: 19,583 Brazilian Portuguese, 6,367 Portuguese with English words and 19,241 English, read by the same voice), so the models are Apache-2.0. The students were distilled with the standard chain (front 10k, decoder 30k, joint 20k steps on a pack of 20,000 teacher renders).

Each int8 file renders three out-of-domain sets of 50 sentences (none in the training text: the training corpus is Wikipedia text without digits plus code-switching templates; no eval sentence occurs in it) with the C runtime on a PC (`runtime/build/vtts_say --lang pt` with the English lexicon; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_pt` | Brazilian Portuguese (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `pt` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_pt` | Portuguese with English terms and names ("O sinal do Wi-Fi está fraco, aproxime um pouco o router.") | Whisper large-v3, `pt` |

A pt-en model has one text mode, `pt`: English sentences are read through the same mode (each Latin word is tagged Portuguese or English, below), so `ood_en` is rendered with `--lang pt`. `vtts_say --lang en` is refused for pt-en models.

The same 50 Portuguese and 50 mixed sentences were also synthesized by VoxCPM2 with the voice `nu-pt` (the audio the teacher learned from; `scripts/data/synth_voxcpm.py --voice nu-pt`) and scored the same way.

## Results

| Model | Portuguese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (pt / en / mixed) |
|---|---|---|---|---|
| `nu-pt` M | **0.008** / **0.022** | 0.089 / 0.166 | 0.026 / 0.059 | 2.36 / 2.71 / 2.54 |
| `nu-pt` S | 0.019 / 0.045 | **0.080** / **0.133** | **0.022** / 0.063 | **2.63 / 2.69 / 2.69** |
| VoxCPM2 `nu-pt` (reference voice) | 0.044 / 0.063 | — | 0.044 / 0.088 | 3.99 / — / 3.93 |

Without the `numbers` group (10 of the 50 sentences per set):

| System | `ood_pt` CER | `mixed_pt` CER |
|---|---:|---:|
| VoxCPM2 `nu-pt` (reference) | 0.001 | 0.016 |
| `nu-pt` M | 0.005 | 0.027 |
| `nu-pt` S | 0.013 | 0.023 |

- **Portuguese:** M reaches a CER of 0.008, the lowest main-language CER of the released pairs (different languages and ASR, so only roughly comparable). Most of what is left is the ASR's spoken style ("pra" for "para") and phone numbers grouped differently. The reference voice scores worse than the students only because VoxCPM2 gets raw digits wrong ("R$ 1.250,00", "15h45", "2.500.000"; numbers group CER 0.20) while the students read them through the pt normalizer; on the other groups it is at 0.001.
- **Mixed:** both models are within about 0.01 of the reference voice. The English words are mostly read correctly (Wi-Fi, Netflix, Bluetooth, Spotify, PowerPoint, backup, deadline, smartwatch); the weak ones are listed below.
- **English:** 0.080–0.089, about four times the other pairs (0.019–0.023). This is a front-end issue, not the voice (next section).
- **UTMOS:** S scores higher than M on Portuguese (2.63 against 2.36), the reverse of the other pairs. Both are about 1.3–1.6 points below the reference voice, the usual gap for students this small.

## English sentences in the pt mode

Portuguese is written in the same letters as English, so the pt mode tags each Latin word by rules (`vtts.frontend.latin`, the same in C): a word with Portuguese letters or in the Portuguese word list is Portuguese, a word in the English list or in camel case is English, and any other word whose spelling fits Portuguese is read as Portuguese. Inside a Portuguese sentence this works well (the mixed set). In a whole English sentence, 81 of the 484 words of `ood_en` (17%) fit Portuguese spelling and are read as Portuguese: short function words (I, a, an, am, me, so, no, can, do) and common words (time, main, temperature, degrees, minutes, heater, oven, fan, medium, total, usual). Whisper then hears "I have turned on the fan" as "You have turned on the phone", and in one long sentence switches to Portuguese altogether. With digits the numbers group is worst (CER 0.20 M, 0.22 S): numbers are always read in Portuguese, as in the other single-mode pairs ("28 degrees" → vinte e oito), and "$42.50" / "1,250" follow Portuguese decimal and thousands separators.

The fix is in the front-end, not the model: the students were trained on English sentences tokenized in English, so an English text mode (or a sentence-level language decision) for the Latin-script pairs would read these sentences as the model learned them. Until then, use pt-en models for Portuguese and Portuguese-with-English text; whole English sentences are understandable but accented in places.

## Where the errors are

- **Names that fit Portuguese spelling** inside mixed sentences are read the Portuguese way: "Elon Musk" → "O aluno nosso" (S), "router" → "Luther"/"Rudder", "gym" → "dia em" (M), "livestream" → "Westin" (M).
- **Similar-sounding words**, more on S: "Ana mora em Belo Horizonte" → "A namorada ainda é horizonte" (S), "trem" → "tempo" (S), "domingos" → "domínios" (S), "Quer ver um show" → "Kevin show" (M).
- **Dates and phone numbers:** "15/12/2026 às 9h30" is read as a full date (quinze de dezembro de dois mil e vinte e seis) and the ASR writes "21h30" or "2020" for S and M once each; "(11) 98765-4321" is regrouped by the ASR.

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang pt`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Portuguese, mixed and English) were decoded again and transcribed with Whisper large-v3: CER 0.014 (M) and 0.009 (S) on average over the six Portuguese and mixed clips, the worst 0.050 (M intro: "ESP32", read with Portuguese letter names, heard as "SP32"); the English clips score 0–0.09, again only for "ESP32". None is broken. The ESP32-P4 output matches `vtts_say` on a PC (correlation ≥ 0.9993, SNR 28–57 dB), and the ESP32-S3 with two cores gives the ESP32-P4 output.

The English intro sample is "This text-to-speech voice runs entirely on the ESP32 microcontroller." instead of the "Hello! I am a text-to-speech voice ..." of the other pairs: "I", "am", "a" and "an" fit Portuguese spelling and are read as Portuguese (above), and Whisper heard the start of that sentence as "Call out, you have" (M, CER 0.19).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.21 / 0.06–0.12 s | 0.27–0.29 / 0.13–0.29 s |
| ESP32-S3 | 0.41–0.45 / 0.21–0.39 s | 0.67–0.71 / 0.28–0.73 s |

Details in [performance.md](performance.md#portuguese-brazil--english-v070).

Raw results: `reports/eval/pten-pt-{M,S}-{ood_pt,ood_en,mixed_pt}.json` and `reports/eval/voxcpm2-nu-pt-{ood_pt,mixed_pt}.json` (not in the repository).
