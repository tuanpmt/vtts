# Hindi + English student evaluation (v0.8.0)

The two models released in v0.8.0 for Hindi: the Hindi + English voice `nu-hi` (female, about 40, Hindi) as a quality model M (preset `M-vocos-p-hi-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-hi-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `hi-en` (vocabulary 157: the 107 tokens of v2 plus 50 Hindi phoneme tokens: 10 vowels, nasalization, 25 stops and nasals with the retroflex and aspirated series, flaps and the nukta consonants). The teacher `hi_nuhi` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-hi` only (48,296 sentences: 23,247 Hindi, 5,808 Hindi with English words and 19,241 English, read by the same voice), so the models are Apache-2.0. The students were distilled with the standard chain (front 10k, decoder 30k, joint 20k steps on a pack of 20,000 teacher renders).

Hindi is written in Devanagari; English words are written in Latin letters inside Hindi sentences ("Zoom पर meeting दोपहर 3:00 बजे शुरू होगी।"), as users type them. Each int8 file renders three out-of-domain sets of 50 sentences with the C runtime on a PC (`runtime/build/vtts_say --lang hi` with the English lexicon; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_hi` | Hindi (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `hi` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_hi` | Hindi with English words in Latin letters (Hinglish: "Wi-Fi का signal बहुत कमज़ोर है, router को थोड़ा पास ले आइए।") | Whisper large-v3, `hi` |

`ood_hi` and `mixed_hi` are new in this release (`eval/sets/`, 10 sentences per group, as for the other pairs); no sentence of either set and no run of 8 words occurs in the training text. An hi-en model has one text mode, `hi`: a word with a Devanagari letter is Hindi, a Latin word is English (except the units and currency words of the Hindi normalizer: km, GB, Rs). `ood_en` is rendered with `--lang hi`.

The same 50 Hindi and 50 mixed sentences were also synthesized by VoxCPM2 with the voice `nu-hi` (`scripts/data/synth_voxcpm.py --voice nu-hi`) and scored the same way.

## Results

| Model | Hindi CER / WER | English CER / WER | Mixed CER (Devanagari only) | Mixed CER / WER (text) | UTMOS (hi / en / mixed) |
|---|---|---|---:|---|---|
| `nu-hi` M | 0.094 / 0.254 | 0.053 / 0.080 | **0.054** | 0.284 / 0.309 | **2.84** / **3.09** / **2.91** |
| `nu-hi` S | **0.092** / **0.245** | **0.028** / **0.037** | 0.056 | 0.293 / 0.320 | **2.84** / 3.03 / 2.88 |
| VoxCPM2 `nu-hi` (reference voice) | 0.069 / 0.181 | — | 0.065 | 0.277 / 0.274 | 3.41 / — / 3.55 |

- **Two CERs for the mixed set.** Whisper writes most English words of a Hindi sentence in Devanagari (meeting → मीटिंग, Netflix → नेटफ्लिक्स), so the plain CER against the text is 0.28–0.29 for every system, the reference voice included. The Devanagari-only CER (`vtts.eval.cer.main_script_cer`, `scripts/eval/mixed_cer.py --lang hi`) counts only the Devanagari characters of the text and skips the English words and what Whisper writes for them, as for Korean (Hangul only) and Japanese (kana and kanji only). On it both students are at the level of the reference voice.
- **Whisper's Hindi spelling** costs every system: nukta or not (फ़ोन / फोन, ज़्यादा / ज्यादा), chandrabindu or anusvara (जाएँगे / जाएंगे), ये or ए (लीजिए / लीजिये), digits for number words. With those merged (a relaxed comparison) and without the numbers group, `ood_hi` scores 0.035 for the reference voice, 0.081 for M and 0.085 for S.

| System | `ood_hi` CER | without `numbers` | relaxed spelling, without `numbers` |
|---|---:|---:|---:|
| VoxCPM2 `nu-hi` (reference) | 0.069 | 0.043 | 0.035 |
| `nu-hi` M | 0.094 | 0.089 | 0.081 |
| `nu-hi` S | 0.092 | 0.094 | 0.085 |

- **Hindi:** about twice the reference voice's error once spelling is set aside, the highest main-language CER of the released pairs (different languages and ASR, so only roughly comparable). Most of the gap is the first word of a sentence (next section). The numbers group is better than the reference (0.114 M, 0.086 S against 0.173), because the students read digits through the hi normalizer while VoxCPM2 misreads raw dates and times ("15/12/2026 को सुबह 9:30" → "15-12-12 दौइट्स हबिस को ...").
- **English:** S 0.028 (0.010 without the numbers group), M 0.053 (0.021). Numbers are always read in Hindi, also in English sentences ("28 degrees" → अट्ठाईस degrees, heard as "at least degrees"; "$42.50" as "42,550 dollars"), as in the other single-mode pairs; without them English is close to the other pairs.
- **UTMOS:** 2.84–3.09, among the higher student scores of the released pairs, 0.6 below the reference voice.

## Where the errors are

- **The first word of a sentence.** In 28 (M) and 23 (S) of the 50 `ood_hi` sentences Whisper gets the first word wrong, against 13 for the reference voice (most of those are spelling): the first consonant is weak or heard as another one, "बैठक" → "मैं तक" / "वैटक", "राहुल" → "नाहूं", "ताजमहल आगरा" → "आज हम हलागरा", "फ़ोन Wi-Fi से" → "वो वेफाई से". The same happens less often inside sentences ("कमरे" → "कमली", M). The Indonesian models show a milder form of it ("Putar" → "Kutar").
- **Aspirated and retroflex stops** are sometimes heard unaspirated or dental (पढ़ाते, धूप → धुक, S), and names of places are the hardest group (0.12 for both models).
- **English words in Hindi sentences** are read with the English front-end and are mostly right; Whisper writes them in Devanagari with Hindi spellings (ओन्लाइन, मेटिंग), which the Devanagari-only CER does not count.

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang hi`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Hindi, mixed and English) were decoded again and transcribed with Whisper large-v3: Devanagari CER 0.013–0.21 per clip on the Hindi and mixed clips (mean 0.11 for M, 0.12 for S; the errors are the first-word and spelling effects above: "फ़ोन" heard as "वो" with M, "कमरे" as "कमली" with M, "दोपहर" as "दोखर"); the English clips score 0–0.08, the only error being "ESP32", read with Hindi letter names and digits in the Hindi mode ("ESP Tindo"). None is broken (no noise, no cut, every sentence complete). The ESP32-P4 output matches `vtts_say` on a PC (correlation ≥ 0.9995, SNR 30–42 dB).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.20 / 0.07–0.12 s | 0.27–0.28 / 0.17–0.30 s |
| ESP32-S3 | 0.40–0.45 / 0.23–0.41 s | 0.68–0.69 / 0.39–0.78 s |

The ESP32-S3 with two cores did not always give the ESP32-P4 output for hi-en; see [performance.md](performance.md#indonesian--english-hindi--english-and-spanish--english-v080).

Raw results: `reports/eval/hien-hi-{M,S}-{ood_hi,ood_en,mixed_hi}.json` and `reports/eval/voxcpm2-nu-hi-{ood_hi,mixed_hi}.json` (not in the repository).
