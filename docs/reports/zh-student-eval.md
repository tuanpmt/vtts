# Chinese + English student evaluation (`nu-zh`)

The two Chinese (Mandarin) + English models of the `nu-zh` voice (female, about 40, Beijing Mandarin): a quality model M (preset `M-vocos-p-zh-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-zh-en`, 0.83M parameters, 1.2 MB int8), token set `zh-en` (171 tokens: the 107 vi-en tokens, then Mandarin initials, finals and tones). Both are **bilingual**: one voice reads Mandarin, English and Mandarin sentences with English words.

The teacher (`zh_nuzh`, VITS, about 24M parameters) was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 (Apache-2.0) in the designed `nu-zh` voice only: 54,636 sentences, Mandarin, Mandarin with English terms, and English sentences read by the same voice. No recorded corpus and no warm start from another model, so the models are Apache-2.0.

Each int8 file renders three out-of-domain sets of 50 sentences (none in the training text, see the [teacher evaluation](bilingual-teacher-eval.md#evaluation-of-new-pairs)) with the C runtime on a PC (`runtime/build/vtts_say --lang zh` with the English lexicon and the ZLEX blob; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them with Whisper large-v3:

| Set | Content | Whisper language | CER unit |
|---|---|---|---|
| `ood_zh` | Mandarin, no Latin letters | `zh` | Han character |
| `mixed_zh` | Mandarin with English brand and tech terms | `zh` | Han character / Latin letter |
| `ood_en` | English | `en` | character |

`ood_en` is rendered in the zh mode too (`--lang zh`): the zh-en token set has one text mode, which reads Latin words with the English front-end.

## Results

| Model | Mandarin CER / WER | Mixed CER / WER | English CER / WER | UTMOS (zh / mixed / en) |
|---|---|---|---|---|
| `nu-zh` M | 0.020 / 0.020 | 0.047 / 0.057 | 0.021 / 0.025 | 3.16 / 3.23 / 3.64 |
| `nu-zh` S | 0.042 / 0.042 | 0.032 / 0.042 | 0.034 / 0.041 | 2.89 / 2.96 / 3.35 |

WER for zh counts each Han character and each English word as one unit.

CER per group (10 sentences each):

| Model | Set | Device | Numbers | Names | Questions | Long |
|---|---|---:|---:|---:|---:|---:|
| M | Mandarin | 0.008 | 0.014 | 0.068 | 0.019 | 0.010 |
| M | Mixed | 0.005 | 0.064 | 0.081 | 0.035 | 0.047 |
| M | English | 0.000 | 0.118 | 0.000 | 0.008 | 0.000 |
| S | Mandarin | 0.089 | 0.055 | 0.051 | 0.029 | 0.017 |
| S | Mixed | 0.034 | 0.035 | 0.062 | 0.041 | 0.008 |
| S | English | 0.000 | 0.189 | 0.014 | 0.000 | 0.000 |

- M is clearly better on Mandarin (CER 0.020 vs 0.042, UTMOS +0.27) and English (0.021 vs 0.034, UTMOS +0.29).
- On the mixed set S scores the lower CER (0.032 vs 0.047). With 50 sentences this is within the noise of a few names: M's mixed errors are almost all in the names and numbers groups (below), and M's UTMOS is higher on every set.
- Naturalness is above the Vietnamese + English students (UTMOS 2.4–2.7 on Vietnamese; 3.2 here for M on Mandarin), and English is the most natural set for both models, as for the vi-en voices.

## `nu-zh` M update (v0.10.3)

v0.10.3 replaces the quality model M with a re-distillation that uses the improved recipe: the same teacher (`zh_nuzh`), the same presets and the same stages except a **longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**). Size (1.84M parameters, 2.6 MB), speed, token set and text mode are unchanged. The released v0.5.0 models and the new ones were rendered again with the current C runtime (`vtts_say --lang zh`) and scored with the same sets and pipeline (Whisper large-v3, UTMOS); the v0.5.0 numbers below therefore differ slightly from the table above, which was measured with the v0.5.0 front-end. "Han only" is the mixed-set CER over the reference's Han characters (`vtts.eval.cer.main_script_cer`; English words and what Whisper writes for them are skipped).

| Model | Mandarin CER / WER | Mixed CER / WER (Han only) | English CER / WER | UTMOS (zh / mixed / en) |
|---|---|---|---|---|
| M v0.5.0 (joint 20k) | 0.023 / 0.023 | 0.047 / 0.057 (0.046) | 0.021 / 0.025 | 3.17 / 3.24 / 3.64 |
| **M v0.10.3 (joint 80k)** | 0.024 / 0.024 | **0.030 / 0.044 (0.015)** | **0.018 / 0.022** | **3.36 / 3.44 / 3.76** |
| S v0.5.0 (joint 20k, kept) | 0.042 / 0.042 | 0.032 / 0.042 (0.023) | 0.034 / 0.041 | 2.90 / 2.96 / 3.35 |
| S joint 80k (not released) | 0.025 / 0.025 | 0.059 / 0.053 (0.033) | 0.021 / 0.029 | 3.11 / 3.25 / 3.56 |

- **M:** UTMOS +0.12 to +0.20 on all three sets; the mixed set improves the most (Han-only CER 0.046 → 0.015: the v0.5.0 errors on names, "第25行" and "一会儿" are gone), English CER drops, and the Mandarin CER is the same within one character (0.023 → 0.024; the new model fixes the names 李明, 刘洋, 孙悦 and gets 卧室 → 博士, "299元" → "1299元" and 坐高铁 → 做糕点 wrong).
- **S stays v0.5.0.** The S of the same re-distillation is better on Mandarin (CER 0.042 → 0.025) and English, and UTMOS is 0.2–0.3 higher, but its mixed-set Han-only CER is higher (0.023 → 0.033: the order code "A3B7", "GitHub" read so that the following Han characters change, 音箱 → 电像, 经理 → 金驴). The release rule is "UTMOS better and no CER worse by more than 0.003", so the S was not released.

On the chip the new M runs at the speed of the v0.5.0 M (ESP32-P4 RTF 0.27–0.29, speech starts after 0.17–0.29 s; ESP32-S3 0.55–0.58). The eight `nu-zh` Quality clips of the website are ESP32-P4 dumps of the new M, 64 kbps MP3; Whisper large-v3 transcribes all eight with CER 0 ([performance.md](performance.md#nu-zh-m-and-nu-ko-s-update-v0103)). The Lite clips are still the v0.5.0 S.

Raw results: `zh-{M,S}-{old,new}-{ood_zh,mixed_zh,ood_en}.json` (not in the repository).

## Where the errors are

- **Names of people.** Two-character given names are the largest Mandarin error group for M (0.068): 刘洋 → 有样, 李明 → 移民, 孙悦 → 三越. Without context these are homophone or near-homophone guesses of the ASR as much as tone errors of the model.
- **Numbers in English sentences are read in Mandarin.** The zh-en token set has one text mode (`zh`), and its normalizer reads digits as Mandarin numbers also inside English sentences: "November 18" → "November Shabbat" (十八), "$42.50" → "42.50美元", "3 p.m." → "10pm". This is the whole English CER of the numbers group (0.118 M, 0.189 S); the other English groups score 0–0.014. English sentences without digits are read correctly. Writing the number as words ("eighteen") avoids it.
- **The lite model on short Mandarin device prompts** (S, device group 0.089): 后门还没有锁，要帮你锁上吗？ → 客户们还没有锁, 还要帮你锁上网。, 卧室 → 博士.

### Mixed CER is inflated by the ASR

In mixed sentences Whisper sometimes writes an English word in Chinese characters, or a Chinese word as an English symbol, although the audio is correct. Each such word counts as several character errors:

| Model | Reference | Whisper transcript | CER |
|---|---|---|---:|
| S | Apple和**Samsung**都发布了新手机。 | Apple和**三星**都发布了新手机 | 0.35 |
| S | 这个USB-C充电器的功率是65**瓦**。 | 这个USB-C充电器的功率是65**W** | 0.12 |
| M | 你会用**ChatGPT**写email吗？ | 你会用**checkgpt**写email吗? | 0.18 |

Real errors of the models in the same set are mostly English names and codes: "Elon Musk" → "Lillian Musk" (M), "LinkedIn" → "Linting" / "Linton", "Wi-Fi" → 未发疫 (S), the order code "A3B7" → "R3笔记" (M). So the mixed CER is an upper bound; listening, the English terms are clear in most sentences.

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang zh`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models) were decoded again and transcribed with Whisper large-v3: CER 0.003 on the Mandarin and mixed clips and 0.009 on the English ones; the worst clip is 0.036 (S reading 零下 heard as 雲下), and none is broken. The English sample sentences contain no digits (see above).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.20 / 0.07–0.11 s | 0.25–0.29 / 0.16–0.29 s |
| ESP32-S3 | 0.28–0.32 / 0.17–0.27 s | 0.49–0.53 / 0.27–0.48 s |

Details, including the two-core issue on the ESP32-S3 (M as with vi-en, and with zh-en also S, mildly; `cores 1` is exact), are in [performance.md](performance.md#chinese--english-v050).

Raw results: `reports/eval/zhen-zh-{M,S}-{ood_zh,mixed_zh,ood_en}.json` (not in the repository).
