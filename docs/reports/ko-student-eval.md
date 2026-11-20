# Korean + English student evaluation (v0.5.0)

The two models released in v0.5.0: the Korean + English voice `nu-ko` (female, about 40, Seoul standard speech) as a quality model M (preset `M-vocos-p-ko-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-ko-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `ko-en` (vocabulary 153: the 107 tokens of v2 plus 46 Korean onset, vowel and coda tokens). The teacher `ko_nuko` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-ko` only (about 43,600 sentences: Korean, Korean with English words, and English read by the same voice), so the models are Apache-2.0.

Each int8 file renders three out-of-domain sets of 50 sentences (none in the training text) with the C runtime on a PC (`runtime/build/vtts_say --lang ko` with the English lexicon blob; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_ko` | Korean (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `ko` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_ko` | Korean with English terms and names ("사진을 Google Drive에 백업했습니다.") | Whisper large-v3, `ko` |

Korean CER counts Hangul syllables (and Latin letters) with spaces removed, after the Korean normalizer has spelled out numbers in both the reference and the transcript (see `vtts.eval.cer`); Korean WER counts space-separated words (어절), so it also counts spacing differences and is not comparable with English WER.

A ko-en model has one text mode, `ko`: English sentences are read through the same mode (Latin words go to the English front-end), so `ood_en` is rendered with `--lang ko`. `vtts_say --lang en` is refused for ko-en models.

## Results

| Model | Korean CER / WER | English CER / WER | Mixed CER: text / Hangul only | UTMOS (ko / en / mixed) |
|---|---|---|---|---|
| `nu-ko` M | **0.021** / 0.088 | 0.023 / 0.035 | 0.303 / **0.024** | 2.75 / 3.39 / 2.75 |
| `nu-ko` S | 0.045 / 0.130 | 0.023 / 0.027 | 0.359 / 0.055 | 2.68 / 3.18 / 2.65 |
| VoxCPM2 `nu-ko` (reference voice, the teacher's data) | — | — | 0.372 / 0.016 | — / — / 3.92 |

- **Korean:** M reads Korean about as well as the Vietnamese models read Vietnamese (CER 0.014–0.024). S has twice the error rate, a third of it from two sentences (a phone number and a subway station name, below).
- **English:** both models are as intelligible in English as the vi-en voices (0.008–0.015), apart from numbers (below). Device prompts and long sentences score 0–0.003.
- **Mixed:** the plain CER (0.30–0.36) does not measure the voice; the Hangul-only CER does (next section). On it M is within 0.01 of the reference voice and S is 0.04 behind.

## `nu-ko` S update (v0.10.3)

v0.10.3 replaces the lite model S with a re-distillation that uses the improved recipe: the same teacher (`ko_nuko`), the same presets and the same stages except a **longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**). Size (0.83M parameters, 1.2 MB), speed, token set and text mode are unchanged. The released v0.5.0 models and the new ones were rendered again with the current C runtime (`vtts_say --lang ko`) and scored with the same sets and pipeline (Whisper large-v3, UTMOS; mixed set: plain and Hangul-only CER, [below](#how-the-mixed-set-is-scored)).

| Model | Korean CER / WER | English CER / WER | Mixed CER: text / Hangul only | UTMOS (ko / en / mixed) |
|---|---|---|---|---|
| S v0.5.0 (joint 20k) | 0.045 / 0.130 | 0.024 / 0.029 | 0.361 / 0.056 | 2.68 / 3.18 / 2.65 |
| **S v0.10.3 (joint 80k)** | **0.026 / 0.099** | **0.018 / 0.024** | **0.314 / 0.044** | **3.18 / 3.54 / 3.06** |
| M v0.5.0 (joint 20k, kept) | 0.021 / 0.088 | 0.023 / 0.035 | 0.314 / 0.026 | 2.75 / 3.39 / 2.76 |
| M joint 80k (not released) | 0.035 / 0.127 | 0.028 / 0.039 | 0.352 / 0.043 | 3.14 / 3.87 / 3.33 |

- **S:** every error rate drops (Korean CER 0.045 → 0.026, Hangul-only mixed 0.056 → 0.044) and UTMOS rises by 0.36–0.50; the new S is more natural than the v0.5.0 M on all three sets, though the M still reads Korean more accurately. Fixed: 지하철역 (was 치아 저력), 조수빈, the phone number; new errors are single syllables (개 → 회, 딸 → 날).
- **M stays v0.5.0.** The M of the same re-distillation is much more natural (UTMOS +0.39 to +0.57) but reads Korean less accurately (CER 0.021 → 0.035, Hangul-only mixed 0.026 → 0.043: 곧 따뜻해질 → 곱다 뜨뜻해질, 한강은 → 한다는, a dropped digit in the phone number). The release rule is "UTMOS better and no CER worse by more than 0.003", so the M was not released.

On the chip the new S runs at the speed of the v0.5.0 S (ESP32-P4 RTF 0.17–0.19, speech starts after 0.06–0.11 s; ESP32-S3 0.30–0.33). The eight `nu-ko` Lite clips of the website are ESP32-P4 dumps of the new S, 64 kbps MP3; Whisper large-v3: Hangul-only CER 0 on four of the six Korean and mixed clips and 0.023–0.029 on the other two (내일 heard as 매일), English 0 and 0.011 ([performance.md](performance.md#nu-zh-m-and-nu-ko-s-update-v0103)). The Quality clips are still the v0.5.0 M.

Raw results: `ko-{M,S}-{old,new}-{ood_ko,mixed_ko,ood_en}.json` (not in the repository).

## How the mixed set is scored

Whisper, forced to Korean, writes most English words in Hangul: "Google Drive" becomes 구글 드라이브, "Netflix" 넷플릭스, "iPhone" 아이폰. Against a reference written with Latin letters each such word counts as a wrong word, so a perfect reading of "사진을 Google Drive에 백업했습니다." scores CER 0.52. The plain CER of the mixed set is therefore mostly a measure of how often Whisper transliterates, not of the voice.

Two checks show this:

1. **The reference voice scores worse than the students.** The same 50 sentences synthesized by VoxCPM2 with the voice `nu-ko` (the audio the teacher learned from; `scripts/data/synth_voxcpm.py --voice nu-ko`, then scored the same way) get a plain CER of 0.372, higher than M (0.303) and S (0.359), although VoxCPM2 is by far the more intelligible system (UTMOS 3.92). Whisper keeps English words in Latin letters a little more often for the students, which lowers their plain CER.
2. **Hangul-only CER.** `vtts.eval.cer.main_script_cer` aligns the normalized reference and transcript and counts only the errors on the reference's Hangul characters: a substituted or missing syllable, or a syllable inserted between two Hangul characters. The English words and whatever Whisper writes in their place are skipped; numbers are spelled out in Hangul by the normalizer, so they count. The denominator is the number of Hangul characters in the reference. On the Korean-only set this equals the plain CER (0.021 / 0.045).

| System | Plain CER | Hangul-only CER |
|---|---:|---:|
| VoxCPM2 `nu-ko` (reference) | 0.372 | 0.016 |
| `nu-ko` M | 0.303 | 0.024 |
| `nu-ko` S | 0.359 | 0.055 |

`scripts/eval/mixed_cer.py --lang ko --ref-voice <reference report> <student reports>` prints both. It also prints the CER of each student transcript against the reference voice's transcript (M 0.182, S 0.170); that number is not useful here, because Whisper switches between Latin and Hangul spellings of the same English word from one clip to the next.

The Hangul-only CER does not judge the English words themselves. Listening and the transcripts show that most are read correctly (Zoom, PowerPoint, Wi-Fi, Netflix, YouTube Music, iPhone), with a few weak ones:

- **"Bluetooth"** is read badly by both models, more so at the start of a sentence (transcribed 부트, 부츠, 부유튿). "Google Meet" is also unclear. Writing them in Hangul (블루투스) works.
- S drops or blurs the Korean particle after an English word more often than M ("이 Wi-Fi는 password가 필요해요?" → "EBIFI에는 파솔카 필요해요").

## Where the errors are

- **Numbers in English sentences are read in Korean.** The ko text mode reads every number in Korean, also inside an English sentence ("The meeting starts at 9:30" → 아홉 시 삼십 분). This gives the English `numbers` group its CER (0.096 M, 0.113 S; "7 kilometers" heard as "2 kilometers"); every other English group is at most 0.026. Write numbers as words in English text.
- **Number formats in the transcript:** "010-1234-5678" transcribed as "010-12345678" is scored as a different reading (0.52 for that S clip) although the digits are all there; "9:30" as "9.30" likewise.
- **Similar-sounding syllables**, mostly on S: 지하철역 → 치아 저력, 최영호 → 최현우, 주말에 → 중월에 (M).

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang ko`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Korean, mixed and English) were decoded again and transcribed with Whisper large-v3: Hangul-only CER 0.006 on average over the 12 Korean and mixed clips (worst 0.029: 내일 heard as 매일), CER 0 on three of the four English clips; the fourth (M, "... turn on the porch light?") scores 0.09 because Whisper appends "for you"; the last 1.6 s transcribed alone end with "porch light(s)". None is broken. The ESP32-P4 output matches `vtts_say` on a PC (SNR 39–60 dB on the single-sentence clips).

The sample sentences avoid "Bluetooth" and "Google Meet" (see above); they show Zoom, PowerPoint, Wi-Fi and Netflix inside Korean sentences.

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.18 / 0.07–0.10 s | 0.25–0.26 / 0.16–0.27 s |
| ESP32-S3 | 0.29–0.30 / 0.18–0.26 s | 0.48–0.49 / 0.27–0.47 s |

On the ESP32-S3 with two cores (the default) the output of both models is not deterministic for these models (M as with vi-en, and now S too); `cores 1` gives the same output as the ESP32-P4. Details in [performance.md](performance.md#korean--english-v050).

Raw results: `reports/eval/koen-ko-{M,S}-{ood_ko,ood_en,mixed_ko}.json` and `reports/eval/voxcpm2-nu-ko-mixed_ko.json` (not in the repository).
