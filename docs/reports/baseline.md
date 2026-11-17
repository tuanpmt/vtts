# Baseline report

Two existing Vietnamese voices, run as black boxes (`eval/baselines/render.py`). Both receive text already normalized by `vtts.frontend.normalize`, so numbers and abbreviations are read the same way.

- Scoring ASR: `vinai/PhoWhisper-large`. CER/WER keep tone marks, so a wrong tone counts as an error.
- UTMOS (`utmos22_strong`) and DNSMOS (OVRL) predict naturalness/cleanliness and were trained mostly on English. Use them only to compare Vietnamese systems with each other.
- Whistle index: the number of spectrogram cells that belong to stationary tonal streaks, per second (lower is better).

## Out-of-domain set (`eval/sets/ood.jsonl`, 50 sentences)

| System | CER | WER | UTMOS | DNSMOS | Whistle |
|---|---:|---:|---:|---:|---:|
| sanoTTS `vi` (1.57M, Piper VAIS1000 as teacher) | 0.064 | 0.127 | 1.49 | 2.83 | 1.5 |
| Piper `vi_VN-25hours_single-low` (InfoRe1) | 0.089 | 0.197 | 2.06 | 2.43 | 1.1 |

CER by sentence group:

| Group | sanoTTS `vi` | Piper 25h |
|---|---:|---:|
| device (device prompts) | 0.117 | 0.109 |
| numbers (numbers, dates, times, money) | 0.032 | 0.081 |
| names (people and place names) | 0.125 | 0.143 |
| prosody (questions, exclamations) | 0.072 | 0.111 |
| long (> 30 syllables) | 0.046 | 0.068 |

Typical errors (reference → what the ASR heard):

- sanoTTS `vi`: "Phố cổ Hội An lung linh đèn lồng về đêm" → "phố cổ hội an lũng nghinh đằng lùng về đằng kia"; "Pin yếu, vui lòng cắm sạc ngay" → the first two syllables are lost.
- Piper 25h: "Cẩn thận, sàn nhà đang ướt!" → "thân thân xanh nhả nặng ruột"; "Chúc bạn ngủ ngon" → "chúc bạn hy vọng".

## Observations

- Short device-prompt sentences (the `device` group) are a common weakness of both. These are exactly the sentences an ESP32 product will speak most.
- sanoTTS `vi` is more intelligible than Piper 25h but has a lower UTMOS (1.49 vs 2.06): clearer, but less natural.
- CER is computed after normalizing tone-mark placement (`hoà` and `hòa` count as the same), so purely orthographic differences are not penalized.
- The sanoTTS `vi` WER of 0.127 here is lower than the 0.468 in the sanoTTS README because the ASR (PhoWhisper vs Whisper) and the sentence set differ. Only compare numbers within one report.

## Derived teacher gate (spec section 6)

On the out-of-domain set the project's teacher must reach:

- CER ≤ 50% of sanoTTS `vi`, i.e. **CER ≤ 0.032**;
- and CER ≤ Piper 25h (0.089), which follows from the first condition.

The teacher that was later trained reached an OOD CER of 0.015 (see the quality table in the [README](../../README.md)).
