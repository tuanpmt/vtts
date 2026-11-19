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

Every clip on the website and in the README is the ESP32-P4's own PCM (firmware `dump` command, `lang zh`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models) were decoded again and transcribed with Whisper large-v3: CER 0.003 on the Mandarin and mixed clips and 0.009 on the English ones; the worst clip is 0.036 (S reading 零下 heard as 雲下), and none is broken. The English sample sentences contain no digits (see above).

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.20 / 0.07–0.11 s | 0.25–0.29 / 0.16–0.29 s |
| ESP32-S3 | 0.28–0.32 / 0.17–0.27 s | 0.49–0.53 / 0.27–0.48 s |

Details, including the two-core issue on the ESP32-S3 (M as with vi-en, and with zh-en also S, mildly; `cores 1` is exact), are in [performance.md](performance.md#chinese--english-v050).

Raw results: `reports/eval/zhen-zh-{M,S}-{ood_zh,mixed_zh,ood_en}.json` (not in the repository).
