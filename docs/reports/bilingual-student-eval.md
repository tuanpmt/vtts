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

## `nu-10` M update (v0.9.1)

The improved distillation recipe keeps the v0.4.0 chain (preset `M-vocos-p-bi`, the same teacher `nu10_vien_b32`, a 20,000-sentence distillation pack; front 10k and decoder 30k steps) and runs the joint stage for 80k steps instead of 20k. The file has the same size (2.6 MB), architecture and speed; it replaces the v0.4.0 `nu-10` M (`vtts-vien-nu10-m-v0.9.1.q8.vtts`). Both models were rendered and scored again with the same pipeline on the same three sets (PhoWhisper-large for `ood`, Whisper large-v3 for `ood_en` and `mixed`, UTMOS):

| Model | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---|---|---|---|
| `nu-10` M v0.4.0 (joint 20k) | 0.014 / 0.027 | 0.008 / 0.010 | 0.015 / 0.041 | 2.73 / 3.44 / 2.70 |
| `nu-10` M v0.9.1 (joint 80k) | 0.014 / 0.024 | 0.008 / 0.010 | 0.015 / 0.032 | **3.11 / 3.87 / 3.12** |

- Naturalness rises by 0.38–0.43 UTMOS on all three sets, closing about 40% of the gap to the teacher (3.67 / 4.38 / 3.83); intelligibility is unchanged (mixed WER slightly lower).
- The re-run of v0.4.0 matches the published numbers above within 0.01 UTMOS and 0.002 WER (different run of the same scoring).
- The `nu-10` S stays the v0.4.0 model for now.

## `nu-10` S update (v0.10.2)

A dedicated re-distillation of `nu-10` with the improved recipe: the same teacher (`nu10_vien_b32`) and 20,000-sentence pack, front 10k, decoder 30k and **joint 80k steps** (instead of 20k), trained for both sizes. The S (preset `S-vocos-p-bi`, 0.82M parameters, 1.2 MB) replaces the v0.4.0 `nu-10` S (`vtts-vien-nu10-s-v0.10.2.q8.vtts`); same size, architecture, speed and text modes. All models were rendered with the int8 C runtime (`vtts_say --lang auto`) and scored again with the same pipeline (`scripts/eval/student_quality.py`: PhoWhisper-large for `ood`, Whisper large-v3 for `ood_en` and `mixed`, UTMOS, and the 5–10 kHz noise metrics):

| Model | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---|---|---|---|
| `nu-10` S v0.4.0 (joint 20k) | 0.015 / 0.027 | 0.011 / 0.018 | 0.026 / 0.059 | 2.52 / 3.26 / 2.50 |
| `nu-10` S v0.10.2 (joint 80k) | **0.010 / 0.015** | **0.008 / 0.010** | **0.016 / 0.039** | **2.90 / 3.73 / 2.92** |
| `nu-10` M v0.9.1 (released, for reference) | 0.014 / 0.024 | 0.008 / 0.010 | 0.015 / 0.032 | 3.11 / 3.87 / 3.12 |
| `nu-10` M of the same re-distillation (not released) | 0.011 / 0.018 | 0.010 / 0.012 | 0.018 / 0.039 | 3.02 / 3.90 / 3.00 |

| Model | Spectral flatness 5–10 kHz (vi / en / mixed) | HF energy ratio, dB (vi / en / mixed) |
|---|---|---|
| `nu-10` S v0.4.0 | 0.286 / 0.295 / 0.285 | −30.8 / −27.3 / −30.5 |
| `nu-10` S v0.10.2 | 0.289 / 0.301 / 0.287 | −30.9 / −27.8 / −30.4 |

- Naturalness rises by 0.38–0.47 UTMOS on all three sets, and intelligibility improves too: the mixed CER drops from 0.026 to 0.016 (the level of the M), the Vietnamese CER from 0.015 to 0.010. The S is now 0.14–0.21 UTMOS below the v0.9.1 M (the v0.4.0 S was 0.18–0.20 below the v0.4.0 M).
- The high band is unchanged (flatness within 0.006, HF ratio within 0.5 dB): the longer joint stage does not add hiss. The whistle score rises to the level of the v0.9.1 M (vi 21 vs 9, mixed 14 vs 7), as for every 80k-joint model so far; the published clips were transcribed again with Whisper (none broken).
- The re-run of the v0.4.0 S matches the published numbers above within 0.002 CER (Vietnamese, mixed) and 0.01 UTMOS; the English CER of this run is 0.011 instead of 0.013.
- The M trained in the same re-distillation is not released: against the v0.9.1 M it reads Vietnamese better (CER 0.011 vs 0.014) but scores 0.09–0.12 UTMOS lower on Vietnamese and mixed and 0.002–0.003 higher CER on English and mixed. The v0.9.1 M stays the `nu-10` quality model.

## Where the errors are

- **Numbers as Whisper writes them.** "9:30" transcribed as "9.30" and "0912 345 678" read as digit groups ("ba trăm bốn mươi lăm") give most of the English number-group CER (0.049 for every model) and the largest Vietnamese errors. Device prompts and long English sentences score 0.
- **Brand names inside Vietnamese sentences:** "Grab" → "crack", "Baemin" → "bánh xèo" / "BuyMe", "Bitexco", "dock". This is the `names` group of the mixed set (0.07 for `nam-1` S, 0.016 for `nu-10` M).
- **Short Vietnamese exclamations** at the start of an utterance ("Nhanh lên, sắp muộn rồi!") sometimes lose a tone on `nam-1`.

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang auto`), compressed to 64 kbps MP3. All 32 published MP3s (8 sentences × 2 voices × 2 models) were decoded again and transcribed with the same ASR as above: CER 0.017 on the Vietnamese clips, 0.010 on the mixed and 0.005 on the English ones; the worst clip is 0.06 (`nam-1` reading the place name "Nhơn Trạch"), and none is broken. The dumps of the same sentences from the ESP32-S3 score the same.

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.19 / 0.06–0.15 s | 0.25–0.27 / 0.17–0.34 s |
| ESP32-S3 | 0.29–0.31 / 0.17–0.32 s | 0.50–0.52 / 0.31–0.61 s |

Details, including a non-deterministic burst artifact of M on the ESP32-S3 with two cores, are in [performance.md](performance.md).

Raw results: `reports/eval/vien-{nam1,nu10}-{M,S}-{ood,ood_en,mixed}.json` (not in the repository).
