# Thai + English student evaluation (v0.10.0)

The two models released in v0.10.0 for Thai: the Thai + English voice `nu-th` (female, Thai) as a quality model M (preset `M-vocos-p-th-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-th-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `th-en` (vocabulary 162: the 107 tokens of v2 plus 55 Thai tokens: 21 initials with the glottal stop, 21 vowels, 8 finals and 5 tones). The teacher `th_nuth` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-th` only (55,555 sentences, about 97 h: 27,635 Thai, 8,679 Thai with English words and 19,241 English, read by the same voice), so the models are Apache-2.0. The students were distilled with the standard chain (front 10k, decoder 30k, joint 20k steps on a pack of 20,000 teacher renders).

Each int8 file renders three out-of-domain sets of 50 sentences with the C runtime on a PC (`runtime/build/vtts_say --lang th` with the English lexicon; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_th` | Thai (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `th` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_th` | Thai with English words in Latin letters ("สัญญาณ Wi-Fi อ่อนมาก ลองย้าย router มาใกล้ ๆ") | Whisper large-v3, `th` |

`ood_th` and `mixed_th` came with the Thai front-end (10 sentences per group, as for the other pairs). Checked against the teacher's training text for this release: no sentence occurs in it; one `ood_th` sentence shared an eight-word run with it ("ดอยอินทนนท์เป็นยอดเขาที่สูงที่สุด…") and was replaced by a new one before scoring. A th-en model has one text mode, `th`: Thai script is Thai, a Latin word is English; `ood_en` is rendered with `--lang th`.

Thai is written without spaces between words, so the CER (`vtts.eval.cer`, lang `th`) counts Thai characters with the spaces removed (Whisper's spacing is not an error), and the WER counts the words of the front-end's own word segmentation. The same 50 Thai and 50 mixed sentences were also synthesized by VoxCPM2 with the voice `nu-th` (`scripts/data/synth_voxcpm.py --voice nu-th`) and scored the same way.

## Results

| Model | Thai CER / WER | English CER / WER | Mixed CER (Thai only) | Mixed CER / WER (text) | UTMOS (th / en / mixed) |
|---|---|---|---:|---|---|
| `nu-th` M | **0.044** / 0.144 | **0.018** / **0.025** | **0.043** | 0.100 / 0.168 | **2.88** / **3.51** / **2.95** |
| `nu-th` S | 0.053 / 0.152 | 0.030 / 0.043 | 0.044 | 0.116 / 0.175 | 2.55 / 3.06 / 2.58 |
| VoxCPM2 `nu-th` (reference voice) | 0.076 / 0.115 | — | 0.022 | 0.086 / 0.124 | 3.97 / — / 4.00 |

- **Two CERs for the mixed set.** Whisper writes most English words of a Thai sentence in Thai script (Liverpool → ลิเวอร์พูล, calendar → คาเลนเดอร์), so the plain CER against the text is 0.09–0.12 for every system, the reference voice included. The Thai-only CER (`vtts.eval.cer.main_script_cer`, `scripts/eval/mixed_cer.py --lang th`) counts only the Thai characters of the text and skips the English words and what Whisper writes for them, as for Korean, Japanese and Hindi.
- **The reference voice is not a clean ceiling on `ood_th`.** VoxCPM2 misreads raw digits and dates ("5/3/2540" → "50302540"; numbers group 0.223) and, in 4 of the 50 Thai sentences, adds words after the end of the sentence. Without the numbers group:

| System | `ood_th` CER | without `numbers` |
|---|---:|---:|
| VoxCPM2 `nu-th` (reference) | 0.076 | 0.039 |
| `nu-th` M | 0.044 | 0.054 |
| `nu-th` S | 0.053 | 0.050 |

- **Thai:** about 1.3 times the reference voice's error once numbers are set aside; the students read digits, dates and times through the Thai normalizer (numbers group 0.007 M, 0.066 S). 20 (M) and 18 (S) of the 50 Thai sentences are transcribed without any error, 33 for the reference voice. The Thai WER is higher than the CER mostly because one wrong letter changes a whole word of the segmentation.
- **English:** M 0.018, S 0.030; numbers in English sentences are read in Thai, as in the other single-mode pairs ("15 percent" heard as "Zip 5%", "25 minutes" as "easy power minutes" with S), which is most of the English error.
- **UTMOS:** 2.88 / 3.51 / 2.95 for M, among the higher student scores of the released pairs; S is about 0.3–0.45 lower. The reference voice scores 3.97–4.00.

## Where the errors are

- **Tones of short particles.** The question particle ไหม (rising tone) is heard as ใหม่ ("new", low tone) in 4 of the 6 sentences with it, for both models; never for the reference voice. Questions are understandable from context, but the tone is not the written one.
- **กรุณา (please)** is read as one cluster, kru-naa, instead of ka-ru-naa: the front-end treats กร here as a true cluster. Whisper writes "กลูนา" or "กรูนา" (both models; also in the website's Zoom clip). An exception-table entry fixes it in a later front-end update.
- **Weak or swapped consonants in names and rarer words**: "ศิริราช" → "ซีริราชะ", "ม่าน" → "มณะ" (M), "ฟอก" → "ฟอบ" (S). Names are the hardest Thai group (0.083 for both models and for the reference voice).
- **English words inside Thai sentences** are read with the English front-end and are mostly right; Whisper writes them in Thai script, which the Thai-only CER does not count. Short English names are less clear than with the reference voice: Bangkok heard as "แปงคอป" / "แบนคอป", Tokyo as "ท็อคพิโย", Toyota as "ทุยวัตเทอร์" (S).

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang th`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Thai, mixed and English) were decoded again and transcribed with Whisper large-v3: Thai CER 0 on 2 (M) and 3 (S) of the 6 Thai and mixed clips, the others 0.010–0.217 (the ไหม/ใหม่ tone of the question clip, "กรุณา" in the Zoom clip, "เย็น" → "ยืน" and "เหลือ" → "เรือ" in the M news clip, "6.30 น." written as digits by Whisper); the English clips score 0 except S intro (0.169: Whisper drops the short "Hello!" and hears "ESP32" as "ESP Samsung"). None is broken (no noise, no cut, every sentence complete). The ESP32-P4 output matches `vtts_say` on a PC (16 of 16 clips the same length, correlation ≥ 0.9997, SNR 32–48 dB).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.19 / 0.07–0.13 s | 0.26–0.28 / 0.18–0.33 s |
| ESP32-S3 | 0.31–0.33 / not measured | 0.55–0.57 / not measured |

ESP32-S3 RTF from `bench` (four Thai sentences) with the current firmware (S3 dot-product kernels without `loopnez`); see [performance.md](performance.md#thai--english-v0100).

Raw results: `reports/eval/then-th-{M,S}-{ood_th,ood_en,mixed_th}.json` and `reports/eval/voxcpm2-nu-th-{ood_th,mixed_th}.json` (not in the repository).
