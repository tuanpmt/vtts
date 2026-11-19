# Japanese + English student evaluation (v0.6.0)

The two models released in v0.6.0: the Japanese + English voice `nu-ja` (female, about 40, Tokyo standard speech) as a quality model M (preset `M-vocos-p-ja-en`, 1.84M parameters, 2.6 MB int8) and a lite model S (preset `S-vocos-p-ja-en`, 0.83M parameters, 1.2 MB int8). Both use the token set `ja-en` (vocabulary 144: the 107 tokens of v2 plus 37 Japanese phoneme tokens). The teacher `ja_nuja` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 from the designed voice `nu-ja` only (49,591 sentences: Japanese, Japanese with English words, and English read by the same voice), so the models are Apache-2.0.

Each int8 file renders three out-of-domain sets of 50 sentences (none in the training text) with the C runtime on a PC (`runtime/build/vtts_say --lang ja` with the English lexicon and the JLEX blob; the same code path and output as the chip), then `scripts/eval/eval_dir.py` scores them:

| Set | Content | ASR |
|---|---|---|
| `ood_ja` | Japanese (device prompts, numbers, names, questions, long sentences) | Whisper large-v3, `ja` |
| `ood_en` | English | Whisper large-v3, `en` |
| `mixed_ja` | Japanese with English terms and names ("このWi-Fiはpasswordが必要ですか？") | Whisper large-v3, `ja` |

A ja-en model has one text mode, `ja`: English sentences are read through the same mode (Latin words go to the English front-end), so `ood_en` is rendered with `--lang ja`. `vtts_say --lang en` is refused for ja-en models.

The same 50 Japanese and 50 mixed sentences were also synthesized by VoxCPM2 with the voice `nu-ja` (the audio the teacher learned from; `scripts/data/synth_voxcpm.py --voice nu-ja`) and scored the same way. This reference voice shows how much of each error rate comes from the ASR and the scoring rather than from the voice.

## Results

| Model | Japanese CER: text / reading | English CER / WER | Mixed CER: text / kana and kanji only | UTMOS (ja / en / mixed) |
|---|---|---|---|---|
| `nu-ja` M | 0.097 / **0.050** | 0.023 / 0.029 | 0.203 / 0.054 | **2.57 / 3.22 / 2.61** |
| `nu-ja` S | 0.110 / 0.053 | 0.019 / 0.025 | 0.236 / **0.049** | 2.30 / 2.76 / 2.28 |
| VoxCPM2 `nu-ja` (reference voice) | 0.064 / 0.023 | — | 0.230 / 0.049 | 3.45 / — / 3.43 |

- **Japanese:** the plain (orthographic) CER is high for every system, the reference voice included (0.064), because the references write many numbers in kanji (十五分, 二十六度) and Whisper writes digits. The CER on readings (next section) removes this: M 0.050 and S 0.053, about twice the reference voice (0.023). The real errors are mostly word-initial *r* and a few similar-sounding words (below).
- **English:** both models are as intelligible in English as the other pairs (0.019–0.023), apart from numbers (below). Device prompts, questions and long sentences score 0–0.013.
- **Mixed:** on the Japanese characters both models are at the level of the reference voice (0.054 M, 0.049 S against 0.049). The plain CER (0.20–0.24) mostly counts English words that Whisper writes in katakana.

## How Japanese is scored

Japanese CER in `vtts.eval.cer` is orthographic: reference and transcript go through the ja front-end's normalizer (numbers written with digits are read in Japanese, katakana is turned into hiragana) and are compared character by character. Two habits of the ASR then count as errors although the audio is right:

- **Kanji numerals.** The `ood_ja` references write several numbers in kanji (洗濯機はあと十五分で終わります, 朝七時, 三十分). Whisper writes digits (15分), which the normalizer reads as じゅうごふん: two kanji against five kana. Ten of the 50 reference-voice clips lose 0.06–0.37 this way.
- **Kanji or kana, homophones.** 色々 / いろいろ, 朝ご飯 / 朝ごはん, 沸きました / 湧きました, 勧めて / 進めて: same sound, different spelling.

`vtts.eval.cer.ja_reading_cer` compares readings instead: reference and transcript are both converted to hiragana by the ja front-end's reading tables (the tables the device uses), so only a different reading is an error. It is counted in kana (about two per kanji), so it is not comparable with the orthographic CER, only between systems. `scripts/eval/mixed_cer.py --lang ja` prints both, also restricted to the reference's kana and kanji for mixed sets (`main_only`):

| System | `ood_ja` text | `ood_ja` reading | `mixed_ja` text | `mixed_ja` kana and kanji only | `mixed_ja` reading, kana only |
|---|---:|---:|---:|---:|---:|
| VoxCPM2 `nu-ja` (reference) | 0.064 | 0.023 | 0.230 | 0.049 | 0.039 |
| `nu-ja` M | 0.097 | 0.050 | 0.203 | 0.054 | 0.032 |
| `nu-ja` S | 0.110 | 0.053 | 0.236 | 0.049 | 0.032 |

The reading CER still counts one front-end issue on both sides: a kanji numeral before 分 is read ぶん (三十分 → さんじゅうぶん) where the digits give the right ぷん (30分 → さんじゅっぷん); see the known issues.

## How the mixed set is scored

As with Korean, Whisper forced to Japanese writes most English words in katakana: "password" becomes パスワード, "online game" オンラインゲーム, "software engineer" ソフトウェアエンジニア, "Alexa" アレクサ. Against a reference in Latin letters each counts as wrong, so a perfect reading of "翔太さんはGoogleのsoftware engineerです。" scores 0.53. The reference voice gets a plain CER of 0.230, between M (0.203) and S (0.236): the plain CER measures the transliteration, not the voice.

`vtts.eval.cer.main_script_cer` (added for Korean) counts only the errors on the reference's kana and kanji; English words and whatever Whisper writes in their place are skipped. On it M is within 0.005 of the reference voice and S equal to it. Measured on readings the students are slightly ahead of the reference voice (0.032 against 0.039).

The kana-only CER does not judge the English words themselves. The transcripts show most are read correctly (Wi-Fi, USB-C, Netflix, PowerPoint, Instagram, Google, dark mode, hashtag), with weak ones:

- **"Bluetooth"** is again the hardest word, mostly at the start of a phrase (transcribed Virtus, プーチュース, once "Google"); writing ブルートゥース works.
- Names that start with a vowel or *l* blur on both models: LinkedIn → ウィンキン, Elon Musk → ヨガン/エオン・マスク, Apple and Samsung → アポートサンソム; S also ChatGPT → チャッチティーチ.

## Where the errors are

- **Word-initial *r*.** The most frequent real error: an *r* at the start of a word is weak or missing, so リビング is heard as イビング (both models, also in the sample sentences), 冷蔵庫 as 映像この, 来月 as A月, りんご (S: ロボット as ボボッと). Inside words *r* is fine. This is a property of the voice and the students (the reference voice has none of these errors); a student refresh is the planned fix.
- **Similar-sounding words**, more on S: 洗濯機 → 選択肢, 鍵 → カリ, 今晩 → 本番, 切符 → キット, 広島 → 日吉間 (M); 明日は雨が降るでしょうか → メガフルで消化, 渡辺 → 旦那部 (S).
- **Numbers in English sentences are read in Japanese.** The ja text mode reads every number in Japanese, also inside an English sentence ("The temperature outside is 28 degrees" → にじゅうはち). This gives the English `numbers` group its CER (0.093 M, 0.107 S: 28 heard as 18, "15 percent" as "0%"); every other English group is at most 0.033. Write numbers as words in English text.
- **Number formats:** a free-dial number "0120-123-456" is transcribed with different grouping by every system, the reference voice included (0.51–0.63 for that clip); "9:30" as "9.30" in English likewise.

## On the chip

Every clip on the website and in [voices.md](../voices.md#listen-generated-on-an-esp32-p4) is the ESP32-P4's own PCM (firmware `dump` command, `lang ja`), compressed to 64 kbps MP3. All 16 published MP3s (8 sentences × 2 models: Japanese, mixed and English) were decoded again and transcribed with Whisper large-v3 before publishing. On the kana and kanji of the 12 Japanese and mixed clips the CER is 0.001 on average (one error: アラーム heard as カラーム in the M numbers clip, 0.017); the Latin parts lose a little with S ("ESP32" heard as "EST3", "Zoom" as ジュン; plain CER 0.10 and 0.09). Of the four English clips, S scores 0 on both; M gets 0.044 ("Hello" heard as "Holol", "ESP32" as "ESP3 to") and 0.011 ("porch lights"). None is broken. The ESP32-P4 output matches `vtts_say` on a PC (SNR 37–56 dB on the single-sentence clips; the clips with two sentences differ only in the pause between them).

The sample sentences avoid "Bluetooth" and word-initial *r* (リビング); they show Zoom, PowerPoint, Wi-Fi and Netflix inside Japanese sentences.

| Chip | S: RTF / speech starts | M: RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.18 / 0.07–0.10 s | 0.25–0.26 / 0.18–0.26 s |
| ESP32-S3 | 0.28–0.30 / 0.18–0.25 s | 0.50 / 0.31–0.45 s |

On the ESP32-S3 with two cores (the default) the output of M is not deterministic (6 of 9 test dumps differ from the ESP32-P4), as for the other pairs; S matched the ESP32-P4 in all 9 dumps, and `cores 1` gives the ESP32-P4 output for both. Details in [performance.md](performance.md#japanese--english-v060).

Raw results: `reports/eval/jaen-ja-{M,S}-{ood_ja,ood_en,mixed_ja}.json` and `reports/eval/voxcpm2-nu-ja-{ood_ja,mixed_ja}.json` (not in the repository).
