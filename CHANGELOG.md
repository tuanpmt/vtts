# Changelog

All notable changes to this project are documented here. Model files are attached to the GitHub release [v0.11.0](https://github.com/tuanpmt/vtts/releases/tag/v0.11.0), which has the current M and S of every voice (v0.12.0 carries the same files), and mirrored on [Hugging Face](https://huggingface.co/tuanpm/vtts). The releases before v0.11.0 and their model files were removed after v0.11.0; the entries below keep their notes, and their git tags stay (`https://github.com/tuanpmt/vtts/tree/v0.x.y`). File names in those entries refer to files that are no longer published; use the `-v0.11.q8.vtts` file of the same voice (table under v0.11.0).

## Unreleased

### In progress
- The other pairs: one designed VoxCPM2 voice per language, then data, teachers and students.
- User pronunciation dictionary.
- Model updates with the longer joint stage for the other models (`nam-1` and the other pairs).

## v0.12.0 (2026-11-23) — ESP32-S31 support and the Metalio E-INK4-Plus board

A **firmware and runtime release**, **Apache-2.0**: the **ESP32-S31** becomes a supported chip, with the **Metalio E-INK4-Plus** board (CloudZao). **Models unchanged**: the release carries the same 22 files and `SHA256SUMS` as v0.11.0 (same names `-v0.11.q8.vtts`, same bytes), so the latest release has everything needed.

### Speed on the ESP32-S31

Metalio E-INK4-Plus, ESP32-S31 rev v0.0 at 320 MHz, octal PSRAM at 200 MHz, vi-en `nu-10` v0.11 files, `bench` (four Vietnamese sentences):

| Model | RTF, 1 core | RTF, 2 cores (default) |
|---|---:|---:|
| S (lite) | 0.34–0.36 | 0.26–0.27 |
| M (quality) | 0.51–0.54 | 0.39–0.42 |

With M, the first chunk is ready after about 0.25 s and speech starts after about 0.36 s, without underruns; `selftest` and `memtest` report 0 mismatches. Only `nu-10` was measured; the other voices have the same size and are expected to run alike.

### Added
- **ESP32-S31 target.** The S31 has the PIE vector unit of the ESP32-P4 and uses its int8 kernels (`runtime/ports/esp32p4/vtts_port_p4.c`, branch loops). `sdkconfig.defaults.esp32s31`: 320 MHz, octal PSRAM at 200 MHz, minimum chip revision v0.0, the shared partition table.
- **ESP-IDF v6.1.1 required for the S31** (the first release where it is a supported target, not a preview one); the P4 and S3 boards still build with 6.1.0. `build.sh` and the docs name v6.1.1.
- **Metalio E-INK4-Plus board** (`BOARD=metalio-eink4-plus`): the speaker sits behind an external Bluetooth audio chip that is the I2S master at a fixed 16 kHz, with an NS4150 amplifier. New speaker driver `bt_audio` (TCA9555 expander outputs, AT commands on UART1, I2S slave TX, amplifier enable; writes time out instead of hanging without a clock), a minimal TCA9555 driver, `BSP_EXTRA_SRCS` in `board.cmake`, `BSP_USB_SWITCH_GPIO` to keep the USB-C port on the console. Speech through this path was checked by ear.
- **Streaming resampler for fixed-rate speakers** (`runtime/src/vtts_resample.c`, `vtts_resample.h`): Kaiser-windowed sinc, 20 zero crossings, exact rational output times, about 4.7 KB of state, no allocation. 22050 -> 16000 Hz: flat to 6.8 kHz within 0.06 dB, aliases of 8.6 kHz and above about 79 dB down. `make -C runtime test` includes `resample_test`. The firmware streams through it when the speaker cannot run at the model rate (previously the whole utterance was buffered and interpolated linearly).
- `parstat` console command: two-core split calls, items and time per core.

### Changed
- **ESP32-S31: two cores.** Only core 1 of the S31 has the PIE, and FreeRTOS moves a task that runs a PIE instruction on core 0 to core 1 for good, so at first both the synthesis task and the worker ended up on core 1 and `cores 2` gave no speedup. Synthesis now runs on core 1, the worker on core 0 with plain C int8 kernels (same int32 sums), and the cores share each pass from both ends; the S31 also gets up to 256 KB of internal RAM for the hot buffers. S RTF 0.35 -> 0.26–0.27, M 0.54 -> 0.39–0.42, output identical. The ESP32-P4 and ESP32-S3 keep their split and speed.
- The GitHub releases v0.1.0 to v0.10.4 and the older model files on Hugging Face were removed; v0.11.0 has the current M and S of every voice, and each Hugging Face folder now holds only its two `-v0.11.q8.vtts` files and `SHA256SUMS`. The git tags of the earlier releases stay. The Vietnamese-only prototype folder `vi/` (v0.1–v0.2, non-commercial) was removed from Hugging Face.
- README, voices.md, the performance report, the website, the roadmap and the Hugging Face card list the ESP32-S31.

### Flashing the Metalio E-INK4-Plus

```bash
gh release download v0.12.0 -R tuanpmt/vtts -p 'vtts-vien-nu10-*' -D models
cd firmware/esp32
BOARD=metalio-eink4-plus ./build.sh ../../models/vtts-vien-nu10-s-v0.11.q8.vtts \
  ../../models/vtts-vien-nu10-m-v0.11.q8.vtts -p PORT flash monitor
```

On the S31 the bootloader is at 0x2000 (as on the P4); `build.sh ... flash` sets the offsets.

## v0.11.0 (2026-11-20) — consolidated release of all voices

A **consolidated release**, **Apache-2.0**: the current quality (M) and lite (S) model of **every released voice in one release**, so one download is enough instead of picking files from v0.4.0 to v0.10.4. **No new training and no new models**: each v0.11 file is byte-identical to the recommended file of an earlier release (same SHA256), only renamed to `-v0.11.q8.vtts`. The `.vtts` header carries no release version, so the files run with the same firmware and runtimes as before. The earlier releases stay available with their original file names, and the Hugging Face folders keep the older files next to the v0.11 ones.

### Models

22 files (11 voices × S and M, about 42 MB) and one `SHA256SUMS`. "From" is the release whose file has the same bytes. CER and UTMOS on the main-language out-of-domain set, as in [voices.md](docs/voices.md#quality) (English, mixed and the reference voices there):

| Voice | Language | Lite (S) file | S from | Quality (M) file | M from | Params S / M | Main-language CER and UTMOS, S / M |
|---|---|---|---|---|---|---|---|
| `nu-en` | English (American) | `vtts-en-nuen-s-v0.11.q8.vtts` | v0.10.1 | `vtts-en-nuen-m-v0.11.q8.vtts` | v0.10.1 | 0.82M / 1.83M | `ood_en` CER 0.015 / 0.012, UTMOS 3.68 / 3.56 |
| `nam-1` | Vietnamese + English | `vtts-vien-nam1-s-v0.11.q8.vtts` | v0.4.0 | `vtts-vien-nam1-m-v0.11.q8.vtts` | v0.4.0 | 0.82M / 1.83M | vi CER 0.024 / 0.021, UTMOS vi 2.38 / 2.59 |
| `nu-10` | Vietnamese + English | `vtts-vien-nu10-s-v0.11.q8.vtts` | v0.10.2 | `vtts-vien-nu10-m-v0.11.q8.vtts` | v0.9.1 | 0.82M / 1.83M | vi CER 0.010 / 0.014, UTMOS vi 2.90 / 3.11 |
| `nu-ko` | Korean + English | `vtts-koen-nuko-s-v0.11.q8.vtts` | v0.10.3 | `vtts-koen-nuko-m-v0.11.q8.vtts` | v0.5.0 | 0.83M / 1.84M | ko CER 0.026 / 0.021, UTMOS ko 3.18 / 2.75 |
| `nu-zh` | Chinese (Mandarin) + English | `vtts-zhen-nuzh-s-v0.11.q8.vtts` | v0.5.0 | `vtts-zhen-nuzh-m-v0.11.q8.vtts` | v0.10.3 | 0.83M / 1.84M | zh CER 0.042 / 0.024, UTMOS zh 2.89 / 3.36 |
| `nu-ja` | Japanese + English | `vtts-jaen-nuja-s-v0.11.q8.vtts` | v0.6.0 | `vtts-jaen-nuja-m-v0.11.q8.vtts` | v0.10.4 | 0.83M / 1.84M | ja reading CER 0.053 / 0.035, UTMOS ja 2.30 / 2.75 |
| `nu-pt` | Portuguese (Brazil) + English | `vtts-pten-nupt-s-v0.11.q8.vtts` | v0.7.0 | `vtts-pten-nupt-m-v0.11.q8.vtts` | v0.7.0 | 0.83M / 1.84M | pt CER 0.019 / 0.008, UTMOS pt 2.63 / 2.36 |
| `nu-id` | Indonesian + English | `vtts-iden-nuid-s-v0.11.q8.vtts` | v0.8.0 | `vtts-iden-nuid-m-v0.11.q8.vtts` | v0.8.0 | 0.83M / 1.84M | id CER 0.011 / 0.011, UTMOS id 2.14 / 2.42 |
| `nu-hi` | Hindi + English | `vtts-hien-nuhi-s-v0.11.q8.vtts` | v0.8.0 | `vtts-hien-nuhi-m-v0.11.q8.vtts` | v0.8.0 | 0.83M / 1.84M | hi CER 0.092 / 0.094, UTMOS hi 2.84 / 2.84 |
| `nu-es` | Spanish + English | `vtts-esen-nues-s-v0.11.q8.vtts` | v0.10.4 | `vtts-esen-nues-m-v0.11.q8.vtts` | v0.10.4 | 0.83M / 1.84M | es CER 0.015 / 0.001, UTMOS es 2.93 / 3.09 |
| `nu-th` | Thai + English | `vtts-then-nuth-s-v0.11.q8.vtts` | v0.10.0 | `vtts-then-nuth-m-v0.11.q8.vtts` | v0.10.0 | 0.83M / 1.84M | th CER 0.053 / 0.044, UTMOS th 2.55 / 2.88 |

```bash
gh release download v0.11.0 -R tuanpmt/vtts -p 'vtts-*' -D models        # every voice
gh release download v0.11.0 -R tuanpmt/vtts -p 'vtts-jaen-*' -D models   # one voice
```

### Changed
- README, voices.md, the website, the roadmap and the Hugging Face card point to v0.11.0 and the `-v0.11.q8.vtts` file names; voices.md lists which release each file comes from.
- Hugging Face: the v0.11 files are added to the per-voice folders (`en-nu-en/`, `vi-en-nam-1/`, `vi-en-nu-10/`, `ko-en-nu-ko/`, `zh-en-nu-zh/`, `ja-en-nu-ja/`, `pt-en-nu-pt/`, `id-en-nu-id/`, `hi-en-nu-hi/`, `es-en-nu-es/`, `th-en-nu-th/`); the older files stay.

## v0.10.4 (2026-11-20) — `nu-ja` M and `nu-es` M and S model update

A **model update** of two bilingual voices, **Apache-2.0**: the **Japanese + English `nu-ja` quality model (M)** and both models of the **Spanish + English `nu-es`, quality (M) and lite (S)**. All three come from re-distillations with the **improved recipe: a longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**), with the same teachers (`ja_nuja`, `es_nues`) and the same architecture (presets `M-vocos-p-ja-en`, `M-vocos-p-es-en`, `S-vocos-p-es-en`). They replace the v0.6.0 `nu-ja` M and the v0.8.0 `nu-es` M and S; size, speed, token sets (`ja-en`, `es-en`) and text modes (`ja`, `es`) are unchanged, and they run with any firmware since v0.6.0 (ja-en) and v0.8.0 (es-en). The `nu-ja` S of the same re-distillation was not released because its English CER got worse (0.019 → 0.034); the `nu-ja` S stays the v0.6.0 model. The other voices are unchanged.

### Models

| File | Voice | Tier | Params | Size | Replaces |
|---|---|---|---:|---:|---|
| `vtts-jaen-nuja-m-v0.10.4.q8.vtts` | `nu-ja` (female, Japanese + English) | Quality (M) | 1.84M | 2.6 MB | `vtts-jaen-nuja-m-v0.6.q8.vtts` |
| `vtts-esen-nues-m-v0.10.4.q8.vtts` | `nu-es` (female, Spanish + English) | Quality (M) | 1.84M | 2.6 MB | `vtts-esen-nues-m-v0.8.q8.vtts` |
| `vtts-esen-nues-s-v0.10.4.q8.vtts` | `nu-es` (female, Spanish + English) | Lite (S) | 0.83M | 1.2 MB | `vtts-esen-nues-s-v0.8.q8.vtts` |

Use the new `nu-ja` M with the v0.6.0 `vtts-jaen-nuja-s-v0.6.q8.vtts`. On Hugging Face the new files are in `ja-en-nu-ja/` and `es-en-nu-es/` next to the older ones; the card recommends them.

### Quality

The released models and the new ones rendered with the int8 C runtime (`vtts_say --lang ja` / `--lang es`) and scored with the same pipeline on the three out-of-domain sets of 50 sentences (Whisper large-v3; UTMOS). Japanese is scored on readings (both sides converted to kana) and the mixed Japanese set also on the kana and kanji only, because Whisper writes most English words in katakana. All rows were measured with the current front-end, so the old rows differ slightly from the v0.6.0 and v0.8.0 reports. Reports: [ja-student-eval.md](docs/reports/ja-student-eval.md#nu-ja-m-update-v0104), [es-student-eval.md](docs/reports/es-student-eval.md#nu-es-m-and-s-update-v0104).

| `nu-ja` | Japanese CER (reading) | Mixed CER: text / kana and kanji only | English CER | UTMOS (ja / mixed / en) |
|---|---:|---|---:|---|
| M v0.6.0 (joint 20k) | 0.049 | 0.202 / 0.053 | 0.023 | 2.58 / 2.61 / 3.23 |
| **M v0.10.4 (joint 80k)** | **0.035** | 0.220 / 0.054 | **0.018** | **2.75 / 2.77 / 3.45** |
| S v0.6.0 (kept) | 0.050 | 0.236 / 0.049 | 0.019 | 2.30 / 2.27 / 2.75 |
| S joint 80k (not released) | 0.039 | 0.227 / 0.053 | 0.034 | 2.54 / 2.60 / 3.38 |

| `nu-es` | Spanish CER | Mixed CER | English CER | UTMOS (es / mixed / en) |
|---|---:|---:|---:|---|
| M v0.8.0 (joint 20k) | 0.019 | 0.006 | 0.020 | 2.83 / 2.87 / 3.07 |
| **M v0.10.4 (joint 80k)** | **0.001** | **0.005** | **0.014** | **3.09 / 3.04 / 3.41** |
| S v0.8.0 (joint 20k) | 0.017 | 0.009 | 0.019 | 2.54 / 2.50 / 2.81 |
| **S v0.10.4 (joint 80k)** | **0.015** | 0.011 | 0.021 | **2.93 / 2.94 / 3.29** |

- `nu-ja` M: UTMOS +0.15 to +0.23, Japanese reading CER 0.049 → 0.035, English CER lower; on the mixed set the kana-and-kanji CER is the same within 0.001 (the plain CER is higher, mostly English words that Whisper writes in katakana).
- `nu-es` M: UTMOS +0.17 to +0.34 and every CER lower (Spanish 0.019 → 0.001: "noche", "coche" and the phone number now right).
- `nu-es` S: UTMOS +0.39 to +0.48, above the v0.8.0 M on all three sets; Spanish CER lower, mixed and English CER within 0.002 of the v0.8.0 S (one and two words).

### Performance

| Board | `nu-ja` M (v0.10.4) | `nu-es` M (v0.10.4) | `nu-es` S (v0.10.4) |
|---|---|---|---|
| ESP32-P4: RTF / speech starts | 0.26–0.27 / 0.17–0.26 s | 0.27–0.30 / 0.16–0.28 s | 0.18–0.21 / 0.06–0.12 s |
| ESP32-S3: RTF | 0.54–0.55 | 0.56–0.60 | 0.31–0.36 |

RTF from `bench` (four sentences of the main language), speech start from playing the eight website sentences on the ESP32-P4 (underruns only with M on a short first sentence followed by a long one, "Hello! I am ..." and "¡Hola! Soy ...", as before), firmware of this release with only the ja or es front-end: ja-en 6.91 MB on the ESP32-P4 (1.47 MB free in the 8 MB app partition, with the 721 KB JLEX blob) and 6.80 MB on the ESP32-S3; es-en 6.21 MB and 6.10 MB. The eight `nu-ja` Quality clips and the sixteen `nu-es` clips on the website are new ESP32-P4 dumps of these models, 64 kbps MP3, each transcribed again with Whisper large-v3 (`nu-es`: CER 0 on 13 of 16, the others 0.010–0.046; `nu-ja` M: kana-and-kanji CER 0 on three of the six Japanese and mixed clips, 0.09–0.12 on the other three, English 0 and 0; none broken); the dumps match `vtts_say` on a PC (same lengths, correlation ≥ 0.9995). Details: [performance.md](docs/reports/performance.md#nu-ja-m-and-nu-es-m-and-s-update-v0104).

### Changed
- **`nu-ja` M** (`vtts-jaen-nuja-m-v0.10.4.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 2.75 / 2.77 / 3.45 (ja / mixed / en) instead of 2.58 / 2.61 / 3.23, Japanese reading CER 0.035 instead of 0.049.
- **`nu-es` M** (`vtts-esen-nues-m-v0.10.4.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 3.09 / 3.04 / 3.41 (es / mixed / en) instead of 2.83 / 2.87 / 3.07, Spanish CER 0.001 instead of 0.019.
- **`nu-es` S** (`vtts-esen-nues-s-v0.10.4.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 2.93 / 2.94 / 3.29 instead of 2.54 / 2.50 / 2.81.
- Website and voices.md: the eight `nu-ja` Quality and sixteen `nu-es` samples are ESP32-P4 dumps of the new models. README, voices.md, performance.md, the ja and es evaluation reports and the Hugging Face card list the new files.

### Known issues
- The `nu-ja` S stays the v0.6.0 (joint 20k) model: its re-distillation was more natural (UTMOS +0.24 to +0.63) and better on Japanese, but its English CER rose from 0.019 to 0.034 (mostly numbers and short questions) and the mixed kana-and-kanji CER from 0.049 to 0.053. `nam-1` and the other pairs still use the 20k joint stage.
- `nu-ja` M: word-initial vowels and *f* are still weak in some sentences (website clips: 朝の気温 heard as ハサノキ温, ファイル as 配慮), as is the word-initial *r* of v0.6.0.
- ESP32-S3: only `bench` was measured for the new models.
- As before: numbers inside English sentences are read in Japanese by the ja text mode; write them as words in English text.

## v0.10.3 (2026-11-20) — `nu-zh` M and `nu-ko` S model update

A **model update** of two bilingual voices, **Apache-2.0**: the **Chinese (Mandarin) + English `nu-zh` quality model (M)** and the **Korean + English `nu-ko` lite model (S)**. Both come from re-distillations with the **improved recipe: a longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**), with the same teachers (`zh_nuzh`, `ko_nuko`) and the same architecture (presets `M-vocos-p-zh-en`, `S-vocos-p-ko-en`). They replace the v0.5.0 files; size, speed, token sets (`zh-en`, `ko-en`) and text modes (`zh`, `ko`) are unchanged, and they run with any firmware since v0.5.0. Both re-distillations also produced the other size; those were not released because one CER got worse: the `nu-zh` S (mixed set, Han-only CER 0.023 → 0.033) and the `nu-ko` M (Korean CER 0.021 → 0.035). The `nu-zh` S and the `nu-ko` M stay the v0.5.0 models. The other voices are unchanged.

### Models

| File | Voice | Tier | Params | Size | Replaces |
|---|---|---|---:|---:|---|
| `vtts-zhen-nuzh-m-v0.10.3.q8.vtts` | `nu-zh` (female, Mandarin + English) | Quality (M) | 1.84M | 2.6 MB | `vtts-zhen-nuzh-m-v0.5.q8.vtts` |
| `vtts-koen-nuko-s-v0.10.3.q8.vtts` | `nu-ko` (female, Korean + English) | Lite (S) | 0.83M | 1.2 MB | `vtts-koen-nuko-s-v0.5.q8.vtts` |

Use them with the v0.5.0 `vtts-zhen-nuzh-s-v0.5.q8.vtts` and `vtts-koen-nuko-m-v0.5.q8.vtts`. On Hugging Face the new files are in `zh-en-nu-zh/` and `ko-en-nu-ko/` next to the older ones; the card recommends them.

### Quality

The v0.5.0 models and the new ones rendered with the int8 C runtime (`vtts_say --lang zh` / `--lang ko`) and scored with the same pipeline on the three out-of-domain sets of 50 sentences (Whisper large-v3; UTMOS). The mixed sets are also scored on the main-script characters only (Han / Hangul), because Whisper writes many English words in Chinese characters or Hangul. All rows were measured with the current front-end, so the v0.5.0 rows differ slightly from the v0.5.0 reports. Reports: [zh-student-eval.md](docs/reports/zh-student-eval.md#nu-zh-m-update-v0103), [ko-student-eval.md](docs/reports/ko-student-eval.md#nu-ko-s-update-v0103).

| `nu-zh` | Mandarin CER | Mixed CER (Han only) | English CER | UTMOS (zh / mixed / en) |
|---|---:|---:|---:|---|
| M v0.5.0 (joint 20k) | 0.023 | 0.047 (0.046) | 0.021 | 3.17 / 3.24 / 3.64 |
| **M v0.10.3 (joint 80k)** | 0.024 | **0.030 (0.015)** | **0.018** | **3.36 / 3.44 / 3.76** |
| S v0.5.0 (kept) | 0.042 | 0.032 (0.023) | 0.034 | 2.90 / 2.96 / 3.35 |
| S joint 80k (not released) | 0.025 | 0.059 (0.033) | 0.021 | 3.11 / 3.25 / 3.56 |

| `nu-ko` | Korean CER | Mixed CER: text / Hangul only | English CER | UTMOS (ko / mixed / en) |
|---|---:|---:|---:|---|
| S v0.5.0 (joint 20k) | 0.045 | 0.361 / 0.056 | 0.024 | 2.68 / 2.65 / 3.18 |
| **S v0.10.3 (joint 80k)** | **0.026** | **0.314 / 0.044** | **0.018** | **3.18 / 3.06 / 3.54** |
| M v0.5.0 (kept) | 0.021 | 0.314 / 0.026 | 0.023 | 2.75 / 2.76 / 3.39 |
| M joint 80k (not released) | 0.035 | 0.352 / 0.043 | 0.028 | 3.14 / 3.33 / 3.87 |

- `nu-zh` M: UTMOS +0.12 to +0.20 on all three sets, mixed CER 0.047 → 0.030 (Han only 0.046 → 0.015), English CER lower, Mandarin CER the same within one character.
- `nu-ko` S: every CER drops (Korean 0.045 → 0.026) and UTMOS rises by 0.36–0.50, above the v0.5.0 M in naturalness.

### Performance

| Board | `nu-zh` M (v0.10.3): RTF / speech starts | `nu-ko` S (v0.10.3): RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.27–0.29 / 0.17–0.29 s | 0.17–0.19 / 0.06–0.11 s |
| ESP32-S3 | 0.55–0.58 / not measured | 0.30–0.33 / not measured |

RTF from `bench` (four sentences of the main language), speech start from playing the eight website sentences on the ESP32-P4 (one underrun with M on the short-then-long "Hello! I am ..." sentence, as with v0.5.0), firmware of this release with only the zh or ko front-end: zh-en 6.32 MB on the ESP32-P4 (2.07 MB free in the 8 MB app partition) and 6.21 MB on the ESP32-S3; ko-en 6.19 MB and 6.08 MB. The eight `nu-zh` Quality and eight `nu-ko` Lite clips on the website are new ESP32-P4 dumps of these models, 64 kbps MP3, each transcribed again with Whisper large-v3 (`nu-zh` M: CER 0 on all eight; `nu-ko` S: Hangul-only CER 0 on four of six Korean and mixed clips, 0.023–0.029 on two (내일 heard as 매일), English 0 and 0.011; none broken); the dumps match `vtts_say` on a PC (same lengths, correlation ≥ 0.9995). Details: [performance.md](docs/reports/performance.md#nu-zh-m-and-nu-ko-s-update-v0103).

### Changed
- **`nu-zh` M** (`vtts-zhen-nuzh-m-v0.10.3.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 3.36 / 3.44 / 3.76 (zh / mixed / en) instead of 3.17 / 3.24 / 3.64, mixed CER 0.030 instead of 0.047.
- **`nu-ko` S** (`vtts-koen-nuko-s-v0.10.3.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 3.18 / 3.06 / 3.54 (ko / mixed / en) instead of 2.68 / 2.65 / 3.18, Korean CER 0.026 instead of 0.045.
- Website and voices.md: the eight `nu-zh` Quality and eight `nu-ko` Lite samples are ESP32-P4 dumps of the new models. README, voices.md, performance.md, the zh and ko evaluation reports and the Hugging Face card list the new files.

### Known issues
- The `nu-zh` S and `nu-ko` M stay the v0.5.0 (joint 20k) models: their re-distillations were more natural (UTMOS +0.2–0.6) but one CER was worse (see above). `nam-1` and the other pairs still use the 20k joint stage.
- ESP32-S3: only `bench` was measured for the new models.
- As before: numbers inside English sentences are read in Mandarin or Korean by the zh and ko text modes; write them as words in English text. "Bluetooth" inside Korean sentences stays a weak word (v0.5.0 report).

## v0.10.2 (2026-11-20) — `nu-10` S model update

A **model update** of the Vietnamese + English voice `nu-10` (female), **lite model (S)**, **Apache-2.0**. It comes from a dedicated re-distillation with the **improved recipe: a longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**), with the same teacher (`nu10_vien_b32`), the same 20,000-sentence distillation pack and the same architecture (preset `S-vocos-p-bi`, 0.82M parameters, 1.2 MB). It replaces the v0.4.0 `nu-10` S; size, speed, token set (`vi-en`) and text modes (`vi`, `en`, `auto`) are unchanged, and it runs with any firmware since v0.4.0. The `nu-10` M stays the v0.9.1 model: the M of the same re-distillation scored 0.09–0.12 UTMOS lower on Vietnamese and mixed text and was not released. The other voices are unchanged.

### Models

| File | Voice | Tier | Params | Size | Replaces |
|---|---|---|---:|---:|---|
| `vtts-vien-nu10-s-v0.10.2.q8.vtts` | `nu-10` (female) | Lite (S) | 0.82M | 1.2 MB | `vtts-vien-nu10-s-v0.4.q8.vtts` |

Use it with the v0.9.1 quality model `vtts-vien-nu10-m-v0.9.1.q8.vtts`. On Hugging Face the new file is in `vi-en-nu-10/` next to the older ones; the card recommends it.

### Quality

The v0.4.0 S and the new S rendered with the int8 C runtime (`vtts_say --lang auto`) and scored with the same pipeline on the three out-of-domain sets of 50 sentences (PhoWhisper-large for Vietnamese, Whisper large-v3 for English and mixed; UTMOS). Report: [bilingual-student-eval.md](docs/reports/bilingual-student-eval.md#nu-10-s-update-v0102).

| `nu-10` | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---|---|---|---|
| S v0.4.0 (joint 20k) | 0.015 / 0.027 | 0.011 / 0.018 | 0.026 / 0.059 | 2.52 / 3.26 / 2.50 |
| **S v0.10.2 (joint 80k)** | **0.010 / 0.015** | **0.008 / 0.010** | **0.016 / 0.039** | **2.90 / 3.73 / 2.92** |
| M v0.9.1 (unchanged) | 0.014 / 0.024 | 0.008 / 0.010 | 0.015 / 0.032 | 3.11 / 3.87 / 3.12 |

Naturalness rises by 0.38–0.47 UTMOS on all three sets and every CER drops (mixed 0.026 → 0.016, the level of the M); the 5–10 kHz noise metrics are unchanged.

### Performance

| Board | Lite model (S, v0.10.2): RTF / speech starts | Quality model (M, v0.9.1): RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.17–0.19 / 0.07–0.14 s | 0.26–0.28 / 0.19–0.35 s |
| ESP32-S3 | 0.30–0.33 / not measured | 0.54–0.57 / 0.35–0.62 s |

S: RTF from `bench` (four Vietnamese sentences), speech start from playing the eight website sentences on the ESP32-P4 (`lang auto`), firmware of this release (vi and en front-ends only): 6.12 MB on the ESP32-P4 (2.27 MB free in the 8 MB app partition), 6.01 MB on the ESP32-S3 (2.38 MB free). M: the v0.9.1 measurement. The eight `nu-10` Lite clips on the website are new ESP32-P4 dumps of this model, 64 kbps MP3, each transcribed again with Whisper (CER 0 for 4 of 8, at most 0.022 for three others; the Vietnamese intro 0.079 from PhoWhisper's reading of "chip ESP32"; none broken); the dumps match `vtts_say` on a PC (same lengths, correlation ≥ 0.9997). Details: [performance.md](docs/reports/performance.md#nu-10-s-update-v0102).

### Changed
- **`nu-10` S** (`vtts-vien-nu10-s-v0.10.2.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 2.90 / 3.73 / 2.92 (vi / en / mixed) instead of 2.52 / 3.26 / 2.50, CER 0.010 / 0.008 / 0.016 instead of 0.015 / 0.011 / 0.026.
- Website and voices.md: the eight `nu-10` Lite samples are ESP32-P4 dumps of the new model. README, voices.md, performance.md, the bilingual evaluation report and the Hugging Face card list the new S.

### Known issues
- `nam-1` and the other pairs still use the 20k joint stage (updates follow).
- The English comparison rows of the `nu-en` report (`ood_en2`) are for the v0.4.0 `nu-10` models; the new S was not scored on `ood_en2`.
- ESP32-S3: only `bench` was measured for the new S.
- As before: brand names inside Vietnamese sentences are the hardest cases; PhoWhisper writes "ESP32" in Vietnamese letters.

## v0.10.1 (2026-11-20) — `nu-en` M and S model update

A **model update** of the English-only voice `nu-en` (female, American English), **quality (M) and lite (S)**, **Apache-2.0**. Both are trained with the **improved distillation recipe: a longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**), with the same teacher (`en_nuen`), the same distillation data, the same front and decoder stages and the same architecture (presets `{M,S}-vocos-p-bi`, 1.83M / 0.82M parameters, 2.6 / 1.2 MB). They replace the v0.9.0 `nu-en` models; size, speed, token set (`vi-en`) and start mode (`en`, header dim `text_mode`) are unchanged, and they run with any firmware since v0.9.0. The other voices are unchanged.

### Models

| File | Voice | Tier | Params | Size | Replaces |
|---|---|---|---:|---:|---|
| `vtts-en-nuen-m-v0.10.1.q8.vtts` | `nu-en` (female) | Quality (M) | 1.83M | 2.6 MB | `vtts-en-nuen-m-v0.9.q8.vtts` |
| `vtts-en-nuen-s-v0.10.1.q8.vtts` | `nu-en` (female) | Lite (S) | 0.82M | 1.2 MB | `vtts-en-nuen-s-v0.9.q8.vtts` |

On Hugging Face the new files are in `en-nu-en/` next to the v0.9 ones; the card recommends the new ones.

### Quality

The v0.9.0 and v0.10.1 models rendered with the int8 C runtime (`vtts_say --lang en`) and scored with the same pipeline on the two English sets of 50 sentences (`ood_en`, `ood_en2`; Whisper large-v3, UTMOS). Report: [en-student-eval.md](docs/reports/en-student-eval.md#nu-en-update-v0101).

| `nu-en` | `ood_en` CER / WER | `ood_en2` CER / WER | UTMOS (ood_en / ood_en2) |
|---|---|---|---|
| M v0.9.0 (joint 20k) | 0.014 / 0.018 | 0.034 / 0.053 | 2.88 / 3.00 |
| **M v0.10.1 (joint 80k)** | 0.012 / 0.018 | 0.024 / 0.034 | **3.56 / 3.56** |
| S v0.9.0 (joint 20k) | 0.015 / 0.022 | 0.027 / 0.043 | 3.00 / 3.08 |
| **S v0.10.1 (joint 80k)** | 0.015 / 0.023 | 0.021 / 0.036 | **3.68 / 3.67** |
| VoxCPM2 `nu-en` (reference voice) | 0.010 / 0.014 | 0.045 / 0.055 | 4.24 / 4.24 |

Naturalness rises by 0.56–0.68 UTMOS for both models on both sets, now above the English of the v0.4.0 `nu-10` M (3.44 / 3.59) and about 0.6 below the reference voice; intelligibility is the same or better (`ood_en2` CER 0.034 → 0.024 for M).

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.21 / 0.07–0.15 s | 0.27–0.29 / 0.17–0.35 s |
| ESP32-S3 | 0.31–0.36 / not measured | 0.56–0.58 / not measured |

RTF from `bench` (four English sentences), speech start from playing the eight website sentences on the ESP32-P4, firmware of this release (vi and en front-ends only): 6.12 MB on the ESP32-P4 (2.27 MB free in the 8 MB app partition), 6.01 MB on the ESP32-S3 (2.38 MB free). The ESP32-S3 numbers are lower than in the v0.9.0 notes (0.41–0.46 / 0.69–0.73) because of the ESP32-S3 SIMD fix of v0.9.1, not because of the models. The 16 `nu-en` clips on the website are new ESP32-P4 dumps of these models, 64 kbps MP3, each transcribed again with Whisper large-v3 (CER 0 for 12 of 16; intro 0.01–0.05, date sentence 0.16 from "9:30" written "9.30"; none broken); the dumps match `vtts_say` on a PC (same lengths, correlation ≥ 0.998). Details: [performance.md](docs/reports/performance.md#nu-en-update-v0101).

### Changed
- **`nu-en` M and S** (`vtts-en-nuen-{m,s}-v0.10.1.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 3.56 / 3.56 (M) and 3.68 / 3.67 (S) instead of 2.88 / 3.00 and 3.00 / 3.08, CER the same or lower.
- Website and voices.md: the 16 `nu-en` samples are ESP32-P4 dumps of the new models. README, voices.md, performance.md, the English evaluation report and the Hugging Face card list the new models.

### Known issues
- As before: "Hello!" before a longer sentence is short and quiet (one playback underrun with M on the ESP32-P4), all-capital words not in the lexicon are spelled ("NASA"), Vietnamese text is not supported by these models.
- ESP32-S3: only `bench` was measured for this release.

## v0.10.0 (2026-11-20) — Thai + English voice `nu-th`

A new bilingual pair with one designed female voice as a quality model (M) and a lite model (S), **Apache-2.0**:

- **Thai + English**, voice `nu-th` (Thai): reads Thai, English and Thai sentences with English words in Latin letters ("สัญญาณ Wi-Fi อ่อนมาก ลองย้าย router มาใกล้ ๆ"). Teacher `th_nuth` trained from random initialization for 120k steps on 55,555 sentences (about 97 h: 27,635 Thai, 8,679 Thai with English words, 19,241 English), all synthesized with VoxCPM2 (Apache-2.0) from the voice `nu-th` only; no recorded corpus and no warm start. Students distilled with the standard chain (front 10k, decoder 30k, joint 20k steps, 20,000-sentence pack).

The earlier voices are unchanged and stay on their releases. **An updated `nu-th` model with the longer joint distillation stage will follow** as a model update of this voice.

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-then-nuth-m-v0.10.q8.vtts` | `nu-th` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-then-nuth-s-v0.10.q8.vtts` | `nu-th` (female) | Lite (S) | 0.83M | 1.2 MB |

Int8, 22.05 kHz, token set `th-en` recorded in the file (162 tokens: the v2 set plus 55 Thai initials, vowels, finals and tones); presets `{M,S}-vocos-p-th-en`. No blob beyond the English lexicon: the Thai tables and word list (about 80 KB) are compiled into the firmware.

### Quality

Three out-of-domain sets of 50 sentences (`ood_th`, `mixed_th`, `ood_en`; none in the training text), Whisper large-v3, audio from the int8 C runtime, and the same Thai and mixed sentences synthesized by the VoxCPM2 `nu-th` voice as a reference. Thai has no spaces between words, so the CER counts Thai characters with spaces removed; the mixed CER counts only the Thai characters, because Whisper writes most English words of a Thai sentence in Thai script. Report: [th-student-eval.md](docs/reports/th-student-eval.md).

| Model | Thai CER | English CER | Mixed CER (Thai only) | UTMOS (th / en / mixed) |
|---|---:|---:|---:|---|
| `nu-th` M | 0.044 | 0.018 | 0.043 | 2.88 / 3.51 / 2.95 |
| `nu-th` S | 0.053 | 0.030 | 0.044 | 2.55 / 3.06 / 2.58 |
| VoxCPM2 `nu-th` (reference voice) | 0.076 | — | 0.022 | 3.97 / — / 4.00 |

The reference voice misreads raw digits and dates and sometimes adds words after a sentence; without the numbers group it scores 0.039 against 0.054 (M) and 0.050 (S). Plain mixed CER against the text: 0.100 (M), 0.116 (S), 0.086 (reference).

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.19 / 0.07–0.13 s | 0.26–0.28 / 0.18–0.33 s |
| ESP32-S3 | 0.31–0.33 / not measured | 0.55–0.57 / not measured |

RTF from `bench` (four Thai sentences; on the ESP32-S3 with the current firmware, whose dot-product kernels no longer use `loopnez`), speech start from playing the eight website sentences on the ESP32-P4. Firmware with only the Thai front-end compiled in: 6.28 MB on the ESP32-P4 (2.10 MB free in the 8 MB app partition), 6.17 MB on the ESP32-S3 (2.22 MB free). Every website clip is the ESP32-P4's own output, matches `vtts_say` on a PC and was transcribed again with Whisper before publishing (16 clips, none broken). Details: [performance.md](docs/reports/performance.md#thai--english-v0100).

### Flash a board

```bash
gh release download v0.10.0 -R tuanpmt/vtts -p 'vtts-then-*' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-then-nuth-s-v0.10.q8.vtts ../../models/vtts-then-nuth-m-v0.10.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`. The pair has one text mode, `th` (the default for its models), which also reads English.

### Added
- **Thai + English voice `nu-th`** (M and S), with 16 on-chip samples (ESP32-P4 dumps of 8 sentences × 2 models, each checked with Whisper) on the website and a Thai entry in the language picker.
- Report [th-student-eval.md](docs/reports/th-student-eval.md), a v0.10.0 section in [performance.md](docs/reports/performance.md), Hugging Face folder `th-en-nu-th/`.
- Eval set `ood_th`: one sentence that shared an eight-word run with the training text replaced by a new one.

### Known issues
- **Tone of the question particle ไหม:** heard as ใหม่ ("new") in 4 of the 6 test sentences with it (both models; never for the reference voice). Questions stay clear from context.
- **กรุณา is read kru-naa** instead of ka-ru-naa (the front-end reads กร as a cluster here); Whisper writes "กลูนา". It will be fixed with an exception-table entry in a front-end update.
- **Numbers and acronyms in English sentences are read in Thai** ("15 percent" with a Thai number), as in the other single-mode pairs; write them as words.
- **Short English names inside Thai sentences** (Bangkok, Tokyo, Toyota) are less clear than with the reference voice, more so with S.
- A very short first sentence followed by a longer one ("Hello! I am ...") can cause one playback underrun (a short gap) with M, as with the other pairs.

## v0.9.1 (2026-11-20) — `nu-10` M model update and ESP32-S3 SIMD fix

A **model update** of the Vietnamese + English voice `nu-10` (female), quality model (M) only, **Apache-2.0**. It is trained with the **improved distillation recipe: a longer joint stage** (front 10k, decoder 30k, **joint 80k steps instead of 20k**), with the same teacher (`nu10_vien_b32`), the same 20,000-sentence distillation pack and the same architecture (preset `M-vocos-p-bi`, 1.83M parameters, 2.6 MB). It replaces the v0.4.0 `nu-10` M; size, speed, token set (`vi-en`) and text modes (`vi`, `en`, `auto`) are unchanged, and it runs with any firmware since v0.4.0. The `nu-10` S stays the v0.4.0 model for now (its update follows); the other voices are unchanged.

The release also ships the **ESP32-S3 SIMD fix**: the ESP32-S3 output is identical to the ESP32-P4 again and about 20% faster for every voice (below; rebuild the firmware from this release).

### Models

| File | Voice | Tier | Params | Size | Replaces |
|---|---|---|---:|---:|---|
| `vtts-vien-nu10-m-v0.9.1.q8.vtts` | `nu-10` (female) | Quality (M) | 1.83M | 2.6 MB | `vtts-vien-nu10-m-v0.4.q8.vtts` |

Use it with the v0.4.0 lite model `vtts-vien-nu10-s-v0.4.q8.vtts`. On Hugging Face both M files are in `vi-en-nu-10/`; the card recommends the new one.

### Quality

The v0.4.0 M and the new M rendered with the int8 C runtime and scored with the same pipeline on the three out-of-domain sets of 50 sentences (PhoWhisper-large for Vietnamese, Whisper large-v3 for English and mixed; UTMOS for naturalness). Report: [bilingual-student-eval.md](docs/reports/bilingual-student-eval.md#nu-10-m-update-v091).

| `nu-10` M | Vietnamese CER / WER | English CER / WER | Mixed CER / WER | UTMOS (vi / en / mixed) |
|---|---|---|---|---|
| v0.4.0 (joint 20k) | 0.014 / 0.027 | 0.008 / 0.010 | 0.015 / 0.041 | 2.73 / 3.44 / 2.70 |
| **v0.9.1 (joint 80k)** | 0.014 / 0.024 | 0.008 / 0.010 | 0.015 / 0.032 | **3.11 / 3.87 / 3.12** |

Naturalness rises by about 0.4 UTMOS on all three sets at the same intelligibility.

### Performance

| Board | Quality model (M): RTF / speech starts | Lite model (S, v0.4.0): RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.26–0.28 / 0.19–0.35 s | 0.18–0.19 / 0.07–0.14 s |
| ESP32-S3 | 0.54–0.57 / 0.35–0.62 s | 0.31–0.33 / 0.20–0.33 s |

RTF from `bench` (four Vietnamese sentences), speech start from playing the eight website sentences (`lang auto`), firmware of this release with the ESP32-S3 fix (the vi and en front-ends only): 6.12 MB on the ESP32-P4 (2.27 MB free in the 8 MB app partition), 6.01 MB on the ESP32-S3 (2.38 MB free). The eight `nu-10` Quality clips on the website are new ESP32-P4 dumps of this model, 64 kbps MP3, each transcribed again with Whisper (CER 0 for 7 of 8; the Vietnamese intro 0.07, PhoWhisper writing "chip ESP32" as "chiếc est d ba hai", as with the v0.4.0 clip; none broken; no underrun in 32 playbacks on the two chips). The ESP32-S3 dumps of the same 16 sentences have the same length as the ESP32-P4's and differ by at most 1 LSB. Details: [docs/reports/performance.md](docs/reports/performance.md#nu-10-m-update-v091).

### Flash a board

```bash
gh release download v0.9.1 -R tuanpmt/vtts -p 'vtts-vien-*' -D models
gh release download v0.4.0 -R tuanpmt/vtts -p 'vtts-vien-nu10-s-*' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-vien-nu10-s-v0.4.q8.vtts ../../models/vtts-vien-nu10-m-v0.9.1.q8.vtts -p PORT flash monitor
```

### Firmware (ESP32-S3 fix)
- **ESP32-S3: output identical to the ESP32-P4 again, and faster.** The bursts and changed phoneme durations on the ESP32-S3 (from v0.4.0 on; lowered but not removed by the two-core fix of v0.7.0) came from the S3 SIMD dot-product kernel: its zero-overhead loop (`loopnez`) around the 128-bit loads now and then returned a wrong sum. The kernels now use branch loops. Over id-en, hi-en and es-en, 144 of 144 two-core and 48 of 48 one-core test dumps were identical to the ESP32-P4. The output staging of v0.7.0 is removed, so the S3 is faster: RTF (`bench`, two cores) M 0.55–0.58, S 0.31–0.32 (was 0.68–0.71 and 0.41–0.43). The issue has been reported to Espressif.
- `say_parity --poison/--fast` and `make ws_state`: checks that stale memory never changes the output.

### Changed
- **`nu-10` M** (`vtts-vien-nu10-m-v0.9.1.q8.vtts`): joint distillation stage 80k steps instead of 20k; UTMOS 3.11 / 3.87 / 3.12 (vi / en / mixed) instead of 2.73 / 3.44 / 2.70, CER unchanged.
- Website and voices.md: the eight `nu-10` Quality samples are ESP32-P4 dumps of the new model. README, voices.md, performance.md, the Hugging Face card and the bilingual evaluation report list the new M.

### Known issues
- Only the `nu-10` M is updated; `nu-10` S, `nam-1` and the other pairs still use the 20k joint stage (updates follow).
- The English comparison rows of the `nu-en` report (`ood_en2`) are for the v0.4.0 `nu-10` M; the new M was not scored on `ood_en2`.
- As before: brand names inside Vietnamese sentences are the hardest cases, and a very short first sentence ("Hello!") before a long one can cause one playback underrun with M.

## v0.9.0 (2026-11-20) — English voice `nu-en`

The first **English-only** voice, as a quality model (M) and a lite model (S), **Apache-2.0**:

- **English (American)**, voice `nu-en` (female, a VoxCPM2 designed voice). It reads English only: prompts, numbers, dates, times, money, units and abbreviations through the on-device English front-end (CMUdict, letter-to-sound rules, normalizer). Use it in the `en` text mode; the files start in it on their own (below). The teacher `en_nuen` was trained for 60k steps on speech synthesized with VoxCPM2 (Apache-2.0) from the voice `nu-en` only, 19,241 English sentences (about 30 h), starting from the `nu-10` teacher (itself trained from random initialization on VoxCPM2 audio). Students distilled with the standard chain (front 10k, decoder 30k, joint 20k steps).

The bilingual voices of v0.4.0 to v0.8.0 are unchanged and stay on their releases. **An improved distillation recipe (a longer joint stage) is being applied; `nu-en` will get an updated model soon**, as a model update of this voice.

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-en-nuen-m-v0.9.q8.vtts` | `nu-en` (female) | Quality (M) | 1.83M | 2.6 MB |
| `vtts-en-nuen-s-v0.9.q8.vtts` | `nu-en` (female) | Lite (S) | 0.82M | 1.2 MB |

Int8, 22.05 kHz, token set `vi-en` (107 tokens; only the English ARPAbet part is trained), presets `{M,S}-vocos-p-bi`. The files record the text mode `en` in the new optional header dim `text_mode`, so the firmware and `vtts_say` start them in English rather than the vi-en default `vi`. No blob beyond the English lexicon.

### Quality

Two out-of-domain English sets of 50 sentences: `ood_en` (the English set of every pair) and the new `ood_en2` (numbers, dates and times, short commands, units and money, abbreviations), none in the training text. Whisper large-v3, audio from the int8 C runtime, compared with the English of the bilingual `nu-10` voice and with the VoxCPM2 `nu-en` voice the students learned from. Report: [en-student-eval.md](docs/reports/en-student-eval.md).

| Model | `ood_en` CER / WER | `ood_en2` CER / WER | UTMOS (ood_en / ood_en2) |
|---|---|---|---|
| `nu-en` M | 0.014 / 0.018 | 0.034 / 0.053 | 2.88 / 3.00 |
| `nu-en` S | 0.015 / 0.022 | 0.027 / 0.043 | 3.00 / 3.08 |
| `nu-10` M (vi-en, `lang en`) | 0.008 / 0.010 | 0.033 / 0.043 | 3.44 / 3.59 |
| `nu-10` S (vi-en, `lang en`) | 0.011 / 0.018 | 0.035 / 0.046 | 3.26 / 3.35 |
| VoxCPM2 `nu-en` (reference voice) | 0.010 / 0.014 | 0.045 / 0.055 | 4.24 / 4.24 |

Intelligibility is at the level of the reference voice; most of the remaining CER is how Whisper writes times and amounts ("9:30" as "9.30", "64 dollars and 20 cents" as "$64.20"), which costs every system. Naturalness is lower than the English of `nu-10` (see the known issues).

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 | 0.18–0.21 / 0.07–0.14 s | 0.27–0.29 / 0.17–0.35 s |
| ESP32-S3 | 0.41–0.46 / not measured | 0.69–0.73 / not measured |

RTF from `bench` (four English sentences), speech start from playing the eight website sentences. Firmware with only the always-built front-ends (vi, en): 6.12 MB on the ESP32-P4 (2.27 MB free in the 8 MB app partition), 6.01 MB on the ESP32-S3 (2.38 MB free). Every website clip is the ESP32-P4's own output and was transcribed again with Whisper before publishing (16 clips, none broken). Details: [docs/reports/performance.md](docs/reports/performance.md#english-v090).

### Flash a board

```bash
gh release download v0.9.0 -R tuanpmt/vtts -p 'vtts-en-*' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-en-nuen-s-v0.9.q8.vtts ../../models/vtts-en-nuen-m-v0.9.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`. The start-up log shows `token set vi-en (header), lang en` for both models. Use a firmware built from this release: older firmware ignores the new header dim and starts these models in `vi` (then type `lang en` once per model).

### Added
- **English voice `nu-en`** (M and S), first in the website's language picker (🇬🇧) and in the README, with 16 on-chip samples (ESP32-P4 dumps of 8 sentences × 2 models, each checked with Whisper).
- **Header dim `text_mode`**: the text mode a model starts in, up to 4 ASCII characters packed little-endian ([model format](docs/model-format.md#optional-dims)). C: `vtts_model.text_mode`, `vtts_text_model_lang()` (the firmware and `vtts_say` use it; without the dim, the token set's first mode as before). Python: `pack_text_mode`, `set_dims`, `read_tensors` in `vtts.export.format`, `export_student.py --text-mode`, `scripts/student/set_text_mode.py` for exported files.
- Firmware `bench` in `lang en` uses four English sentences (before: the Vietnamese ones).
- Eval set `eval/sets/ood_en2.jsonl` (50 English sentences: numbers, dates and times, commands, units and money, abbreviations; held out from the English training text). Report [en-student-eval.md](docs/reports/en-student-eval.md), a v0.9.0 section in [performance.md](docs/reports/performance.md), Hugging Face folder `en-nu-en/`.

### Known issues
- **Naturalness below the bilingual voices' English:** UTMOS 2.88–3.08 against 3.26–3.59 for `nu-10`'s English and 4.24 for the reference voice. The updated model with the longer joint stage is meant to close part of this gap.
- **A short first sentence is quiet:** "Hello!" before a longer sentence is short and soft, and Whisper drops it in the website's intro clip (both models).
- **All-capital words are spelled:** "NASA" is read N-A-S-A, as are other all-capital words that are not in the lexicon; write them in lower case ("Nasa") to read them as a word.
- **Vietnamese text is not supported** by these models (the vi-en token set is shared, but only English was trained); `lang vi` and `lang auto` give poor results.
- **ESP32-S3:** only `bench` was measured for this release (RTF 0.41–0.46 S, 0.69–0.73 M); speech start and two-core determinism were not re-checked. As for the earlier pairs, two cores on the ESP32-S3 can now and then change a dump slightly; `cores 1` gives exact output.

## v0.8.0 (2026-11-20) — Indonesian + English, Hindi + English and Spanish + English voices

Three new bilingual pairs, each with one designed female voice as a quality model (M) and a lite model (S), **Apache-2.0**:

- **Indonesian + English**, voice `nu-id` (about 40, Indonesian): reads Indonesian, English and Indonesian sentences with English words ("Sinyal Wi-Fi lemah sekali, coba dekatkan router-nya."). Teacher `id_nuid` trained from random initialization for 120k steps on 45,857 sentences (20,025 Indonesian, 6,591 Indonesian with English words, 19,241 English).
- **Hindi + English**, voice `nu-hi` (about 40, Hindi): reads Hindi in Devanagari, English, and Hinglish sentences with the English words in Latin letters ("Wi-Fi का signal बहुत कमज़ोर है"). Teacher `hi_nuhi`, 120k steps on 48,296 sentences (23,247 Hindi, 5,808 Hindi with English words, 19,241 English).
- **Spanish + English**, voice `nu-es` (about 40, Spanish): reads Spanish, English and Spanish sentences with English words ("El deadline del proyecto es el 20/11/2026."). Teacher `es_nues`, 120k steps on 48,336 sentences (21,940 Spanish, 7,155 Spanish with English words, 19,241 English).

All speech was synthesized with VoxCPM2 (Apache-2.0) from the pair's designed voice only; no recorded corpus and no warm start. Students distilled with the standard chain (front 10k, decoder 30k, joint 20k steps, 20,000-sentence pack). The earlier voices are unchanged and stay on their releases.

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-iden-nuid-m-v0.8.q8.vtts` | `nu-id` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-iden-nuid-s-v0.8.q8.vtts` | `nu-id` (female) | Lite (S) | 0.83M | 1.2 MB |
| `vtts-hien-nuhi-m-v0.8.q8.vtts` | `nu-hi` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-hien-nuhi-s-v0.8.q8.vtts` | `nu-hi` (female) | Lite (S) | 0.83M | 1.2 MB |
| `vtts-esen-nues-m-v0.8.q8.vtts` | `nu-es` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-esen-nues-s-v0.8.q8.vtts` | `nu-es` (female) | Lite (S) | 0.83M | 1.2 MB |

Int8, 22.05 kHz, token set recorded in the file: `id-en` (141 tokens: the v2 set plus 34 Indonesian tokens), `hi-en` (157: plus 50 Hindi phonemes), `es-en` (138: plus 31 Spanish tokens); presets `{M,S}-vocos-p-{id,hi,es}-en`. No blob beyond the English lexicon for any of them.

### Quality

Three out-of-domain sets of 50 sentences per pair (`ood_<L>`, `mixed_<L>`, `ood_en`; `ood_hi` and `mixed_hi` are new), Whisper large-v3, audio from the int8 C runtime, and the same main-language and mixed sentences synthesized by the pair's VoxCPM2 voice as a reference. Reports: [id-en](docs/reports/id-student-eval.md), [hi-en](docs/reports/hi-student-eval.md), [es-en](docs/reports/es-student-eval.md).

| Model | Main-language CER | English CER | Mixed CER | UTMOS (main / en / mixed) |
|---|---:|---:|---:|---|
| `nu-id` M | 0.011 | 0.022 | 0.018 | 2.42 / 3.05 / 2.57 |
| `nu-id` S | 0.011 | 0.059 | 0.015 | 2.14 / 2.63 / 2.25 |
| VoxCPM2 `nu-id` (reference voice) | 0.023 | — | 0.042 | 3.07 / — / 3.22 |
| `nu-hi` M | 0.094 | 0.053 | 0.054 (Devanagari only) | 2.84 / 3.09 / 2.91 |
| `nu-hi` S | 0.092 | 0.028 | 0.056 (Devanagari only) | 2.84 / 3.03 / 2.88 |
| VoxCPM2 `nu-hi` (reference voice) | 0.069 | — | 0.065 (Devanagari only) | 3.41 / — / 3.55 |
| `nu-es` M | 0.019 | 0.020 | 0.006 | 2.83 / 3.07 / 2.87 |
| `nu-es` S | 0.017 | 0.019 | 0.009 | 2.54 / 2.81 / 2.50 |
| VoxCPM2 `nu-es` (reference voice) | 0.020 | — | 0.037 | 3.50 / — / 3.57 |

The reference voices misread raw digits; without the numbers group Indonesian is at 0.002–0.003 and Spanish at 0.006–0.008. Hindi CER includes Whisper's Hindi spelling (nukta, chandrabindu); with that merged and without numbers it is 0.081 (M) / 0.085 (S) against 0.035 for the reference voice (see the known issues). The Hindi mixed CER counts only the Devanagari of the text, because Whisper writes the English words in Devanagari (plain CER 0.28–0.29 for every system, the reference included).

### Performance

| Pair | Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|---|
| id-en | ESP32-P4 | 0.18–0.20 / 0.07–0.12 s | 0.26–0.28 / 0.17–0.28 s |
| id-en | ESP32-S3 | 0.40–0.44 / 0.23–0.39 s | 0.67–0.70 / 0.38–0.72 s |
| hi-en | ESP32-P4 | 0.18–0.20 / 0.07–0.12 s | 0.27–0.28 / 0.17–0.30 s |
| hi-en | ESP32-S3 | 0.40–0.45 / 0.23–0.41 s | 0.68–0.70 / 0.39–0.78 s |
| es-en | ESP32-P4 | 0.17–0.21 / 0.06–0.11 s | 0.26–0.29 / 0.15–0.28 s |
| es-en | ESP32-S3 | 0.41–0.46 / 0.20–0.39 s | 0.68–0.73 / 0.32–0.71 s |

RTF from `bench` (four sentences of the main language), speech start from playing the eight website sentences. One firmware per pair with only its front-end compiled in: 6.20–6.21 MB on the ESP32-P4 (2.17–2.19 MB free in the 8 MB app partition), 6.09–6.10 MB on the ESP32-S3 (2.29–2.30 MB free). Every website clip is the ESP32-P4's own output, matches `vtts_say` on a PC and was transcribed again with Whisper before publishing (48 clips, none broken). Details: [docs/reports/performance.md](docs/reports/performance.md#indonesian--english-hindi--english-and-spanish--english-v080).

### Flash a board

```bash
gh release download v0.8.0 -R tuanpmt/vtts -p 'vtts-esen-*' -D models   # or vtts-iden-* / vtts-hien-*
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-esen-nues-s-v0.8.q8.vtts ../../models/vtts-esen-nues-m-v0.8.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`. Each pair has one text mode (`id`, `hi`, `es`, the default for its models), which also reads English.

### Front-end
- **Language of a sentence in the Latin-script pairs** (es, id, pt, fr, de, it, tr, pl, nl, sv, no, da, fi, ms, tl, sw) and the `vi` mode: a whole English sentence is now read in English (numbers included) instead of word by word, where English words that fit the language's spelling (I, a, am, time, minutes) were read in the main language (pt: 16% of the words of `ood_en`, es 21%, id 18%, now 0). Sentences of the language with English terms keep their word tags. Python and C, same ids; see [pronunciation rules](docs/frontend/pronunciation-rules.md#language-of-a-sentence). Measured on the new models, English CER with word tags only → with the sentence decision: `nu-id` M 0.070 → 0.022, S 0.106 → 0.059; `nu-es` M 0.056 → 0.020, S 0.064 → 0.019.
- **Portuguese (v0.7.0) users get better English without new models:** update the runtime / rebuild the firmware from this release and the same `nu-pt` files read whole English sentences in English (English CER 0.047 → 0.012 for M and 0.065 → 0.014 for S in one run; Portuguese and mixed sentences unchanged). This fixes the first known issue of v0.7.0.

### Added
- **Indonesian + English voice `nu-id`, Hindi + English voice `nu-hi` and Spanish + English voice `nu-es`** (M and S each), with 48 on-chip samples (ESP32-P4 dumps of 8 sentences × 2 models per pair, each checked with Whisper) on the website and Indonesian, Hindi and Spanish entries in the language picker.
- Reports [id-student-eval.md](docs/reports/id-student-eval.md), [hi-student-eval.md](docs/reports/hi-student-eval.md), [es-student-eval.md](docs/reports/es-student-eval.md), a v0.8.0 section in [performance.md](docs/reports/performance.md), Hugging Face folders `id-en-nu-id/`, `hi-en-nu-hi/`, `es-en-nu-es/`.
- Eval sets `eval/sets/ood_hi.jsonl` and `mixed_hi.jsonl` (50 sentences each, held out from the training text); `main_script_cer` (and `scripts/eval/mixed_cer.py`) supports `hi` (Devanagari only).

### Known issues
- **Hindi: the first word of a sentence is often misheard.** Its first consonant is weak or heard as another one ("बैठक" → "वैटक", "राहुल" → "नाहूं"): Whisper gets the first word wrong in 28 (M) / 23 (S) of 50 sentences against 13 for the reference voice. Hindi CER is about twice the reference voice's once Whisper's spelling variants are set aside. Hindi is understandable but the weakest of the released pairs.
- **ESP32-S3 with two cores is not fully deterministic.** The two-core fix of v0.7.0 lowered but did not remove the PSRAM errors: 15 of 16 id-en, 10 of 16 hi-en and 12 of 16 es-en dumps matched the ESP32-P4; the others have a short burst or a changed token duration. `cores 1` gives exact output (slower). The ESP32-P4 is not affected.
- **Hindi: numbers and acronyms in English sentences are read in Hindi** ("28 degrees" → अट्ठाईस degrees, "ESP32" with Hindi letter names); write them as words. In the Latin-script pairs (id, es) whole English sentences read numbers in English.
- **Indonesian S on English:** Whisper sometimes hears an accented English sentence as Indonesian (2 of 50 clips), English CER 0.059 for S against 0.022 for M.
- A very short first sentence followed by a longer one ("Halo! Saya ...", "नमस्ते! मैं ...", "¡Hola! Soy ...") can cause one playback underrun (a short gap), as with the other pairs.

## v0.7.0 (2026-11-20) — Portuguese (Brazil) + English voice

A new bilingual pair with one designed female voice as a quality model (M) and a lite model (S), **Apache-2.0**:

- **Portuguese (Brazil) + English**, voice `nu-pt` (about 40, Brazilian Portuguese). One voice reads Portuguese, English and Portuguese sentences with English words ("O sinal do Wi-Fi está fraco, aproxime um pouco o router."); each Latin word is tagged Portuguese or English on the chip (Portuguese letters and word list, English word list, CamelCase, spelling). The teacher `pt_nupt` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 (Apache-2.0) from the designed voice `nu-pt` only: 45,191 sentences (19,583 Brazilian Portuguese, 6,367 Portuguese with English words, 19,241 English) read by the same voice. Students distilled with the standard chain (front 10k, decoder 30k, joint 20k steps, 20,000-sentence pack).

No recorded corpus and no warm start. The earlier voices are unchanged. This release also ships the firmware fixes, four new front-ends and the faster distillation listed below.

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-pten-nupt-m-v0.7.q8.vtts` | `nu-pt` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-pten-nupt-s-v0.7.q8.vtts` | `nu-pt` (female) | Lite (S) | 0.83M | 1.2 MB |

Int8, 22.05 kHz, token set `pt-en` recorded in the file (vocabulary 150: the v2 tokens plus 43 Brazilian Portuguese phoneme tokens; presets `M-vocos-p-pt-en` and `S-vocos-p-pt-en`). No blob beyond the English lexicon.

### Quality

Three out-of-domain sets of 50 sentences, Whisper large-v3, audio from the int8 C runtime (`--lang pt`), and the same Portuguese and mixed sentences synthesized by the VoxCPM2 voice `nu-pt` as a reference. Report: [docs/reports/pt-student-eval.md](docs/reports/pt-student-eval.md).

| Model | Portuguese CER | English CER | Mixed CER | UTMOS (pt / en / mixed) |
|---|---:|---:|---:|---|
| `nu-pt` M | 0.008 | 0.089 | 0.026 | 2.36 / 2.71 / 2.54 |
| `nu-pt` S | 0.019 | 0.080 | 0.022 | 2.63 / 2.69 / 2.69 |
| VoxCPM2 `nu-pt` (reference voice) | 0.044 | — | 0.044 | 3.99 / — / 3.93 |

The reference voice reads raw digits poorly ("R$ 1.250,00", "15h45"); without the numbers group it scores 0.001 (Portuguese) and 0.016 (mixed), against 0.005 / 0.027 for M and 0.013 / 0.023 for S. The English CER is about four times that of the other pairs: see the known issues.

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 (86-Panel, NANO) | 0.18–0.21 / 0.06–0.12 s | 0.27–0.29 / 0.13–0.29 s |
| ESP32-S3 (Touch-LCD-2.8, EchoEar 2.0) | 0.41–0.45 / 0.21–0.39 s | 0.67–0.71 / 0.28–0.73 s |

RTF from `bench` (four short Portuguese sentences; mean P4 0.19 / 0.28, S3 0.42 / 0.69), speech start from playing the eight website sentences, with the current firmware (ESP32-S3 two-core fix included). Every website clip is the ESP32-P4's own output and was transcribed again with Whisper before publishing; the ESP32-S3 with two cores gave the same audio as the ESP32-P4 for all 16 dumps. Image size in the 8 MB app partition with the two pt-en models and the English lexicon: 6.22 MB on the ESP32-P4 (2.17 MB free), 6.10 MB on the ESP32-S3 (2.28 MB free). Details: [docs/reports/performance.md](docs/reports/performance.md#portuguese-brazil--english-v070).

### Flash a board

```bash
gh release download v0.7.0 -R tuanpmt/vtts -p '*.vtts' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-pten-nupt-s-v0.7.q8.vtts ../../models/vtts-pten-nupt-m-v0.7.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`. On the console type Portuguese, English or mixed text; `model s|m` switches the model. pt-en models have one text mode, `pt` (the default), which also reads English words with the English front-end.

### Firmware
- **Multi-sentence text matches the host render.** `vtts_say` joined the chunks (sentences) of a text without any pause, while the firmware, the teacher and the Python renderers put 150 ms of silence between them, and the firmware also after the last chunk; compared with `vtts_say`, the device's second sentence looked shifted by 0.15 s (correlation 0.11–0.65), although the device audio itself was fine. Now everything joins chunks the same way (`VTTS_CHUNK_GAP_MS`, between chunks only) and `vtts_say` rounds to int16 like the firmware, so ESP32-P4 and ESP32-S3 dumps of single and multi-sentence vi-en text match `vtts_say` with correlation ≥ 0.9995; the only audible change on the device is that the 150 ms of trailing silence is gone. `make -C runtime say_parity MODEL=...` checks the firmware's streaming path against whole-text synthesis sample by sample (host builds use `-ffp-contract=off`, so the two are bit-identical).
- **ESP32-S3: no more random bursts with two cores.** Two cores working on PSRAM data at once now and then gave a wrong int8 layer output (about one in 10^6), heard as short bursts that changed from run to run, mostly with M. The S3 build now stages the int8 layer outputs in 32 KB of internal RAM (`vtts_set_out_stage`), keeps their activations in 40 KB of internal RAM and runs the lighter passes on one core; 22 of 23 two-core test dumps were bit-identical to one core, and `cores 1` stays exact. Cost: RTF on the ESP32-S3 rises from 0.49–0.51 to 0.69–0.70 for M and from 0.29–0.30 to 0.41–0.42 for S (about 1.4x the time; speech starts 0.43–0.93 s instead of 0.31–0.61 s with M) (README and [docs/reports/performance.md](docs/reports/performance.md)); the ESP32-P4 is unchanged. The new `memtest` command reproduces the problem without a model.
- **Optional `debuzz` post filter** (console `debuzz N`, off by default): a high-shelf cut of N dB above about 6 kHz before the speaker; 6 dB takes about 3.3 dB off 5–10 kHz and changes 0–4 kHz by less than 0.05 dB.

### Added
- **Portuguese (Brazil) + English voice `nu-pt`** (M and S), with 16 on-chip samples (ESP32-P4 dumps of 8 sentences × 2 models, each checked with Whisper) on the website and a Portuguese (Brazil) entry in the language picker.
- Report [docs/reports/pt-student-eval.md](docs/reports/pt-student-eval.md), a Portuguese section in [performance.md](docs/reports/performance.md), Hugging Face folder `pt-en-nu-pt/`.
- **Front-ends for Danish, Lao, Khmer and Burmese**, in Python and on the device (C, exact parity, each compiled into the firmware only when an embedded model needs it): token sets `da-en` (158), `lo-en` (163), `km-en` (176) and `my-en` (160), eval sets `ood_*` / `mixed_*`, corpus, teacher-row and preset support. Details in the v0.4.0 list of front-ends for the next pairs below; no models yet.
- **Faster student distillation.** The distill pack is rendered in length-sorted batches with the same per-item noise as before (equal to the per-item path up to float summation order; fp32 by default, `--tf32` to allow TF32) and the frame prosody is computed in a process pool during the render. `train_student.py` always uses a vectorized expand and reads losses only on log steps; opt-in `--fast` (fused AdamW without a per-step host sync, cuDNN autotuning), `--prefetch N`, `--amp`, `--compile`, `--init-decoder`. `run_bilingual_chain.sh` passes `TRAIN_ARGS` to every stage and `DEC_TRAIN_ARGS` to the decoder stage, and saves the assembled float student.

### Known issues
- **Whole English sentences are partly read as Portuguese.** The pt mode tags each Latin word by its spelling, so short or common English words that fit Portuguese spelling (I, a, an, am, me, so, no, time, main, temperature, minutes) are read as Portuguese: 17% of the words of the English eval set. English CER 0.089 (M) and 0.080 (S), about four times the other pairs. Portuguese sentences with English words are not affected (mixed CER 0.022–0.026). An English text mode or a sentence-level language decision for the Latin-script pairs is the planned fix; the models need no retraining.
- **Numbers are always read in Portuguese**, also inside English sentences ("28 degrees" → vinte e oito), and "$42.50" / "1,250" follow the Portuguese separators; write numbers in English sentences as words.
- **Acronyms are spelled with Portuguese letter names** (ESP32 → é-esse-pê trinta e dois), also inside English sentences.
- **Names and English words that fit Portuguese spelling** inside Portuguese sentences can be read the Portuguese way ("Elon" → "O aluno" with S, "router", "gym", "livestream").
- A very short first sentence followed by a longer one ("Olá! Eu sou ...") can cause one playback underrun with M (a short gap), as with the other pairs.

## v0.6.0 (2026-11-20) — Japanese + English voice

A new bilingual pair with one designed female voice as a quality model (M) and a lite model (S), **Apache-2.0**:

- **Japanese + English**, voice `nu-ja` (about 40, Tokyo standard speech). One voice reads Japanese, English and Japanese sentences with English words ("このWi-Fiはpasswordが必要ですか？"); kana and kanji go to the Japanese front-end and Latin words to the English one, on the chip. The teacher `ja_nuja` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 (Apache-2.0) from the designed voice `nu-ja` only: 49,591 sentences of Japanese, Japanese with English words, and English read by the same voice.

No recorded corpus and no warm start. The Vietnamese + English (v0.4.0), Korean + English and Chinese + English (v0.5.0) voices are unchanged.

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-jaen-nuja-m-v0.6.q8.vtts` | `nu-ja` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-jaen-nuja-s-v0.6.q8.vtts` | `nu-ja` (female) | Lite (S) | 0.83M | 1.2 MB |

Int8, 22.05 kHz, token set `ja-en` recorded in the file (vocabulary 144: the v2 tokens plus 37 Japanese phoneme tokens; presets `M-vocos-p-ja-en` and `S-vocos-p-ja-en`). The firmware needs the 721 KB `JLEX` blob (`main/lex_ja.bin`: Japanese reading tables and NFKC data), which `build.sh` builds and embeds.

### Quality

Three out-of-domain sets of 50 sentences, Whisper large-v3, audio from the int8 C runtime (`--lang ja`), and the same Japanese and mixed sentences synthesized by the VoxCPM2 voice `nu-ja` as a reference. Report: [docs/reports/ja-student-eval.md](docs/reports/ja-student-eval.md).

| Model | Japanese CER (reading) | English CER | Mixed CER (kana and kanji only) | UTMOS (ja / en / mixed) |
|---|---:|---:|---:|---|
| `nu-ja` M | 0.050 | 0.023 | 0.054 | 2.57 / 3.22 / 2.61 |
| `nu-ja` S | 0.053 | 0.019 | 0.049 | 2.30 / 2.76 / 2.28 |
| VoxCPM2 `nu-ja` (reference voice) | 0.023 | — | 0.049 | 3.45 / — / 3.43 |

The Japanese references write some numbers in kanji (十五分) where Whisper writes digits, and kanji/kana spellings differ (いろいろ / 色々), so the orthographic CER (0.097 M, 0.110 S, 0.064 for the reference voice) counts spelling; the reading CER converts both sides to kana with the ja front-end and counts in kana. On the mixed set Whisper writes most English words in katakana (password → パスワード): the plain CER is 0.20 (M), 0.24 (S) and 0.23 for the reference voice itself, and the kana-and-kanji-only CER puts both students at the reference voice's level.

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 (86-Panel, NANO) | 0.17–0.18 / 0.07–0.10 s | 0.25–0.26 / 0.18–0.26 s |
| ESP32-S3 (Touch-LCD-2.8, EchoEar 2.0) | 0.28–0.30 / 0.18–0.25 s | 0.50 / 0.31–0.45 s |

RTF from `bench` (four Japanese sentences), speech start from playing the eight website sentences (Japanese, mixed and English): the same speed as the other pairs. Every website clip is the ESP32-P4's own output and was transcribed again with Whisper before publishing. Image size in the 8 MB app partition with the two ja-en models, the English lexicon and the JLEX blob: 6.90 MB on the ESP32-P4 (1.49 MB free), 6.78 MB on the ESP32-S3 (1.60 MB free). Details: [docs/reports/performance.md](docs/reports/performance.md#japanese--english-v060).

### Flash a board

```bash
gh release download v0.6.0 -R tuanpmt/vtts -p '*.vtts' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-jaen-nuja-s-v0.6.q8.vtts ../../models/vtts-jaen-nuja-m-v0.6.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`. On the console type Japanese, English or mixed text; `model s|m` switches the model. ja-en models have one text mode, `ja` (the default), which also reads English words and English sentences with the English front-end.

### Added
- **Japanese + English voice `nu-ja`** (M and S), with 16 on-chip samples (ESP32-P4 dumps of 8 sentences × 2 models, each checked with Whisper) on the website and a Japanese tab.
- `vtts.eval.cer.ja_reading_cer`: Japanese CER on readings (reference and transcript converted to kana by the ja front-end), optionally over the reference's kana only; `scripts/eval/mixed_cer.py --lang ja` prints it next to the orthographic and main-script CER.
- Report [docs/reports/ja-student-eval.md](docs/reports/ja-student-eval.md), a Japanese section in [performance.md](docs/reports/performance.md), Hugging Face folder `ja-en-nu-ja/`.

### Changed
- **Shorter README:** what vtts is, a table of the released voices (pair, voice, size, RTF on both chips, download links, generated from `docs/site.json`), a four-step quick start, a short "how it works" and links to the documentation. The voice catalog, quality tables, speed table and samples moved to [docs/voices.md](docs/voices.md); the architecture, training steps and repository layout to [docs/architecture.md](docs/architecture.md); the roadmap to [docs/roadmap.md](docs/roadmap.md); the serial console commands and board defaults to the [firmware README](firmware/esp32/README.md#serial-console).
- **Website language picker:** the label reads "Language 🇬🇧:" (English, the language every voice reads, once) and each entry shows only its main-language flag; English-only voices, when they come, are listed first with the English flag.
- **Removed `README.vi.md`** (the Vietnamese translation of the README) and the `*_vi` fields of `docs/site.json`; `scripts/docs/sync_docs.py` no longer generates it.

### Known issues
- **Word-initial *r* is weak** in both ja-en models: リビング can sound like イビング, 冷蔵庫 like 映像この, 来月 like A月. Inside words *r* is fine. The reference voice does not have this; a student refresh is planned.
- **Digits in English sentences are read in Japanese** ("28 degrees" → にじゅうはち), as in the ko-en and zh-en modes: the ja mode normalizes every number in Japanese. This is the English numbers-group error (CER 0.09 M, 0.11 S); write numbers in English sentences as words.
- **Kanji numerals before 分** are read ぶん (三十分 → さんじゅうぶん, 十五分 → じゅうごぶん) instead of ぷん/ふん; digits are read correctly (30分 → さんじゅっぷん). Write minutes with digits.
- **"Bluetooth"** is read poorly inside Japanese sentences (write ブルートゥース); "Zoom" is unclear with the lite model.
- **ESP32-S3, two cores (the default): model M is not deterministic** for ja-en too: 6 of 9 test dumps differ from the ESP32-P4 output (SNR 3–40 dB, differences up to 0.48 full scale, once a changed duration). The lite model S was clean in all 9 dumps for ja-en. `cores 1` gives output identical to the ESP32-P4 at the cost of speed. The ESP32-P4 is not affected; the website samples come from the ESP32-P4.
- A very short first sentence followed by a long one ("Hello! I am ...") can cause one playback underrun with M (a short gap).

## v0.5.0 (2026-11-19) — Korean + English and Chinese + English voices

Two new bilingual pairs, each with one designed female voice as a quality model (M) and a lite model (S), all **Apache-2.0**:

- **Korean + English**, voice `nu-ko` (about 40, Seoul standard speech). One voice reads Korean, English and Korean sentences with English words ("스마트폰을 Wi-Fi에 연결했어요"); Hangul goes to the Korean front-end and Latin words to the English one, on the chip. The teacher `ko_nuko` was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 (Apache-2.0) from the designed voice `nu-ko` only: about 43,600 sentences of Korean, mixed Korean and English, and English read by the same voice.
- **Chinese (Mandarin) + English**, voice `nu-zh` (about 40, Beijing Mandarin). The same voice reads Mandarin, English and Mandarin sentences with English words ("已经通过Bluetooth连接到AirPods"), and the Chinese and English front-ends run on the chip. The teacher (`zh_nuzh`, VITS) was trained from random initialization for 120k steps on speech synthesized with VoxCPM2 (Apache-2.0) in the designed `nu-zh` voice only: 54,636 sentences of Mandarin, Mandarin with English terms and English.

No recorded corpus and no warm start for either teacher. The Vietnamese + English voices of v0.4.0 are unchanged.

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-koen-nuko-m-v0.5.q8.vtts` | `nu-ko` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-koen-nuko-s-v0.5.q8.vtts` | `nu-ko` (female) | Lite (S) | 0.83M | 1.2 MB |
| `vtts-zhen-nuzh-m-v0.5.q8.vtts` | `nu-zh` (female) | Quality (M) | 1.84M | 2.6 MB |
| `vtts-zhen-nuzh-s-v0.5.q8.vtts` | `nu-zh` (female) | Lite (S) | 0.83M | 1.2 MB |

Int8, 22.05 kHz, token set recorded in the file:
- `ko-en`: vocabulary 153, the v2 tokens plus 46 Korean onset, vowel and coda tokens. Presets `M-vocos-p-ko-en` and `S-vocos-p-ko-en`; ko-en needs no blob of its own.
- `zh-en`: 171 tokens, the vi-en set, then Mandarin initials, finals and tones. The firmware needs the 116 KB `ZLEX` blob (`main/lex_zh.bin`), which `build.sh` builds and embeds.

### Quality

Three out-of-domain sets of 50 sentences per pair, Whisper large-v3, audio from the int8 C runtime (`--lang ko` / `--lang zh`). Reports: [docs/reports/ko-student-eval.md](docs/reports/ko-student-eval.md), [docs/reports/zh-student-eval.md](docs/reports/zh-student-eval.md).

**Korean + English**

| Model | Korean CER | English CER | Mixed CER (Hangul only) | UTMOS (ko / en / mixed) |
|---|---:|---:|---:|---|
| `nu-ko` M | 0.021 | 0.023 | 0.024 | 2.75 / 3.39 / 2.75 |
| `nu-ko` S | 0.045 | 0.023 | 0.055 | 2.68 / 3.18 / 2.65 |
| VoxCPM2 `nu-ko` (reference voice) | — | — | 0.016 | — / — / 3.92 |

Whisper writes most English words in Hangul ("Google Drive" → 구글 드라이브), so the plain CER of the mixed set is 0.30 (M), 0.36 (S) and 0.37 for the VoxCPM2 reference voice itself; it measures the transliteration, not the voice. The mixed column counts only errors on the Korean characters of the reference (`main_script_cer`), and the reference voice synthesized through the VoxCPM2 service and scored the same way shows the floor.

**Chinese + English**

| Model | Mandarin CER | Mixed CER | English CER | UTMOS (zh / mixed / en) |
|---|---:|---:|---:|---|
| `nu-zh` M | 0.020 | 0.047 | 0.021 | 3.16 / 3.23 / 3.64 |
| `nu-zh` S | 0.042 | 0.032 | 0.034 | 2.89 / 2.96 / 3.35 |

Whisper sometimes writes an English word of a mixed sentence in Chinese characters (Samsung → 三星) or a Chinese word as a symbol (瓦 → W), so the zh mixed CER (plain CER) is an upper bound.

### Performance

| Board | Pair | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|---|
| ESP32-P4 (86-Panel, NANO) | ko-en | 0.17–0.18 / 0.07–0.10 s | 0.25–0.26 / 0.16–0.27 s |
| ESP32-P4 (86-Panel, NANO) | zh-en | 0.17–0.20 / 0.07–0.11 s | 0.25–0.29 / 0.16–0.29 s |
| ESP32-S3 (Touch-LCD-2.8, EchoEar 2.0) | ko-en | 0.29–0.30 / 0.18–0.26 s | 0.48–0.49 / 0.27–0.47 s |
| ESP32-S3 (Touch-LCD-2.8, EchoEar 2.0) | zh-en | 0.28–0.32 / 0.17–0.27 s | 0.49–0.53 / 0.27–0.48 s |

RTF from `bench` (four sentences of the main language), speech start from playing the eight website sentences (main language, mixed and English): the same speed as the vi-en models. Every website clip is the ESP32-P4's own output and was transcribed again with Whisper before publishing. Image size in the 8 MB app partition, with the two models of one pair and the English lexicon:
- ko-en: 6.40 MB on the ESP32-P4 (1.98 MB free), 6.29 MB on the ESP32-S3 (2.10 MB free).
- zh-en (plus the ZLEX blob): 6.54 MB on the ESP32-P4 (1.85 MB free), 6.42 MB on the ESP32-S3 (1.96 MB free).

Details: [docs/reports/performance.md](docs/reports/performance.md#korean--english-v050) (Korean) and [docs/reports/performance.md](docs/reports/performance.md#chinese--english-v050) (Chinese).

### Flash a board

```bash
gh release download v0.5.0 -R tuanpmt/vtts -p '*.vtts' -D models
cd firmware/esp32
# Korean + English
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-koen-nuko-s-v0.5.q8.vtts ../../models/vtts-koen-nuko-m-v0.5.q8.vtts -p PORT flash monitor
# Chinese + English
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-zhen-nuzh-s-v0.5.q8.vtts ../../models/vtts-zhen-nuzh-m-v0.5.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`. On the console type text in the main language, English or mixed; `model s|m` switches the model. ko-en models have one text mode, `ko` (the default), and zh-en models one, `zh` (the default); both also read English words and English sentences with the English front-end.

### Added
- **Korean + English voice `nu-ko`** (M and S) and **Chinese + English voice `nu-zh`** (M and S), each with 16 on-chip samples (ESP32-P4 dumps of 8 sentences × 2 models, each checked with Whisper) on the website and in the README, and a Korean and a Chinese tab on the website.
- `vtts.eval.cer.main_script_cer`: CER over the main-language characters only (Hangul, Han, kana/kanji, Thai) for mixed sets, where the ASR writes English words in the main script; `scripts/eval/mixed_cer.py` prints the plain and the main-script CER of eval reports next to a reference voice's.
- Reports [docs/reports/ko-student-eval.md](docs/reports/ko-student-eval.md) and [docs/reports/zh-student-eval.md](docs/reports/zh-student-eval.md), Korean and Chinese sections in [performance.md](docs/reports/performance.md), Hugging Face folders `ko-en-nu-ko/` and `zh-en-nu-zh/`.

### Known issues
- **ESP32-S3, two cores (the default):** the output is not deterministic: model M as in v0.4.0, and now also the lite model S for ko-en and zh-en (a token's duration can change, or a short burst appears; zh-en S: 4 of 9 test dumps, peaks up to 0.15 full scale). `cores 1` gives the same output as the ESP32-P4 and the PC at the cost of speed. The ESP32-P4 is not affected; the website samples come from the ESP32-P4.
- **Digits in English sentences are read in Korean / Mandarin** ("The meeting starts at 9:30" → 아홉 시 삼십 분; "November 18" with 十八): the ko and zh modes normalize every number in the main language. Digits inside Korean or Mandarin sentences are read correctly; write numbers in English sentences as words for now. For zh-en this is the whole English numbers-group error (CER 0.12 M, 0.19 S); the other English groups score 0–0.014.
- **"Bluetooth" and "Google Meet"** are read poorly inside Korean sentences, more so at the start of a sentence; writing them in Hangul (블루투스) works.
- S is less accurate than M in Korean (CER 0.045 vs 0.021) and blurs the particle after an English word more often.
- Mandarin: two-character given names (刘洋, 李明) and English names inside Mandarin sentences are the hardest cases.
- A very short first sentence followed by a long one ("Hello! I am ...") can cause one playback underrun (a short gap), as in v0.4.0.

## v0.4.0 (2026-11-19)

First bilingual release: two Vietnamese + English voices, `nam-1` (male) and `nu-10` (female), each as a quality model (M) and a lite model (S), all **Apache-2.0**. One voice reads Vietnamese, English and sentences that mix both ("Đã kết nối Bluetooth với AirPods"); the language is chosen per word on the chip. The teachers were trained from random initialization on speech synthesized with VoxCPM2 (Apache-2.0) from designed voices, about 98 h per voice, with no recorded corpus and no warm start from another model. Every released model is now bilingual (one main language + English); the Vietnamese-only prototype of v0.1–v0.3 is retired (its files stay on those GitHub releases).

### Models

| File | Voice | Tier | Params | Size |
|---|---|---|---:|---:|
| `vtts-vien-nam1-m-v0.4.q8.vtts` | `nam-1` (male) | Quality (M) | 1.83M | 2.6 MB |
| `vtts-vien-nam1-s-v0.4.q8.vtts` | `nam-1` (male) | Lite (S) | 0.82M | 1.2 MB |
| `vtts-vien-nu10-m-v0.4.q8.vtts` | `nu-10` (female) | Quality (M) | 1.83M | 2.6 MB |
| `vtts-vien-nu10-s-v0.4.q8.vtts` | `nu-10` (female) | Lite (S) | 0.82M | 1.2 MB |

Int8, token set `vi-en` (recorded in the file, format revision 1.1), 22.05 kHz.

### Quality

Three out-of-domain sets of 50 sentences (CER from PhoWhisper-large for Vietnamese, Whisper large-v3 for English and mixed; audio from the int8 C runtime). Report: [docs/reports/bilingual-student-eval.md](docs/reports/bilingual-student-eval.md).

| Model | Vietnamese CER | English CER | Mixed CER | UTMOS (vi / en / mixed) |
|---|---:|---:|---:|---|
| `nam-1` M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M | 0.014 | 0.008 | 0.015 | 2.72 / 3.44 / 2.70 |
| `nu-10` S | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

The earlier (warm-started) teachers scored CER 0.002–0.005 (vi), 0.012 (en) and 0.018–0.019 (mixed) with UTMOS 3.4–4.4; the first, unreleased `nam-1` M student 0.021 / 0.014 / 0.035 with UTMOS 2.40 / 3.23 / 2.49, so the clean `nam-1` M is as intelligible and slightly more natural.

### Performance

| Board | Lite model (S): RTF / speech starts | Quality model (M): RTF / speech starts |
|---|---|---|
| ESP32-P4 (86-Panel, NANO) | 0.17–0.19 / 0.06–0.15 s | 0.25–0.27 / 0.17–0.34 s |
| ESP32-S3 (Touch-LCD-2.8, EchoEar 2.0) | 0.29–0.31 / 0.17–0.32 s | 0.50–0.52 / 0.31–0.61 s |

RTF from `bench` and `dump` (no playback), speech start from playing eight Vietnamese, English and mixed sentences; the same for both voices. Measured on an ESP32-P4-86-Panel-ETH-2RO and an ESP32-S3-Touch-LCD-2.8. The S model is larger than the old prototype S (0.82M vs 0.77M parameters), so S is a little slower than in v0.3.2. Details: [docs/reports/performance.md](docs/reports/performance.md).

### Flash a board

```bash
gh release download v0.4.0 -R tuanpmt/vtts -p '*.vtts' -D models
cd firmware/esp32
BOARD=esp32-p4-nano ./build.sh ../../models/vtts-vien-nu10-s-v0.4.q8.vtts ../../models/vtts-vien-nu10-m-v0.4.q8.vtts -p PORT flash monitor
```

`BOARD` is `esp32-p4-86-panel-eth-2ro` (default), `esp32-p4-nano`, `esp32-s3-touch-lcd-2.8` or `echoear`; use the `nam1` files for the male voice. The firmware embeds the English lexicon (1.9 MB). With two vi-en models and only that lexicon the image is 6.35 MB on the ESP32-P4 (86-Panel, 2.03 MB free) and 6.24 MB on the ESP32-S3 (Touch-LCD-2.8, 2.15 MB free) in the 8 MB app partition; `build.sh` also builds and embeds the Chinese and Japanese blobs, which vi-en models do not use (about 0.85 MB more, still within the partition). On the console: `model s|m`, `lang vi|en|auto`.

### Added
- **Dutch, Swedish and Norwegian device front-ends (C):** modes `VTTS_LANG_NL`, `VTTS_LANG_SV`, `VTTS_LANG_NO` of `vtts_text_to_ids_ex` (token sets nl-en, sv-en, no-en, header codes 21, 23, 24) with the sentence split, tagging, scanner normalizer and spelling rules of the Python front-ends, exactly matching `text_to_ids(text, "nl" | "sv" | "no")` (12,101 / 11,940 / 11,912 fixture cases, about 180,000 more in larger random runs, fuzz clean under ASan/UBSan). Tables generated into `vtts_text_nx_tables.h` (no blob, the workspace does not grow). Each language is compiled only with `VTTS_ENABLE_NL` / `_SV` / `_NO`; the firmware enables them from the token sets of its models: about 44 KB of flash for one language, 89 KB for all three. `lang nl|sv|no`, bench sentences, `vtts_say` with nl-en, sv-en and no-en models.
- **Norwegian front-end (Python):** token set `no-en` (code 24; Bokmål with Urban East Norwegian pronunciation; 49 Norwegian tokens from id 107: 9 long and 9 short vowels, the diphthongs ei øy au ai, the schwa, the tone tokens `'1` `'2` and `,`, 23 consonants with the kj- and sj-sounds and five retroflex consonants; vocabulary 156), `text_to_ids(text, "no")` for Norwegian with English words: the Swedish rules of `scand_g2p.py` with Norwegian tables (kj tj, skj sj, hv- gj- hj-, e before r, silent d in god / land / gård / holde, silent g in -ig -lig, the t of -et, tonem 1 for -el -en -et, tonem 2 for plurals in -er), number words morph by morph, `lexicons/no/overrides.tsv`. Normalization with the shared scanner: moderne tellemåte (tjueen, to tusen og tjueseks, hundre og fem, years 1999 → nitten nittini), ordinals with a dot (17. mai, not a sentence end), dates, times (kl. 14.30), kroner with øre (50,-), percent, units, phone numbers, ranges, abbreviations (f.eks., bl.a., osv.). Agreement with eSpeak NG (measuring stick only, its Norwegian voice reads the spelling, not Urban East Norwegian): 44.1% of words read the same, 46.0% same sounds, phoneme error rate 16.2%. Eval sets `ood_no` and `mixed_no`, Wikipedia corpus (Bokmål, rate 5.0 syllables/s), templates (ids nom...); teacher rows, distill packs, presets, CER with lang `no`.
- **Swedish front-end (Python):** token set `sv-en` (code 23; 48 Swedish tokens from id 107: 11 long and 10 short vowels with the ä ö allophones before r, the schwa, the tone tokens `'1` `'2` after the stressed vowel and `,` for a secondary stress, 23 consonants with the sj- and tj-sounds and five retroflex consonants; vocabulary 155), `text_to_ids(text, "sv")` for Swedish with English words. Spelling rules shared with Norwegian (`scand_g2p.py`): sj skj stj tj kj, soft k g sk, dj gj hj lj, -tion, complementary vowel length, retroflex rt rd rn rs rl (also rst), stress from stressed endings and the prefixes be- för-, accent 1 / accent 2 from the stress position and the endings, number words morph by morph, `lexicons/sv/overrides.tsv`. Normalization with the shared scanner: numbers (tjugoett, tvåtusentjugosex, years in hundreds, 1 000 000 with spaces), ordinals (1:a, 3:e, 3 maj), dates, times (kl. 14.30), kronor with öre (50:-), percent, units, phone numbers, ranges, abbreviations (t.ex., bl.a., osv.). Agreement with eSpeak NG (measuring stick only): 70.2% of words read the same, 72.5% same sounds, phoneme error rate 8.0% (eSpeak reads function words in their written form). Eval sets `ood_sv` and `mixed_sv`, Wikipedia corpus without the generated stubs (rate 5.0 syllables/s), templates (ids svm...); teacher rows, distill packs, presets, CER with lang `sv`.
- **Dutch front-end (Python):** token set `nl-en` (code 21; 52 Dutch tokens from id 107: short vowels A E I O Y, long a: e: o: 2: i u y, diphthongs Ei 9y Au, each also stressed, the schwa @ and 21 consonants with x for g/ch, N, S, Z; vocabulary 159), `text_to_ids(text, "nl")` for Dutch with English words: graphemes (ie oe eu ui ij ei au ou aa ee oo uu, ieuw eeuw aai ooi oei), vowel length from open and closed syllables, schwa (unstressed e, -ig, -lijk, prefixes), final devoicing, sch, -isch, -tie, unstressed prefixes be- ge- ver- ont- her- er-, stressed foreign endings, number words morph by morph, `lexicons/nl/overrides.tsv`. Normalization shared with Swedish and Norwegian (`scan_norm.py`, one scanner pass without regular expressions): numbers (eenentwintig, tweeëntwintig, één, years in hundreds), ordinals (1e, 2de, 8ste), dates, times (14.30 uur), euro with cents, percent, units, phone numbers, ranges, abbreviations, codes and acronyms; sentences are not cut after an abbreviation or an initial. Agreement with eSpeak NG (measuring stick only) on held-out Wikipedia sentences: 85.3% of words read the same, 89.8% same sounds, phoneme error rate 2.8% (`scripts/frontend/eval_g2p_espeak.py`). Eval sets `ood_nl` and `mixed_nl`, Wikipedia corpus (rate 5.5 syllables/s) and code-switching templates (ids nlm...); teacher rows, distill packs, presets, CER with lang `nl`.
- **Bilingual device front-end (C):** `vtts_text_to_ids_ex` with modes vi, en and auto (phoneme set v2): English normalization and G2P, per-word language tagging and chunk packing, exactly matching Python (2,018 fixture cases, 13,023 in a larger run, fuzz clean). The English lexicon and letter-to-sound rules ship as a 1.9 MB `VLEX` blob read in place (`scripts/frontend/build_lexicon.py`, `vtts_lex_*`).
- **Language modules** in Python (`src/vtts/frontend/languages.py`) and C (`LANGS`): a new language plugs in a normalizer, a word-to-token function and a tagging rule; see docs/frontend/pronunciation-rules.md.
- **Evaluation of bilingual teachers:** English and mixed out-of-domain sets, language-aware CER/WER, Whisper with a forced language; `nam-1` at 100k: CER 0.005 (vi), 0.015 (en), 0.033 (mixed).
- **Bilingual distillation:** v2 distill packs from a `{text, lang}` corpus, presets `M-vocos-p-bi`, `S-vocos-p-bi` and `M-vocos-p-bi-s3`, `run_bilingual_chain.sh`.
- Firmware command `ids ...` and `say.py --lang` to play token ids from a host front-end.
- **On-device bilingual text:** the firmware embeds the VLEX lexicon (read in place from flash) and uses the bilingual front-end for models with token set v2; `lang vi|en|auto` sets the mode. Same audio as the host front-end on ESP32-P4.
- `render_student_c.py --lang` renders bilingual models through the C runtime for evaluation.
- **Token set in the model file:** optional dim `token_set` (format revision 1.1: v1, vi-en, zh-en, ko-en, ja-en), written by `write_model` / `write_model_int8` and `export_student.py --token-set` (default: from the checkpoint or the vocab size), read with `vtts_token_set()` in C and `token_set_of()` in Python. Files without it map by vocab as before, and older runtimes ignore it.

### Added (front-ends for the next pairs; no released models yet)
- **Chinese front-end (Python):** token set `zh-en` (v2 ids 0–106 unchanged, Mandarin initials, finals and tones from id 107), `text_to_ids(text, "zh")` for Chinese with English words, readings from a default-per-character table plus a polyphone phrase table generated from pypinyin (`scripts/frontend/build_zh_lexicon.py`), Chinese number, date, time and percentage reading; teacher rows with lang `zh` use it.
- **Chinese device front-end (C):** mode `VTTS_LANG_ZH` of `vtts_text_to_ids_ex` (token set zh-en) with Chinese normalization, forward-maximum-matching readings and English words, exactly matching `text_to_ids(text, "zh")` (9,397 fixture cases, 78,017 in a larger run, fuzz clean). The reading tables ship as a 116 KB `ZLEX` blob read in place (`scripts/frontend/build_zh_blob.py`, `vtts_zlex_*`); the text workspace grows by 2 KB. `make -C runtime test` runs all text front-end tests.
- **Chinese on the device:** the firmware picks the text front-end from each model's token set instead of its vocab size, embeds the 116 KB ZLEX blob next to the English lexicon (`build.sh` builds `main/lex_zh.bin`), and accepts `lang zh` for zh-en models (`lang` refuses modes of other token sets; ko-en and ja-en models take `ids` only). `bench` uses Mandarin sentences for zh-en models. Host tool `vtts_say` runs the same text → ids → audio path on a PC.
- **Korean device front-end (C):** mode `VTTS_LANG_KO` of `vtts_text_to_ids_ex` (token set ko-en) with Korean normalization (Sino-Korean and native numbers with counters, dates with 유월/시월, times, decimals, percent, ranges, phone numbers, money, units, product codes in English), the exception table and the ordered pronunciation rules, exactly matching `text_to_ids(text, "ko")` (11,369 fixture cases, 126,277 in a larger run, fuzz clean). The tables are generated into `vtts_text_tables.h` (about 4 KB, no blob); the text workspace grows by 2 KB. The firmware accepts `lang ko` (default for ko-en models), `bench` has Korean sentences, and `vtts_say` runs ko-en models.
- **Greek device front-end (C):** mode `VTTS_LANG_EL` of `vtts_text_to_ids_ex` (token set el-en, model header code 26: `VTTS_TOKSET_EL_EN`) with Greek normalization (numbers with gender from the next word, ordinals, dates with month genitives, times, phone numbers, euros and cents, units and percent, abbreviations, Greek acronyms, Latin words through the English normalizer), the letter, digraph, synizesis and stress rules with the overrides, `;` and U+037E read as `?`, exactly matching `text_to_ids(text, "el")` (11,533 fixture cases, 69,257 more in a larger run, fuzz clean under ASan/UBSan). Tables are generated into `vtts_text_el_tables.h` (no blob); about 34 KB on the ESP32-P4. Compiled only with `VTTS_ENABLE_EL` (default 1 on the host); the firmware builds it only when an embedded model is el-en, accepts `lang el` and has Greek `bench` sentences.
- **Finnish device front-end (C):** mode `VTTS_LANG_FI` of `vtts_text_to_ids_ex` (token set fi-en, model header code 25: `VTTS_TOKSET_FI_EN`) with Finnish normalization (numbers as one word, ordinals with a dot, dates, times with klo, spaces as thousands separators, phone numbers, euros and cents, partitive units and percent, ranges in the elative and illative, abbreviations, acronyms, codes), the spelling, length and stress rules with the number-word stresses, the Latin-script tagging with the neighbour rule for words of both lists and the dot rule of the sentence split, exactly matching `text_to_ids(text, "fi")` (11,545 fixture cases, 69,343 more in a larger run, fuzz clean under ASan/UBSan). Tables are generated into `vtts_text_fi_tables.h` (no blob); about 38 KB on the ESP32-P4. Compiled only with `VTTS_ENABLE_FI` (default 1 on the host); the firmware builds it only when an embedded model is fi-en, accepts `lang fi` and has Finnish `bench` sentences. The runtime's token-set table is indexed by code with designated entries (codes 11-24 stay unknown).
- **Hindi device front-end (C):** mode `VTTS_LANG_HI` of `vtts_text_to_ids_ex` (token set hi-en, model header code 10) with Hindi normalization (numbers 0–99 from the table with sau, hazaar, lakh and crore, decimals, dates, years, times with बजे, rupees and paise, percent, units, ordinals, ranges, phone numbers, product codes, Devanagari digits, the danda as a sentence end), the Devanagari letter, anusvara and schwa-deletion rules and the exception table, exactly matching `text_to_ids(text, "hi")` (10,951 fixture cases, 143,285 more in larger random runs, fuzz clean). The tables are generated into `vtts_text_tables.h` (no blob); the runtime knows token set hi-en (`VTTS_TOKSET_HI_EN`). The firmware accepts `lang hi` (default for hi-en models), `bench` has Hindi sentences, and `vtts_say` runs hi-en models; the front-end adds about 25 KB to the ESP32-P4 image.
- **Japanese device front-end (C):** mode `VTTS_LANG_JA` of `vtts_text_to_ids_ex` (token set ja-en) with Japanese normalization (NFKC, numbers with counters and their sound changes, 万/億/兆, dates, times, money, percent, ranges, phone numbers, units, product codes in English), forward-longest-match readings with the context tables, kanji defaults and 々, kana to phonemes and English words, exactly matching `text_to_ids(text, "ja")` (12,238 fixture cases, 322,134 in a larger run, fuzz clean). The reading tables and the NFKC data ship as a 721 KB `JLEX` blob read in place (`scripts/frontend/build_ja_blob.py`, `vtts_jlex_*`; about 150 ns per lookup on the host); the text workspace is unchanged. The firmware embeds it (`build.sh` builds `main/lex_ja.bin`) and accepts `lang ja` (default for ja-en models), `bench` has Japanese sentences, and `vtts_say --ja` runs ja-en models.
- **Korean front-end (Python):** token set `ko-en` (v2 ids 0–106 unchanged, 46 Korean onset, vowel and coda tokens from id 107), `text_to_ids(text, "ko")` for Korean with English words: Hangul decomposition, the standard pronunciation rules (liaison, neutralization, nasalization, liquidization, aspiration, tensification, palatalization) as an ordered rule table plus an exception table, Sino-Korean and native number reading with counters, dates, times and units; teacher rows with lang `ko` use it. Korean corpus builder `scripts/data/build_ko_corpus.py` (Korean Wikipedia).
- **Japanese front-end (Python):** token set `ja-en` (v2 ids 0–106 unchanged, 37 Japanese phonemes in the style of Open JTalk from id 107; long vowels as repeated vowels, `N` and `cl` as tokens), `text_to_ids(text, "ja")` for Japanese with English words: kana rules, kanji readings by longest match over word, context (after kanji / katakana) and per-kanji tables generated from Open JTalk's dictionary with pyopenjtalk (60,000 entries, 1.3 MB TSV; 98.2% mora agreement with pyopenjtalk on held-out Wikipedia sentences), Japanese numbers with counters and sound changes, dates and times; teacher rows with lang `ja` use it. Japanese corpus builder `scripts/data/build_ja_corpus.py` (Japanese Wikipedia).
- **Spanish front-end (Python):** token set `es-en` (code 6; v2 ids 0–106 unchanged, 31 Spanish tokens from id 107: 5 vowels, the same vowels stressed, glides j/w, 19 consonants; vocabulary 138), `text_to_ids(text, "es")` for Spanish with English words: spelling rules (c/z, g/j, qu/gu, ll/y, r/rr, x, silent h), diphthongs and hiatus, stress from the written accent or the default rules, unstressed function words, an exception table; Spanish numbers (apocope un/veintiún), ordinals, dates, times, money, percentages, units, phone numbers, product codes and acronyms. Code-switching for Latin-script pairs (`frontend/latin.py`): own letters, word lists (`lexicons/es/native.txt`, `lexicons/latin/english.txt`), CamelCase, acronyms, then a Spanish spelling check. Eval sets `ood_es` and `mixed_es`; teacher rows, distill packs, presets and CER with lang `es`.
- **Indonesian front-end (Python):** token set `id-en` (code 7; 34 Indonesian tokens from id 107: six vowels with the schwa `@` and the e of "enak", five stressed vowels, 23 consonants with the glottal stop `?`; vocabulary 141), `text_to_ids(text, "id")` for Indonesian with English words: digraphs ng/ny/sy/kh, final k and apostrophe as a glottal stop, final diphthongs, the two e's by default rules plus an exception table that also covers affixed forms (`lexicons/id/overrides.tsv`, 94 entries), penultimate stress moving off the schwa; Indonesian numbers (sebelas, seratus, seribu, juta), ordinals (ke-3), dates, times (pukul 14.30), rupiah, percentages, units, phone numbers, reduplication (anak2), product codes and acronyms. Code-switching by the Latin-script rules with `lexicons/id/native.txt`. Eval sets `ood_id` and `mixed_id`.
- **Brazilian Portuguese front-end (Python):** token set `pt-en` (code 8; 43 Portuguese tokens from id 107: oral and nasal vowels, stressed vowels with open `E`/`O`, glides j/w, 19 consonants with the tap `r` and the strong `rr`; vocabulary 150), `text_to_ids(text, "pt")` for Portuguese with English words: spelling rules (c/ç, g/j, qu/gu, ch/lh/nh, r/rr, s/z between vowels, x by position), nasal vowels and nasal diphthongs (ão, ãe, õe, -am, -em), falling diphthongs, stress from accents or the default rules, open/closed e/o (accents, -el/-ol, -ela, -osa, exception table), final unstressed e/o read i/u; `lexicons/pt/overrides.tsv` (99 entries). Portuguese numbers (mil e duzentos, dois mil e vinte e seis), ordinals, dates (primeiro de maio), times (14h30), reais with centavos, percentages, units, phone numbers, product codes, acronyms and chat abbreviations (vc, pq). Eval sets `ood_pt` and `mixed_pt`. Latin-script tagging: units and abbreviations of a language's normalizer (kWh, etc) and single letters belong to the language; Latin-script pairs fold other letters with NFKD (º, ª).
- **Spanish, Indonesian and Portuguese device front-ends (C):** modes `VTTS_LANG_ES`, `VTTS_LANG_ID`, `VTTS_LANG_PT` of `vtts_text_to_ids_ex` (token sets es-en, id-en, pt-en, header codes 6–8) with the Latin-script tagging rules, the three normalizers pass by pass (abbreviations, dates, times, phone numbers, money, percent, units, ordinals, ranges, product codes, numbers, reduplication, acronyms), the spelling, stress, nasal and vowel-quality rules and the exception tables, exactly matching `text_to_ids(text, "es" | "id" | "pt")` (11,896 / 11,870 / 11,872 fixture cases; 205,614 in a larger run and 120,000 character-level random strings, all exact; fuzz clean). All tables, including Python's `\w`, `\d`, `isspace` and `lower` classes, are generated into `vtts_text_tables.h` (no blob, about 62 KB of code and tables in the ESP32-P4 firmware); the text workspace is unchanged. The C runtime knows the token sets es-en, id-en and pt-en (they loaded as `unknown` before); the firmware defaults to `es`, `id`, `pt` for these models, `lang es|id|pt` works and `bench` has sentences in each language. C whitespace now matches Python's `str.isspace()` in every mode (U+001C–U+001F, U+0085).
- **Hindi front-end (Python):** token set `hi-en` (code 10; 50 Hindi tokens from id 107: 10 vowels, a nasalization mark `~`, 39 consonants with retroflex, aspirated, flap and nukta consonants; vocabulary 157), `text_to_ids(text, "hi")` for Hindi with English words: Devanagari letters, matras, conjuncts with virama, nukta consonants, anusvara as a homorganic nasal or nasalization, chandrabindu, visarga; schwa deletion (word-final and the medial VC_CV rule, right to left) with `lexicons/hi/overrides.tsv` (27 entries); Hindi numbers from a 0-99 table (`lexicons/hi/numbers.tsv`) with सौ, हज़ार, लाख, करोड़, decimals (दशमलव), dates, times (बजे / बजकर), years (उन्नीस सौ सैंतालीस), rupees with paise, percentages, units, phone numbers, ordinals (10वीं), product codes, Devanagari digits, the danda । and ॥ as sentence ends. Latin words are English; teacher rows, distill packs, presets, the unreadable filter and CER with lang `hi`.
- **Arabic device front-end (C):** `VTTS_LANG_AR` (token set ar-en, code 19, 149 ids) in `vtts_text_to_ids_ex` gives exactly `text_to_ids(text, "ar")`: vowel restoration, pausal reading and stress, `normalize_ar` pass by pass (`runtime/src/vtts_text_ar.c`, tables generated into `vtts_text_ar_tables.h`, no blob, about 108 KB of flash on the ESP32-P4: the app grows by 110,448 bytes). Compiled only with `VTTS_ENABLE_AR` (default 1 on the host; the firmware enables it when an embedded model is ar-en). Parity fixture `text_parity_ar.tsv` (16,325 cases, all exact; about 100,000 more in larger random runs), fuzz in ar mode, `make -C runtime ar_test`; firmware `lang ar` and Arabic bench sentences. In every mode ، ؛ ؟ are stripped from chunk edges and ؟ ؛ ۔ end a sentence.
- **Arabic front-end (Python):** token set `ar-en` (code 19; 42 Arabic tokens from id 107: 28 consonants with the hamza `?` and the emphatics, loanword g v, vowels a i u aa ii uu and the same vowels stressed; vocabulary 149), `text_to_ids(text, "ar")` for Modern Standard Arabic with English words, read in pausal form: vowel restoration from a table of 6,920 frequent words (hand-written from the maintainer's and Claude's own knowledge of Arabic, no entry copied or derived from Tashkeela, SAMA/Buckwalter, Mishkal/Arramooz, CAMeL or any other GPL, LDC or CC BY-SA source; `lexicons/ar/words.tsv`) with proclitics, the article, endings and pronoun suffixes, then word patterns and a default reading; vowel marks in the text are used; spelling exceptions (`lexicons/ar/spelling.tsv`: هذا, ذلك, الله); sun/moon letters, hamzat al-wasl, tāʾ marbūṭa, hamza seats, alif maqṣūra, shadda, tanwin, stress by syllable weight. 85.8% words with all vowels right (4.0% phoneme errors) on the held-out half of the vowelled QCRI WikiNews set (`scripts/frontend/eval_ar_vowels.py`; 78.3% / 6.3% with the first 1,966 entries, 46.9% with the rules alone). Arabic numbers (masculine; ألف/آلاف/ألفا, مليون, مليار; years in the genitive), Arabic-Indic and Eastern digits, ٫ ٬ ٪, dates, times, years with هـ / م, money with the count's noun form (dollar, riyal, dirham, dinar, pound, euro), percentages, units, phone numbers, ranges, product codes, abbreviations; ؟ ؛ ۔ end sentences. Wikipedia sentence rule and rate for `ar`, code-switching templates, eval sets `ood_ar` and `mixed_ar`; teacher rows, distill packs, presets, the unreadable filter and CER (letters without vowel marks) with lang `ar`.
- **Greek front-end (Python):** token set `el-en` (code 26; 32 Greek tokens from id 107: 5 vowels, the same vowels stressed, 21 consonants with θ δ γ χ as `th dh gh x`, the affricates `ts dz`, the velar nasal `ng`, and the glide `j`; vocabulary 139), `text_to_ids(text, "el")` for Greek with English words: Greek script tagging, lower case with accented capitals and the final sigma, vowel digraphs with the dialytika and tonos rules, αυ/ευ before voiced and voiceless sounds, μπ ντ γκ γγ τσ τζ, σ voiced before voiced consonants, synizesis (παιδιά, ήλιος) with `lexicons/el/overrides.tsv` (21 entries), stress from the tonos; Greek numbers with gender agreement guessed from the next word (τρία παιδιά, τρεις ώρες, διακόσιες χιλιάδες), ordinals (1ος, 2η, 21ο), dates with month genitives, times, euros and cents, percentages, units, phone numbers, abbreviations (π.χ., κ.λπ., δηλ.), Greek acronyms (ΔΕΗ, ΟΤΕ as words, others spelled), the Greek question mark `;` read as `?` and the ano teleia. 99.0% phoneme agreement and 99.99% stress agreement with eSpeak NG on 14,470 words of held-out Wikipedia sentences (`scripts/frontend/eval_espeak_fi_el.py`). Mixed templates (`templates_el.txt`), eval sets `ood_el` and `mixed_el`; teacher rows, distill packs, presets, CER with lang `el`.
- **Finnish front-end (Python):** token set `fi-en` (code 25; 35 Finnish tokens from id 107: 8 vowels with ä `ae` and ö `oe`, the same vowels stressed, the length mark `:`, 18 consonants with `ng` and the loan sounds b d g f sh zh; vocabulary 142), `text_to_ids(text, "fi")` for Finnish with English words: phonemic spelling rules, long vowels and consonants from doubled letters, ng/nk, loan letters, first-syllable stress and the stresses of number compounds, `lexicons/fi/overrides.tsv` (19 loanword respellings); Finnish numbers written as one word below a million, ordinals with a dot (3. toukokuuta), dates, times (klo 14.30), euros and cents, percentages and units with the partitive, ranges in the elative and illative, phone numbers, abbreviations (esim., jne., n.), acronyms. A dot before a lower-case word does not end a Finnish sentence; words of both the Finnish and the English list (on, he) follow their neighbours. 99.98% phoneme agreement with eSpeak NG on 10,355 words of held-out Wikipedia sentences (`scripts/frontend/eval_espeak_fi_el.py`). Wikipedia sentence rules for fi and el (`wiki_corpus.py`), mixed templates (`templates_fi.txt`), eval sets `ood_fi` and `mixed_fi`; teacher rows, distill packs, presets, CER with lang `fi`.
- **Burmese device front-end (C):** mode `VTTS_LANG_MY` of `vtts_text_to_ids_ex` (token set my-en, header code 30), compiled with `VTTS_ENABLE_MY` (the firmware enables it only when an embedded model has the my-en token set): Zawgyi detection and conversion, canonical mark order, Burmese normalization on `vtts_text_nsp.c`, syllables, onsets, rhymes and tones with the tables generated into `vtts_text_my_tables.h` (no blob, about 16 KB of flash). Fixture `runtime/test/text_parity_my.tsv` (12,079 cases) matches exactly, `text_test --fuzz-my` under ASan/UBSan; firmware lang `my`, Burmese bench sentences. The Python normalizer reads the Shan digits U+1090–U+1099 as digits.
- **Khmer device front-end (C):** mode `VTTS_LANG_KM` of `vtts_text_to_ids_ex` (token set km-en, header code 31), compiled with `VTTS_ENABLE_KM` (`runtime/include/vtts_langs.h`, 1 for host builds; the firmware enables it only when an embedded model has the km-en token set, read from the model headers by `main/vtts_langs.cmake`): Khmer normalization on the shared C engine `vtts_text_nsp.c`, spelling folds, word segmentation over the front-coded word list, clusters, syllables, onset, rhyme and override tables generated into `vtts_text_km_tables.h` (no blob, about 230 KB of flash on the ESP32). Fixture `runtime/test/text_parity_km.tsv` (14,256 cases) matches exactly, `text_test --fuzz-km` under ASan/UBSan; firmware lang `km`, Khmer bench sentences.
- **Burmese front-end (Python):** token set `my-en` (code 30; 53 Burmese tokens from id 107: 31 initials (r and D reserved) with the voiceless nasals and laterals of ှ, glides y w, 14 vowels, finals N and ?, tones low, high, creaky and checked; vocabulary 160), `text_to_ids(text, "my")` for Burmese with English words: Zawgyi detection and conversion to Unicode (`my/zawgyi.py`, all 83 pairs of Google's Zawgyi test file), canonical mark order, syllables by the spelling (stacks, kinzi, finals with asat), onsets, rhymes and tones after Google's Burmese grammar (Apache-2.0), the reduced vowel; Burmese numbers (creaky ဆယ့် ရာ့ ထောင့်, သောင်း သိန်း သန်း), Burmese digits and ဝ for zero, dates, times, kyat, percent, units, ranges, phone numbers. 62.5% of 8,387 Wiktionary words read exactly, 75.5% with voicing neutralized (`scripts/frontend/eval_my_g2p.py`; eSpeak NG's Burmese is not usable). Eval sets `ood_my` and `mixed_my`; corpus support (`build_wiki_corpus.py --lang my`, `build_mixed.py --lang my`); teacher rows, distill packs, presets, CER with lang `my`.
- **Khmer front-end (Python):** token set `km-en` (code 31; 69 Khmer tokens from id 107: 24 consonants with the glottal stop and the implosives, 30 vowels, 15 finals; vocabulary 176), `text_to_ids(text, "km")` for Khmer with English words: spelling folds (subscript ដ/ត, ឲ, coeng ro), word segmentation over the Khmer words of Google's Khmer lexicon (CC BY 4.0) found in Khmer Wikipedia, orthographic clusters to syllables (finals, subscript pairs that split, bantoc, silent ៍ ៌, silent final ិ ុ), the a/o series, onset and rhyme tables learned from the lexicon and 4,163 overrides (`scripts/frontend/build_km_lexicon.py`); Khmer numbers (ម្ភៃ, ម៉ឺន, សែន, លាន), Khmer digits, dates, times, riel, percent, units, phone numbers, ranges, abbreviations, ៗ, on a normalizer engine shared with Burmese (`frontend/nospace_norm.py`); spaces between Khmer runs read as pauses, ។ ៕ end a sentence. Rules alone: 80.7% of Wikipedia word tokens and 87.3% of syllables as in the lexicon on held-out words (`scripts/frontend/eval_km_g2p.py`). Eval sets `ood_km` and `mixed_km`; corpus support (`build_wiki_corpus.py --lang km`, `build_mixed.py --lang km`); teacher rows, distill packs, presets, CER with lang `km`.
- **Thai front-end (Python):** token set `th-en` (code 9; 55 Thai tokens from id 107: 21 initials with the glottal stop `?`, 21 vowels (nine short/long pairs and the diphthongs ia, uea, ua), 8 finals (k p t m n ng w j), 5 tones; vocabulary 162), `text_to_ids(text, "th")` for Thai with English words: word segmentation over a 16,377-word list made from PyThaiNLP's CC0 word list (`lexicons/th/words.txt`, `scripts/frontend/build_th_lexicon.py`), syllables by a cost-based split over the spelling patterns (preposed vowels, clusters, silent ร, ห and leading consonants, unwritten o/a, ์, ฤ, linking finals ฐ ษ ศ ธ), tones from consonant class, tone mark and live/dead syllables, `lexicons/th/overrides.tsv` (116 respellings), ๆ and ฯ; Thai numbers (เอ็ด, ยี่สิบ, ล้าน), Thai digits, dates, times (14.30 น.), money, percentages, units, phone numbers; spaces between Thai runs read as pauses. 90.4% syllable agreement and 99.4% tone agreement with TLTK's g2p (PyThaiNLP `tltk_g2p`) on 1,193 held-out Wikipedia sentences (`scripts/frontend/eval_th_g2p.py`). Eval sets `ood_th` and `mixed_th`; teacher rows, distill packs, presets, CER with lang `th`.
- **French front-end (Python):** token set `fr-en` (code 11; 36 French tokens from id 107: 11 oral vowels with the open `E` `O`, `eu` `oe` and the schwa `@`, 4 nasal vowels, glides `j w H`, 18 consonants; vocabulary 143), `text_to_ids(text, "fr")` for standard French with English words: silent final letters, -ent of verbs (silent) and of nouns, adjectives and adverbs (`lexicons/fr/ent.txt`, -ment, -ents), -er/-ez/-et, nasal vowels, glides, ill, e muet (final e, the three-consonant rule), mid vowels by syllable position, elision (l' d' qu' jusqu') and liaison (determiners, pronouns, numbers, prenominal adjectives, short prepositions and adverbs, inverted verbs; h aspiré, onze, et block it; bon ami denasalized), hand-written tables `lexicons/fr/` (78 overrides, word lists for final consonants, -ent, -er, -ment verbs); French numbers (soixante-dix, quatre-vingts, vingt et un, une before feminine nouns, six/dix/huit/vingt/neuf finals), ordinals and Roman ordinals (XIXe), dates, times (14 h 30), euros with centimes, percentages, units, phone numbers in pairs, acronyms and abbreviations. 3.06% phoneme error rate (1.51% with mid vowels merged) and 92.9% / 98.0% word agreement against eSpeak NG on held-out Wikipedia sentences (`scripts/frontend/eval_fr_g2p.py`, measuring only). Wikipedia sentence selection for fr (apostrophes, the space before ? !), mixed templates, eval sets `ood_fr` and `mixed_fr`; teacher rows, distill packs, presets, the unreadable filter and CER with lang `fr`.
- **Per-language build switches:** every optional language of the device front-end (zh, ko, ja, hi, th, es, id, pt, fr, de, it, tr, ru, pl, ar, fi, el, ms, tl, sw, nl, sv, no) compiles only with its `VTTS_ENABLE_<L>` (`runtime/include/vtts_langs.h`, all on for host builds and `make test`; `make langs_test` checks each alone and none). The firmware derives them from the token sets of its two models (`main/vtts_langs.cmake`, `VTTS_LANGS=all` for everything) and embeds `lex_zh.bin` / `lex_ja.bin` only with their language, so a vi-en image no longer carries the Japanese blob. Model files without the `token_set` dim are mapped by vocabulary size only to the sets that existed before the dim (v1 .. hi-en); every newer set needs its recorded code.
- **French device front-end (C):** mode `VTTS_LANG_FR` of `vtts_text_to_ids_ex` (token set fr-en, code 11) with the French normalizer (numbers, ordinals and Roman numerals, dates, times, money, percent, units, phone numbers in pairs, abbreviations, inverted verbs), liaison and elision, tagging with elided clitics, silent letters, endings, letter rules, e muet and mid vowels, exactly matching `text_to_ids(text, "fr")` (12,790 fixture cases, 232,760 more in larger random runs, fuzz clean under ASan/UBSan). Tables generated into `vtts_text_fr_tables.h` (no blob); the text workspace does not grow. Compiled only with `VTTS_ENABLE_FR` (default 1 on the host): the firmware enables it when an embedded model is fr-en (about 70 KB of code and tables on the ESP32-P4), accepts `lang fr` and has French `bench` sentences; `vtts_say` runs fr-en models.
- **Russian front-end (Python):** token set `ru-en` (code 16; 47 Russian tokens from id 107: unstressed vowels a i u y @ after reduction, stressed vowels a1 e1 i1 o1 u1 y1, 15 hard/soft consonant pairs, sh zh ts ch shch j; vocabulary 154), `text_to_ids(text, "ru")` for Russian with English words: stress from a 47,809-ending table and a 15,859-word table built from Koziev/NLP_Datasets' CC0 stress dictionary (`scripts/frontend/build_ru_stress.py`; Wikipedia word counts chose the entries and the words whose ё is usually written е), 112 hand-written overrides, unstressed clitics; spelling rules (silent consonants, сч, -тся, -ого), softness and j, akanye/ikanye reduction, assimilative softness, voicing assimilation and final devoicing, в к с joined to the next word; Russian numbers with cheap gender agreement and the genitive after до/от/около, decimals (целых, десятых), dates and years as ordinals in their case, Roman centuries and regnal numbers, times, roubles with kopecks, тыс./млн, percentages, units, ordinals with endings (3-го, 1990-х), compounds (5-этажный), phone numbers, abbreviations and acronyms. 92.9% stress agreement and 4.5% phoneme error rate against eSpeak NG on 2,000 held-out Wikipedia sentences (`scripts/frontend/eval_ru_g2p.py`). Eval sets `ood_ru` and `mixed_ru`, Wikipedia corpus and mixed templates for `ru`; teacher rows, distill packs, presets, CER with lang `ru` (ё counted as е).
- **Polish front-end in C:** `vtts_text_to_ids_ex` mode `VTTS_LANG_PL` (token set `pl-en`, code 17) gives exactly `text_to_ids(text, "pl")`: Latin-script tagging for Polish, the spelling, nasal, voicing and stress rules, and the normalizer's patterns as Python parse trees (`vtts_re.c`), all tables generated into `src/vtts_text_pl_tables.h`, no blob; compiled only with `VTTS_ENABLE_PL` (the firmware enables it for pl-en models). Parity fixture `runtime/test/text_parity_pl.tsv` (11,153 cases) 100%, `text_test --fuzz-pl`, `make pl_test`; about 66 KB on the ESP32-P4.
- **Russian front-end in C:** `vtts_text_to_ids_ex` mode `VTTS_LANG_RU` (token set `ru-en`, code 16) gives exactly `text_to_ids(text, "ru")`: the RLEX blob (`scripts/frontend/build_ru_blob.py`, `include/vtts_rlex.h`, 358 KB) holds the stress tables, the normalizer's and the spelling rules' regular expressions are Python's own parse trees (`runtime/tools/gen_slavic_tables.py`) matched by `src/vtts_re.c`; compiled only with `VTTS_ENABLE_RU` (default 1 on the host; the firmware enables it and embeds `lex_ru.bin` when a ru-en model is built in). Parity fixture `runtime/test/text_parity_ru.tsv` (13,960 cases) 100%, `text_test --fuzz-ru`, `make ru_test`; about 75 KB of code and tables plus the blob on the ESP32-P4.
- **Polish front-end (Python):** token set `pl-en` (code 17; 44 Polish tokens from id 107: vowels a e i o u y and the nasal vowels on/en, the same stressed, 28 consonants with sh zh ch dzh, the soft s' z' c' dz' n', x, w (ł), ts dz; vocabulary 151), `text_to_ids(text, "pl")` for Polish with English words: spelling rules (cz sz rz ż dż dz dź ch, ci si zi ni dzi softness, i before a vowel as j, au eu), nasal vowels by the next consonant (ręka, będzie, dąb; final ę oral), voicing assimilation with progressive devoicing of w and rz and final devoicing, penultimate stress with the -yka/-ika stems of `lexicons/pl/antepenult.txt` and the -liśmy / -byśmy forms, unstressed clitics, w z joined to the next word; Polish numbers with cheap gender agreement and the genitive after od/do/około, decimals (dwa i pięć dziesiątych), dates and years as ordinals (w 2026 roku), Roman centuries, times (o czternastej trzydzieści), złoty with grosze, dollars, euros, tys./mln/mld, percentages, units with noun forms, ranges, phone numbers, abbreviations and acronyms. Code-switching by the Latin-script rules with `lexicons/pl/native.txt`. 99.2% stress agreement and 3.0% phoneme error rate against eSpeak NG on 2,000 held-out Wikipedia sentences (`scripts/frontend/eval_pl_g2p.py`). Eval sets `ood_pl` and `mixed_pl`, Wikipedia corpus and mixed templates for `pl`; teacher rows, distill packs, presets, CER with lang `pl`.
- **Lao front-end (Python):** token set `lo-en` (code 32; 56 Lao tokens from id 107 in the layout of th-en: 21 initials, 21 vowels, 8 finals, 6 tones of Vientiane Lao; vocabulary 163), `text_to_ids(text, "lo")` for Lao with English words: word segmentation over a 12,528-word list from Google's Lao spell-check list (Apache-2.0) and the Lao E-Government Center's Lao-English dictionary (MIT), filtered by use in Lao Wikipedia (`scripts/frontend/build_lo_lexicon.py`), syllables by a cost-based split over the spelling patterns (preposed vowels, ຫ before sonorants, ໜ ໝ ຫຼ, ວ ຼ ຣ ລ clusters, ໌), tones from consonant class, tone mark and live/dead syllables, ໆ; Lao numbers (ຊາວ, ເອັດ, ໝື່ນ, ແສນ, ລ້ານ), Lao digits, dates, times (ໂມງ), kip and other money, percent, units, phone numbers, ຄ.ສ. ພ.ສ. ຯລຯ; spaces between Lao runs read as pauses, a dot after a Lao letter does not end a sentence in mode `lo`. Syllable count agrees with the E-Government dictionary's romanization for 96.1% of 46,350 entries, initials 96.3%, finals 98.9% (`scripts/frontend/eval_lo_g2p.py`). Eval sets `ood_lo` and `mixed_lo`, templates, wiki corpus (lo; `build_wiki_corpus.py --mc4` tops up the 20 h of Lao Wikipedia with mC4 web text), teacher rows, distill packs, presets, CER with lang `lo`.
- **Danish front-end (Python):** token set `da-en` (code 22; 51 Danish tokens from id 107 in the NST SAMPA notation: 15 short and 12 long vowels, the glides j~ w 6~, 18 consonants, stød `?` and the stress marks `"` `%`; vocabulary 158), `text_to_ids(text, "da")` for Danish with English words: the 20,000 most frequent Danish Wikipedia words from the NST pronunciation lexicon for Danish (CC0; `lexicons/da/lexicon.tsv` 16,183 readings the rules miss, `words.txt` 3,817 words they read right; `scripts/frontend/build_da_lexicon.py`), compounds of 2-3 known words with linking s/e, spelling rules for the rest (stress with foreign endings and prefixes, vowel length and quality, soft d, vocalized r v g, r-schwa, stød); Danish numbers (enogtyve, halvtreds, years in hundreds), ordinals, dates, times (kl. 14.30), kroner and øre, percent, units, phone numbers, abbreviations; in mode `da` a dot before a lower-case word or a digit does not end a sentence. 67.2% of word tokens agree with eSpeak NG (coarse IPA, PER 10.2%) on 1,000 Wikipedia sentences (`scripts/frontend/eval_da_g2p.py`). Eval sets `ood_da` and `mixed_da`, templates, wiki corpus (da), teacher rows, distill packs, presets, CER with lang `da`.
- **Danish device front-end (C):** mode `VTTS_LANG_DA` of `vtts_text_to_ids_ex` (token set da-en, code 22) with the Danish tagging of plain Latin words (latin.py rules with the known words and compounds), normalize_da pass by pass (numbers, ordinals, dates, times, kroner and øre, units, phone numbers, abbreviations, acronyms; a dot before a lower-case word or a digit does not end a sentence), the NST readings of the 20,000 frequent words, compounds and the spelling rules with stress and stød, exactly matching `text_to_ids(text, "da")` (11,414 fixture cases with both Danish eval sets and the Danish unit-test strings, 130,509 more in larger runs, fuzz clean under ASan/UBSan). Compiled only with `VTTS_ENABLE_DA` (1 on the host; the firmware sets it only when a model is da-en, `main/vtts_langs.cmake`); da-en models load in every build. `gen_text_tables.py` writes `vtts_text_da_tables.h` (no blob): 20.4 KB of code and 258 KB of tables on the ESP32-P4 (the 20,000 words with their readings front coded in 245 KB); the text workspace does not grow. Month names in Danish dates match lower case or capitalized only (no `re.IGNORECASE`, which also folds the Kelvin sign and the long s). The firmware accepts `lang da` (default for da-en models), `bench` has Danish sentences, and `vtts_say` runs da-en models.
- **Lao device front-end (C):** mode `VTTS_LANG_LO` of `vtts_text_to_ids_ex` (token set lo-en, code 32) with Lao normalization (the Thai passes with Lao tables), word segmentation over the word list, the lowest-cost syllable split and the six Vientiane tones, exactly matching `text_to_ids(text, "lo")` (13,029 fixture cases with both Lao eval sets and the Lao unit-test strings, 140,749 more in larger runs, fuzz clean under ASan/UBSan). Compiled only with `VTTS_ENABLE_LO` (1 on the host; the firmware sets it only when a model is lo-en, `main/vtts_langs.cmake`); lo-en models load in every build. `gen_text_tables.py` writes `vtts_text_lo_tables.h` (no blob): 14.5 KB of code and 56 KB of tables on the ESP32-P4, the 12,528 words front coded in 50 KB; the text workspace does not grow. The firmware accepts `lang lo` (default for lo-en models), `bench` has Lao sentences, and `vtts_say` runs lo-en models.
- **Thai device front-end (C):** mode `VTTS_LANG_TH` of `vtts_text_to_ids_ex` (token set th-en, code 9; vocab 162 maps to it too) with Thai normalization (Thai digits, abbreviations, numbers, dates, times with น., money, percent, units, phone numbers, product codes, pauses between Thai runs), word segmentation over the word list, the lowest-cost syllable split, silent letters, linking finals, leading consonants, respellings and tones, exactly matching `text_to_ids(text, "th")` (12,997 fixture cases with both Thai eval sets and the Thai unit-test strings, 70,000 more in a larger run, fuzz clean). `gen_text_tables.py` writes the tables into `vtts_text_th_tables.h` (no blob): the 16,493 words front coded in 68 KB plus a 4 KB block index, about 80 KB in all; the text workspace does not grow. A dot after a Thai letter no longer ends a sentence in any mode (as in Python). The firmware accepts `lang th` (default for th-en models), `bench` has Thai sentences, and `vtts_say` runs th-en models.
- **German front-end (Python):** token set `de-en` (code 12; 60 German tokens from id 107: 7 short and 8 long vowels and 3 diphthongs, each also stressed, the schwa `@` and vocalized r `6`, 22 consonants with the ich-Laut `C`, ach-Laut `x`, `S`, `N`, `R` and the glottal stop `?`; vocabulary 167), `text_to_ids(text, "de")` for German with English words: a lowest-cost split into prefixes, stems (`lexicons/de/stems.txt`, about 1,300 hand-written stems), suffixes and linking elements, vowel length (h, ß, open syllables, doubled consonants, stem-final consonants), schwa and vocalized r, final devoicing, ich/ach-Laut, -ig, sp/st, glottal stops, stress (stressed and unstressed prefixes, foreign endings, first syllable), `lexicons/de/overrides.tsv` (about 240 words); German numbers (einundzwanzig, years, eins/ein/eine), ordinals with a dot (am 3. Mai -> dritten), dates, times, euro amounts, percentages, units, phone numbers, abbreviations (z. B., usw., Dr.) and a German sentence splitter that keeps them; tagging with `lexicons/de/native.txt` and `lexicons/de/english.txt`. 84.0% word agreement (86.5% in sounds, 3.5% phoneme error rate) with eSpeak NG on held-out Wikipedia sentences (`scripts/frontend/eval_de_g2p.py`, eSpeak used only for measuring). Eval sets `ood_de` and `mixed_de`, Wikipedia corpus and code-switching templates for `de`; teacher rows, distill packs, presets, CER with lang `de`.
- **German device front-end (C):** mode `VTTS_LANG_DE` of `vtts_text_to_ids_ex` (token set de-en, header code 12) mirrors `text_to_ids(text, "de")`: the German sentence split (ordinal and abbreviation dots), Latin-script tagging, `normalize_de` pass by pass, the morph split over the stem list, graphemes, stress and sounds (`runtime/src/vtts_text_de.c`, tables generated into `vtts_text_de_tables.h` by `runtime/tools/gen_text_tables.py`; no blob, no extra workspace). Compiled only with `VTTS_ENABLE_DE` (1 on the host; the firmware sets it only when an embedded model is de-en, about 91 KB). Parity fixture `runtime/test/text_parity_de.tsv` (12,526 cases) exact, a 72,661-case random run exact, `text_test --fuzz-de` under ASan/UBSan. Python fixes found by the port: a decimal part with a second mark (1,234,5) raised in `normalize_de`.
- **Italian front-end (Python):** token set `it-en` (code 13; 35 Italian tokens from id 107: 5 vowels, 7 stressed vowels with open `E`/`O`, glides j/w, 21 consonants with `ts dz ch dj sh ny ly`; geminates written twice; vocabulary 142), `text_to_ids(text, "it")` for Italian with English words: spelling rules (c/g before e/i, ci/gi/sci + vowel, gli, gn, sc, qu, voiced s, z), gemination (doubled letters, long ny ly sh ts dz between vowels), glides and hiatus, stress from accents, suffix rules for antepenultimate stress (-abile, -imo, -ico, -olo, -ere, -ono, -avano …) and stressed -ia (-logia, -eria), open/closed e/o (accents, ie/uo, antepenultimate, suffixes), elision (l'acqua, c'è; sull'iPhone splits off the English word), `lexicons/it/overrides.tsv` (151 respellings) and `native.txt`; Italian numbers (ventuno, ventitré, mille duecento …), ordinals, dates, times, euro with centesimi, percentages, units, phone numbers, product codes, acronyms and abbreviations. Agreement with eSpeak NG (measuring stick only) on 1,200 held-out Wikipedia sentences (`scripts/frontend/eval_latin_g2p.py`): 96.9% of phonemes, 94.6% stress position, 83.4% of words exact. Wikipedia sentence selection for it (apostrophes inside words), code-switching templates, eval sets `ood_it` and `mixed_it`; teacher rows, distill packs, presets, CER with lang `it`.
- **Turkish front-end (Python):** token set `tr-en` (code 15; 39 Turkish tokens from id 107: 8 vowels, the same vowels stressed, a length token `long`, 22 consonants with the palatal `ky gy`; vocabulary 146), `text_to_ids(text, "tr")` for Turkish with English words: Turkish lower-casing (I → ı, İ → i), letters, ğ (long vowel, y between front vowels), â î û, doubled consonants; stress on the last syllable except the hand-written `lexicons/tr/overrides.tsv` (96 entries: place names, loanwords, adverbs; also with case, plural and possessive suffixes), unstressed suffixes after an apostrophe (İstanbul'da), pre-stressing suffixes (gelmiyor, gelmedi, geliyor, şehirdir, amacıyla) and unstressed clitics (mi, de, ki, ile); a suffix after an English word is split off (iPhone'da → iPhone / 'da) and a dot after a number before a lower-case word is an ordinal, not a sentence end (5. sınıf). Turkish numbers (separate words, suffixes after apostrophes: 2026'da, 4'üncü), ordinals, dates, times, lira with kuruş, percentages (%25), units, phone numbers, product codes, acronyms and abbreviations. Agreement with eSpeak NG (measuring stick only) on 1,200 held-out Wikipedia sentences: 98.8% of phonemes (eSpeak's Turkish stress is mostly word-final, so stress agreement, 82.5%, is not a quality measure). Wikipedia sentences for tr, code-switching templates, eval sets `ood_tr` and `mixed_tr`; teacher rows, distill packs, presets, CER with lang `tr`.
- **Italian and Turkish device front-ends (C):** modes `VTTS_LANG_IT` and `VTTS_LANG_TR` of `vtts_text_to_ids_ex` (token sets it-en, code 13, and tr-en, code 15), exactly matching `text_to_ids(text, "it" | "tr")`: tagging with elision and suffix splitting, the normalizers pass by pass, the spelling, stress and vowel rules (11,969 and 11,850 fixture cases; 68,644 and 70,585 more plus 60,000 character-level random strings each in a larger run; fuzz clean under ASan/UBSan). Tables generated into `vtts_text_it_tables.h` / `vtts_text_tr_tables.h` (`runtime/tools/gen_lt_tables_it_tr.py`; no blob, no workspace growth). Each module is compiled only with `VTTS_ENABLE_IT` / `VTTS_ENABLE_TR` (about 51 KB and 44 KB): the firmware enables the languages of its models; `lang it|tr`, `bench` sentences, `make -C runtime it_tr_test`.
- **Malay device front-end (C):** `vtts_text_to_ids_ex` mode `VTTS_LANG_MS` (token set `ms-en`, header code 28) gives exactly `text_to_ids(text, "ms")`: the Indonesian code paths of `vtts_text_lt.c` with generated Malay tables (`vtts_text_ms_tables.h`), Malay dates with month abbreviations, times before day parts, ringgit and sen, Malaysian number marks. Compiled only with `VTTS_ENABLE_MS` (host default 1; the firmware enables it when a model is ms-en), about 9 KB on the ESP32-P4. Parity 13,814 / 13,814 (`text_parity_ms.tsv`), fuzz clean under ASan/UBSan. Python fixes: `normalize_ms` no longer raises on `1,500.300.200` or on month look-alikes matched by `re.IGNORECASE` (`5 ſep`).
- **Tagalog device front-end (C):** `vtts_text_to_ids_ex` mode `VTTS_LANG_TL` (token set `tl-en`, header code 29, vocab 139 maps to it too) gives exactly `text_to_ids(text, "tl")`: its own module `vtts_text_tl.c` with generated tables (`vtts_text_tl_tables.h`): tagging with the hyphenated-English rule, `normalize_tl` pass by pass (linker before nouns, alas/ala clock times with the part of the day, Spanish peso prices, month-first dates, `re.IGNORECASE` look-alikes), the stress table with clitics, prefixes, infixes and suffixes, glottal stops and accent marks. Compiled only with `VTTS_ENABLE_TL` (host default 1; the firmware enables it when a model is tl-en), about 33 KB on the ESP32-P4; no blob, the text workspace does not grow. Parity 11,920 / 11,920 (`text_parity_tl.tsv`), two larger runs of about 223,000 cases each all exact, fuzz clean under ASan/UBSan. Python fixes (`normalize_tl` raised): numbers with both marks (1.234,5; 21,234.531,234.5) and month names matched through `re.IGNORECASE` look-alikes (Set. with a long s, dİs.). The firmware accepts `lang tl` (default for tl-en models) and `bench` has Tagalog sentences.
- **Malay front-end (Python):** token set `ms-en` (code 28; 38 Malay tokens from id 107: the six Indonesian vowels with the schwa `@` and the e taling `e`, five stressed vowels, 27 consonants with `v`, `gh`, `dh`, `th` of Malay spelling; vocabulary 145), `text_to_ids(text, "ms")` for Malaysian Malay with English words. The spelling, e, diphthong and stress rules are the Indonesian code (`id/g2p_id.py`, shared through parameters) with Malay letters, ngg read ng + g, the schwa of ke-/se- before a vowel and a Malay exception table over the Indonesian one (`lexicons/ms/overrides.tsv`, 39 entries); final a is not reduced. Malay numbers (lapan, sejuta, bilion, sifar, perpuluhan with the decimals digit by digit, Malaysian marks 1,250.50), ringgit and sen, peratus, darjah selsius, Malay months and month abbreviations, times (pukul 8.30 pagi), ordinals, phone numbers, Malay abbreviations (Jln., En., Pn., Sdn. Bhd.) and English-style letter names. 88.4% of words and 97.3% of phonemes agree with eSpeak NG on held-out Malay Wikipedia sentences (`scripts/frontend/eval_g2p_reference.py`). Wikipedia corpus support (`build_wiki_corpus.py --lang ms`), code-switching templates, eval sets `ood_ms` and `mixed_ms`; teacher rows, distill packs, presets, the unreadable filter and CER with lang `ms`.
- **Tagalog front-end (Python):** token set `tl-en` (code 29; 32 Tagalog tokens from id 107: five vowels, the same vowels stressed, 22 consonants with the glottal stop `?`, `ng` and the loanword consonants f v z j ch sh; vocabulary 139), `text_to_ids(text, "tl")` for Tagalog (Filipino) with English words (Taglish). Spelling rules (ng, mga read manga, the particle ng read nang, Spanish letters c qu ll ñ j in names), glottal stops between vowels, after a hyphen (mag-aral) and at the end of malumi/maragsa words, penultimate stress by default plus a hand-written table with the Filipino accent marks (`lexicons/tl/stress.tsv`, 186 entries: mabilis akó, malumi batà, maragsa hindî, and Spanish names) that also covers the linker -ng, 't/'y and affixed forms (prefixes, -um-/-in-, suffixes); Spanish final stress for -yon, -dad, -al, -ar, -el, -or; accent marks in the text are read. Native numbers with the linker (dalawampu't isang tao, apat na raan), Spanish-derived clock times (alas tres i medya) and peso prices up to 999 (singkuwenta pesos), ordinals (ika-3), month-first dates, punto decimals, units, percentages, phone numbers, Filipino abbreviations (Gng., Brgy., atbp.); a hyphenated word with an English part (i-share, nag-email) is English. 97.7% of words and 99.3% of phonemes agree with Wiktionary's pronunciations on held-out Tagalog Wikipedia sentences, stress on 70% (`scripts/frontend/eval_g2p_reference.py`). Wikipedia corpus support, code-switching templates, eval sets `ood_tl` and `mixed_tl`; teacher rows, distill packs, presets, the unreadable filter and CER with lang `tl`.
- **Swahili front-end (Python):** token set `sw-en` (code 33; 40 Swahili tokens from id 107: five vowels, the same vowels stressed, 26 consonants with ch sh ny th dh gh kh and the velar nasal `ng` of ng'ombe, the prenasalized stops mb nd nj `ngg`; vocabulary 147), `text_to_ids(text, "sw")` for Swahili with English words: phonemic spelling rules, every vowel a syllable, word-initial syllabic m/n (mtu, nchi), penultimate stress with a small table (`lexicons/sw/stress.tsv`). Swahili numbers in the counting form (kumi na moja, mia moja na moja, elfu, laki, milioni), nukta decimals, shilingi/senti and dola before the number (TSh 5,000, 5,000/=), asilimia, units before the number (kilomita tano), times read as written with saa, robo, nusu and dakika (not converted to Swahili time), day-first dates with tarehe, wa kwanza / ya pili, phone numbers, Swahili abbreviations (n.k., Bw., Dkt.) and English-style letter names. 99.7% of words, 99.9% of phonemes and 99.8% of stressed syllables agree with eSpeak NG on held-out Swahili Wikipedia sentences (`scripts/frontend/eval_g2p_reference.py`). Wikipedia corpus support (ng' kept), code-switching templates, eval sets `ood_sw` and `mixed_sw`; teacher rows, distill packs, presets, the unreadable filter and CER with lang `sw`.
- **Swahili device front-end (C):** mode `VTTS_LANG_SW` of `vtts_text_to_ids_ex` (token set sw-en, code 33; vocab 147 maps to it too) with the Latin-script tagging rules for Swahili (ng' is one word), `normalize_sw` pass by pass (abbreviations, dates with tarehe, times with saa, phone numbers, money before and after the amount, asilimia, units before and after the number, wa kwanza / ya pili, ranges, product codes, counting-form numbers, acronyms), fold, digraphs, syllabic nasals and penultimate stress with the stress table, exactly matching `text_to_ids(text, "sw")` (12,801 fixture cases; 153,906 in a larger run with the full corpora and 60,000 character-level random strings, all exact; fuzz clean under ASan/UBSan). `gen_text_tables.py` writes the tables into `vtts_text_sw_tables.h` (no blob; the English list and Unicode classes are shared with `vtts_text_lt.c`); about 20 KB of code and tables on the ESP32-P4 at `-Os` (25 KB at `-O2`); the text workspace does not grow. Compiled only with `VTTS_ENABLE_SW` (default 1 on the host); the firmware enables it when an embedded model is sw-en, `lang sw` is the default for sw-en models and `bench` has Swahili sentences.
- **Pair data and evaluation tools:** Korean and Japanese code-switching templates and `scripts/data/build_mixed.py --lang zh|ko|ja` (replaces `build_zh_mixed.py`); `scripts/data/pair_train_list.py` joins several synthesis runs into one teacher list (optional audio-path column in `train.csv`, per-source hour caps); out-of-domain and mixed evaluation sets for zh, ko and ja with character-level CER (`--lang zh|ko|ja` in `render_teacher.py` and `eval_dir.py`).
- **Mandarin corpus builder** (`scripts/data/build_zh_corpus.py`): plain Simplified Chinese sentences from Chinese Wikipedia for the planned Chinese + English voice.

### Changed
- **Direction:** vtts now targets bilingual voices (main language + English): Vietnamese, Chinese, Korean and Japanese first, then more pairs by ESP32 market. Single-language models are retired once the Vietnamese + English voices are released. See the [roadmap](docs/design/plans/2026-11-18-roadmap-bilingual.md).
- Docs, website and Hugging Face card list only the bilingual voices; all audio samples are the ESP32-P4's own output from the v0.4.0 models.

### Known issues
- ESP32-S3, model M with two cores (the default): the output is not deterministic and some sentences contain short bursts a few frames long; `cores 1` avoids it at the cost of speed. S on the S3 and both models on the ESP32-P4 are not affected. See [docs/reports/performance.md](docs/reports/performance.md#chip-output-against-the-pc-runtime).
- A very short first sentence followed by a long one ("Hello! I am ...") can cause one playback underrun (a short gap).

### Removed
- The Vietnamese prototype (S-vocos v0.1, M-vocos v0.2, CC BY-NC 4.0) from the voice catalog, website samples and Hugging Face card. The firmware and runtime still read its v1 files for one more release.

## v0.3.2 (2026-11-17)

Same model files; faster start of speech and a faster runtime on both chips.

### Changed
- Firmware: playback starts as soon as the next chunks are sure to be ready, based on each model's measured RTF, and a slower model streams in smaller chunks. ESP32-S3: M starts speaking after 0.40–0.43 s (was 1.2–1.3 s), S after 0.21–0.27 s. ESP32-P4: M after 0.23–0.27 s (was 0.74–0.90 s), S after 0.08–0.09 s.
- Runtime: register-tiled fp32 conv for the token and duration blocks (about 40% faster), lighter int8 epilogue; bit-exact. ESP32-S3 RTF: S 0.28 → 0.26, M 0.51 → 0.49; ESP32-P4: S 0.17 → 0.15, M 0.27 → 0.24.
- `prof` splits the vocoder into input conv, depthwise + LayerNorm, MLP (pw1, GELU + quantization, pw2), head and iSTFT.

## v0.3.1 (2026-11-17)

Same model files as v0.3.0; faster runtime, new board, front-end and documentation updates.

### Added
- **Bilingual Vietnamese + English front-end (Python):** token set v2 (v1 + English ARPAbet phonemes and stress, 107 tokens; v1 ids unchanged), CMU Pronouncing Dictionary lexicon, letter-to-sound rules learned from CMUdict for out-of-vocabulary words, English text normalization, and per-word language tagging (modes `vi`, `en`, `auto`).
- **Synthetic training data:** VoxCPM2 synthesis client and bilingual corpus builder (sentences chosen to cover rare Vietnamese syllables, English and code-switched text). About 98 h of speech per voice for `nam-1` (male) and `nu-10` (female).
- **Teacher:** bilingual training lists (`lang` column, token set v2), FLAC input resampled on load, warm-start from project checkpoints, a frame budget per batch for long utterances.
- **Website and documentation:** language dropdown with one table per language (model size and RTF per chip), shared content in `docs/site.json` synced into the READMEs, self-hosted fonts; English README with a multilingual voice catalog (Vietnamese translation in `README.vi.md`), [website](https://tuanpmt.github.io/vtts/) with on-chip audio samples, Hugging Face model repository with one folder per voice, runtime optimization research for ESP32-S3 and ESP32-P4, documentation index, runtime README, this changelog and contributing guide. All design documents and reports translated to English.
- **Pronunciation data per language:** Vietnamese tables moved from code to `src/vtts/frontend/lexicons/vi/*.tsv`, with a data test and [docs/frontend/pronunciation-rules.md](docs/frontend/pronunciation-rules.md) (layout, precedence, how to change a reading or add a language).
- **Runtime speedups (everything in PSRAM):** exact streaming with per-layer state; fused depthwise conv + LayerNorm + quantization and GELU + quantization; 64-frame MLP blocks; cached iSTFT window and two-core overlap-add. ESP32-P4: S 0.21–0.24 → 0.17, M 0.38–0.40 → 0.27. ESP32-S3: S 0.42–0.47 → 0.28, M 0.86–0.96 → 0.51, so the quality model is practical on the S3 too. Optional `vtts_set_fast_scratch()` for internal SRAM (off in the firmware). A correct fused `ld.ip` kernel for the S3 behind `vtts_s3_kernel`, with a `fusetest` command.
- **EchoEar 2.0** board support (`BOARD=echoear`).

### Changed
- Product codes (upper-case letters + digits such as ESP32, S3, U23, VN123) read their digits one by one: "ESP32-P4" → "e ét pê ba hai pê bốn" / "E S P three two P four" (Python and C).
- Vietnamese letter `s` reads "ét" (was "ét xì"); `smartphone` → "sờ mát phôn"; added `smarthome` → "sờ mát hôm".
- `firmware/esp32p4/` renamed to `firmware/esp32/` (it builds for both chips); `scripts/device/p4_say.py` renamed to `say.py`.

## v0.3.0 (2026-11-16)

Models unchanged from v0.2.0 (S-vocos v0.1, M-vocos v0.2); runtime, firmware and boards.

### Added
- **ESP32-S3 port:** int8 SIMD kernels using `ee.vmulas.s8.accx`, two-core scheduling, and the Waveshare ESP32-S3-Touch-LCD-2.8 board (PCM5101). RTF 0.42–0.47 (S) and 0.85–0.99 (M); needs at least 8 MB of PSRAM.
- **Waveshare ESP32-P4-NANO** board, selected with `BOARD=nano`.
- Per-board default volume and gain, per-core CPU load report after each sentence, a more robust first console command.
- `selftest` also checks the SIMD kernels with both cores running at once.

### Changed
- **Runtime 2.1–2.3× faster on ESP32-P4:** GELU lookup table, multi-frame int8 kernels pipelined with the PIE instruction `esp.vmulas.s8.xacc.ld.ip`, half-size real FFT for the iSTFT, depthwise convolution, LayerNorm, activation quantization and iSTFT split across both cores. RTF 0.20–0.22 (S) and 0.34–0.42 (M); speech starts after 0.3 s (S) and 1.2 s (M). Audio correlation with v0.2.0 is 0.9998.
- Detailed numbers moved to [docs/reports/performance.md](docs/reports/performance.md).

### Fixed
- `M_PI` is defined when strict C99 headers omit it (glibc).

## v0.2.0 (2026-11-15)

### Changed
- **M-vocos v0.2** (1.73M parameters) trained with prosody v2: a frame-level pitch and energy predictor conditions the acoustic model, and an unbiased duration loss fixes the too-fast speaking rate. On 50 held-out sentences the mean duration is 5.80 s per sentence (v0.1: 4.95 s, human reader: 6.08 s) and pitch variation is 2.37 semitones (v0.1: 2.32, human: 2.60). OOD CER 0.012, UTMOS 2.19.
- On-chip audio samples and numbers refreshed.

## v0.1.0 (2026-11-15)

First release: a Vietnamese prototype voice that runs entirely on an ESP32-P4.

### Added
- **Models** (int8 `.vtts`, CC BY-NC 4.0, non-commercial research use): S-vocos v0.1 (0.77M parameters, 1.1 MB) and M-vocos v0.1 (1.73M parameters), distilled from a VITS teacher trained on InfoRe1.
- **Vietnamese front-end** in Python and C with exact parity: spelling-based G2P (65 tokens, 6 tones), normalization of numbers, dates, times and abbreviations.
- **C99 runtime** without `malloc`: fp32 and int8 synthesis, streaming that is bit-exact with whole-utterance synthesis, versioned model file format.
- **Training pipeline:** InfoRe1 preparation and filtering, VITS teacher, three-stage student distillation, int8 export, evaluation tools (CER with PhoWhisper, UTMOS, DNSMOS, whistle index) and black-box baselines.
- **ESP32-P4 firmware** for the Waveshare ESP32-P4-86-Panel: type a sentence on the serial console and the board speaks it; `model`, `vol`, `gain`, `speed`, `expr`, `bench`, `prof`, `selftest` and `dump` commands; ESP32-P4 PIE SIMD int8 kernels and two-core synthesis.
