# Bilingual teacher evaluation

Teachers for the bilingual Vietnamese + English voices, trained on speech synthesized with VoxCPM2 (about 98 h per voice). Each checkpoint renders three out-of-domain sets that are not in the training text, 50 sentences each:

| Set | Content | ASR | Text normalization for CER/WER |
|---|---|---|---|
| `eval/sets/ood.jsonl` | Vietnamese: device prompts, numbers, names, prosody, long sentences | PhoWhisper-large | Vietnamese normalizer |
| `eval/sets/ood_en.jsonl` | English: device prompts, numbers, names, questions, long sentences | Whisper large-v3, `en` | English normalizer |
| `eval/sets/mixed.jsonl` | Vietnamese with English terms and names | Whisper large-v3, `vi` | words kept as written, numbers read in Vietnamese |

```bash
uv run python scripts/teacher/render_teacher.py --ckpt CKPT --set eval/sets/mixed.jsonl --out DIR --lang mixed
uv run python scripts/eval/eval_dir.py --system NAME --set eval/sets/mixed.jsonl --audio DIR \
  --out reports/NAME-mixed.json --lang mixed --asr openai/whisper-large-v3 --asr-language vi
```

## Results

| Voice | Step | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---:|---|---|---|---|
| `nam-1` | 100k | 0.005 / 0.013 | 0.015 / 0.029 | 0.033 / 0.066 | 3.17 / 3.82 / 3.34 |
| `nam-1` | 200k | 0.005 / 0.014 | 0.012 / 0.020 | 0.018 / 0.041 | 3.41 / 4.04 / 3.47 |
| `nu-10` | 200k | 0.002 / 0.007 | 0.012 / 0.018 | 0.019 / 0.042 | 3.67 / 4.38 / 3.83 |

For reference, the teacher of the earlier Vietnamese-only voice (trained on a recorded corpus) scored CER 0.015 and UTMOS 2.50 on the same Vietnamese set.

## Notes on `nam-1` at 100k

- Part of the error is scoring, not speech: Whisper writes times as "9.30" (scored as a decimal) and codes as "VN-254"; without these, English CER is about 0.008.
- Real errors are mostly English words inside Vietnamese sentences said with a Vietnamese accent ("dark mode", "task"), unusual brand names (Baemin), a Vietnamese name read by the English front-end ("Nguyen") and a few tone slips in Vietnamese.
- Training loss (mel) still falls slowly, about 0.2–0.3 per 10k steps.

## Notes on `nam-1` at 200k (final)

- Better than 100k on every set: mixed CER almost halves (0.033 → 0.018) and UTMOS rises on all three sets (+0.24 Vietnamese, +0.22 English).
- Remaining English errors are mostly numbers as Whisper writes them (CER 0.049 in that group); device prompts and long sentences score 0.
- Training stopped at 200k; the student is distilled from this checkpoint.

## Notes on `nu-10` at 200k (final)

- On par with `nam-1` at 200k for accuracy and higher UTMOS on all three sets, so training stopped at 200k as well.
- The "whistle" score (high-frequency energy) is higher than for `nam-1` (18–29 vs 9–12); part of this is the higher female pitch, to be checked by listening after distillation.

## First student (`nam-1`, M, distilled from the 200k teacher)

Rendered with the C runtime on the host (same output as the chip) and scored like the teachers:

| Model | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---|---|---|---|
| `nam-1` M student (1.83M params, 2.6 MB) | 0.021 / 0.053 | 0.014 / 0.025 | 0.035 / 0.078 | 2.40 / 3.23 / 2.49 |

Words come through almost as well as from the teacher; naturalness (UTMOS) drops by about one point, the usual gap for a model this small. RTF on the ESP32-P4: 0.26–0.28.

## Clean retraining

These teachers were warm-started from a Vietnamese teacher trained on another corpus (VietBibleVox, CC BY-SA 4.0); `nu-10` started from an early `nam-1` checkpoint. So that the released voices carry only the synthetic VoxCPM2 audio and can be Apache-2.0, both teachers were retrained from random initialization on that audio alone and the students distilled again; those students are the v0.4.0 release ([bilingual-student-eval.md](bilingual-student-eval.md)). The results above are kept for comparison.

## Evaluation of new pairs

Each new pair (zh-en, ko-en, ja-en) is scored on its own two sets plus the shared English set `eval/sets/ood_en.jsonl`. The sets are written for evaluation (not taken from the training corpora; checked against `data/*/sentences.jsonl` and `data/zh/mixed.jsonl`), 50 sentences each in five groups of 10: device prompts, numbers (digits, dates, times, percentages, money, phone numbers), names (people and places), questions and long sentences.

| Set | Content | `lang` (render and score) | Whisper language |
|---|---|---|---|
| `eval/sets/ood_zh.jsonl` | Mandarin, no Latin letters | `zh` | `zh` |
| `eval/sets/mixed_zh.jsonl` | Mandarin with English brand and tech terms | `zh` | `zh` |
| `eval/sets/ood_ko.jsonl` | Korean, no Latin letters | `ko` | `ko` |
| `eval/sets/mixed_ko.jsonl` | Korean with English terms | `ko` | `ko` |
| `eval/sets/ood_ja.jsonl` | Japanese, no Latin letters | `ja` | `ja` |
| `eval/sets/mixed_ja.jsonl` | Japanese with English terms | `ja` | `ja` |

One `lang` value per pair covers both sets: the pair token set reads main-language and mixed text alike (as in training, where mixed rows have the pair language), and the same scoring handles the English words. Each row carries its `lang`, so `render_teacher.py` picks the token set from the row.

```bash
uv run python scripts/teacher/render_teacher.py --ckpt CKPT --set eval/sets/mixed_zh.jsonl --out DIR --lang zh
uv run python scripts/eval/eval_dir.py --system NAME --set eval/sets/mixed_zh.jsonl --audio DIR \
  --out reports/NAME-mixed_zh.json --lang zh --asr openai/whisper-large-v3
```

Metrics (`vtts.eval.cer`, `--lang zh|ko|ja`; the Whisper language follows `--lang`):

- Reference and transcript go through the pair front-end's normalizers, so numbers are compared as read in the main language ("20%" and "百分之二十" match) and English words through the English normalizer; punctuation is dropped. Chinese is compared in Simplified characters, Japanese with katakana folded to hiragana.
- **CER** is character-level with spaces removed: Han characters, Hangul syllables, kana and kanji, and the letters of English words. Korean word spacing and the spacing of English terms ("Wi-Fi" / "WiFi") are not errors.
- **WER** for zh and ja counts each Han character or kana as one unit and each English word as one unit (a mixed error rate, since these languages have no spaces); for ko it counts space-separated words (어절), so it also counts spacing differences and is reported for reference only.
- Japanese CER is orthographic: Whisper writing a word in kanji where the reference has kana (or another kanji spelling) counts as an error, so part of the Japanese CER is spelling, not speech. Check the worst clips by ear before reading a Japanese difference as a model difference.
- Release gate as in the roadmap: mixed CER within 0.01 of the vi-en result and no regression on `ood_en`.
