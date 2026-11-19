# Bilingual student evaluation (v0.4.0)

The four models released in v0.4.0: Vietnamese + English voices `nam-1` (male) and `nu-10` (female), each as a quality model M (preset `M-vocos-p-bi`, 1.83M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-bi`, 0.82M parameters, 1.2 MB int8). Their teachers were trained from random initialization on speech synthesized with VoxCPM2 only (about 98 h per voice), so the models are Apache-2.0.

Each int8 file renders the three out-of-domain sets of the [teacher evaluation](bilingual-teacher-eval.md) (50 sentences each, none in the training text) with the C runtime on a PC (`runtime/build/vtts_say --lang auto` with the English lexicon blob; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood` | Vietnamese | PhoWhisper-large |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed` | Vietnamese with English terms and names | Whisper large-v3, `vi` |

## Results

| Model | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---|---|---|---|
| `nam-1` M | 0.021 / 0.041 | 0.015 / 0.025 | 0.030 / 0.063 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.024 / 0.049 | 0.009 / 0.014 | 0.036 / 0.073 | 2.38 / 3.05 / 2.45 |
| `nu-10` M | 0.014 / 0.027 | 0.008 / 0.010 | 0.015 / 0.039 | 2.72 / 3.44 / 2.70 |
| `nu-10` S | 0.015 / 0.027 | 0.013 / 0.020 | 0.027 / 0.059 | 2.52 / 3.26 / 2.50 |

For comparison (same sets and scoring):

| Model | Vietnamese CER | English CER | Mixed CER | UTMOS (vi / en / mixed) |
|---|---:|---:|---:|---|
| First `nam-1` M student (warm-started teacher, not released) | 0.021 | 0.014 | 0.035 | 2.40 / 3.23 / 2.49 |
| `nam-1` teacher, warm-started, 200k | 0.005 | 0.012 | 0.018 | 3.41 / 4.04 / 3.47 |
| `nu-10` teacher, warm-started, 200k | 0.002 | 0.012 | 0.019 | 3.67 / 4.38 / 3.83 |

- The clean `nam-1` M matches the first (unreleased) student on intelligibility and is better on mixed text (0.030 vs 0.035) and in naturalness (UTMOS +0.19 / +0.02 / +0.14), so retraining the teachers from scratch cost nothing.
- `nu-10` is the stronger voice: its M model is within 0.01 of the teacher's CER on all three sets.
- The lite models lose 0.1–0.2 UTMOS against M and up to 0.012 mixed CER; English stays as intelligible (`nam-1` S scores lower English CER than M, within the noise of 50 sentences).
- As for every student so far, naturalness is about one UTMOS point below the teacher: the limit is the model size, not the data.

## Where the errors are

- **Numbers as Whisper writes them.** "9:30" transcribed as "9.30" and "0912 345 678" read as digit groups ("ba trăm bốn mươi lăm") give most of the English number-group CER (0.049 for every model) and the largest Vietnamese errors. Device prompts and long English sentences score 0.
- **Brand names inside Vietnamese sentences:** "Grab" → "crack", "Baemin" → "bánh xèo" / "BuyMe", "Bitexco", "dock". This is the `names` group of the mixed set (0.07 for `nam-1` S, 0.016 for `nu-10` M).
- **Short Vietnamese exclamations** at the start of an utterance ("Nhanh lên, sắp muộn rồi!") sometimes lose a tone on `nam-1`.

## On the chip

Every clip on the website and in the README is the ESP32-P4's own PCM (firmware `dump` command, `lang auto`), compressed to 64 kbps MP3. All 32 published MP3s (8 sentences × 2 voices × 2 models) were decoded again and transcribed with the same ASR as above: CER 0.017 on the Vietnamese clips, 0.010 on the mixed and 0.005 on the English ones; the worst clip is 0.06 (`nam-1` reading the place name "Nhơn Trạch"), and none is broken. The dumps of the same sentences from the ESP32-S3 score the same.

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.19 / 0.06–0.15 s | 0.25–0.27 / 0.17–0.34 s |
| ESP32-S3 | 0.29–0.31 / 0.17–0.32 s | 0.50–0.52 / 0.31–0.61 s |

Details, including a non-deterministic burst artifact of M on the ESP32-S3 with two cores, are in [performance.md](performance.md).

Raw results: `reports/eval/vien-{nam1,nu10}-{M,S}-{ood,ood_en,mixed}.json` (not in the repository).
