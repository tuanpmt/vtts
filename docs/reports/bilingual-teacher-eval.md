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

For reference, the Vietnamese prototype teacher (trained on a recorded corpus) scored CER 0.015 and UTMOS 2.50 on the same Vietnamese set.

## Notes on `nam-1` at 100k

- Part of the error is scoring, not speech: Whisper writes times as "9.30" (scored as a decimal) and codes as "VN-254"; without these, English CER is about 0.008.
- Real errors are mostly English words inside Vietnamese sentences said with a Vietnamese accent ("dark mode", "task"), unusual brand names (Baemin), a Vietnamese name read by the English front-end ("Nguyen") and a few tone slips in Vietnamese.
- Training loss (mel) still falls slowly, about 0.2–0.3 per 10k steps. The next evaluation at about 150k decides whether to stop the teacher and start distillation.
