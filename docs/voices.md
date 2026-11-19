# Voices

Every vtts model is **bilingual: one main language + English**, with code-switching. One voice reads single-language sentences and mixed sentences such as "Đã kết nối Bluetooth với AirPods", "스마트폰을 Wi-Fi에 연결했어요" or "このWi-Fiはpasswordが必要ですか？"; the front-end picks the language per word. The English front-end runs on the device too (C, parity-tested against Python), so mixed text is handled on the chip.

Each voice comes as a quality model (M) and a lite model (S, about 1.5× faster, with less CPU load and flash). Both run faster than real time on the ESP32-P4 and the ESP32-S3; pick by sound versus headroom, not by chip.

## Catalog

<!-- BEGIN:voices -->
| Voice | Languages | Quality model (M) | Lite model (S) | Status |
|---|---|---|---|---|
| `nam-1` (male) | 🇻🇳 vi + 🇺🇸 en, code-switching | M (1.83M params, 2.6 MB) | S (0.82M params, 1.2 MB) | **Released in v0.4.0 (Apache-2.0)** |
| `nu-10` (female) | 🇻🇳 vi + 🇺🇸 en, code-switching | M (1.83M params, 2.6 MB) | S (0.82M params, 1.2 MB) | **Released in v0.4.0 (Apache-2.0)** |
| `nu-ko` (female) | 🇰🇷 ko + 🇺🇸 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.5.0 (Apache-2.0)** |
| `nu-zh` (female) | 🇨🇳 zh + 🇺🇸 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.5.0 (Apache-2.0)** |
| `nu-ja` (female) | 🇯🇵 ja + 🇺🇸 en, code-switching | M (1.84M params, 2.6 MB) | S (0.83M params, 1.2 MB) | **Released in v0.6.0 (Apache-2.0)** |
| Spanish + English | 🇪🇸 es + 🇺🇸 en, code-switching | M | S | Planned |
| Portuguese (Brazil) + English | 🇧🇷 pt + 🇺🇸 en, code-switching | M | S | Planned |
| Indonesian + English | 🇮🇩 id + 🇺🇸 en, code-switching | M | S | Planned |
| Hindi + English | 🇮🇳 hi + 🇺🇸 en, code-switching | M | S | Planned |
| Thai + English | 🇹🇭 th + 🇺🇸 en, code-switching | M | S | Planned |
| Dutch + English | 🇳🇱 nl + 🇺🇸 en, code-switching | M | S | Planned |
| Swedish + English | 🇸🇪 sv + 🇺🇸 en, code-switching | M | S | Planned |
| Norwegian + English | 🇳🇴 no + 🇺🇸 en, code-switching | M | S | Planned |
<!-- END:voices -->

Model files are attached to [GitHub Releases](https://github.com/tuanpmt/vtts/releases) and mirrored on [Hugging Face](https://huggingface.co/tuanpm/vtts), one folder per voice (`vi-en-nam-1/`, `vi-en-nu-10/`, `ko-en-nu-ko/`, `zh-en-nu-zh/`, `ja-en-nu-ja/`):

| Voice | Files (lite S, quality M) | Release | Notes |
|---|---|---|---|
| `nam-1`, `nu-10` | `vtts-vien-{nam1,nu10}-{s,m}-v0.4.q8.vtts` | v0.4.0 | Text modes `vi`, `en`, `auto` |
| `nu-ko` | `vtts-koen-nuko-{s,m}-v0.5.q8.vtts` | v0.5.0 | Text mode `ko`; no blob beyond the English lexicon |
| `nu-zh` | `vtts-zhen-nuzh-{s,m}-v0.5.q8.vtts` | v0.5.0 | Text mode `zh`; embeds the 116 KB `ZLEX` blob (`main/lex_zh.bin`) |
| `nu-ja` | `vtts-jaen-nuja-{s,m}-v0.6.q8.vtts` | v0.6.0 | Text mode `ja`; embeds the 721 KB `JLEX` blob (`main/lex_ja.bin`) |

`build.sh` builds and embeds the blobs a model needs. In the single-mode pairs (ko, zh, ja) English words and English sentences go through the English front-end; digits are always read in the main language.

## Quality

Three out-of-domain sets of 50 sentences per language pair (main language, English, mixed; device prompts, numbers, names, questions, long sentences), none of them in the training text. CER is the character error rate when an ASR model transcribes the audio: PhoWhisper-large for Vietnamese (tones included), Whisper large-v3 for English and the other languages. UTMOS predicts naturalness. Audio comes from the int8 C runtime, which gives the same output as the chip.

**Vietnamese + English** ([report](reports/bilingual-student-eval.md)):

| Model | Params | Vietnamese CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (vi / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nam-1` M | 1.83M | 0.021 | 0.015 | 0.030 | 2.59 / 3.25 / 2.63 |
| `nam-1` S | 0.82M | 0.024 | 0.009 | 0.036 | 2.38 / 3.05 / 2.45 |
| `nu-10` M | 1.83M | **0.014** | **0.008** | **0.015** | **2.72 / 3.44 / 2.70** |
| `nu-10` S | 0.82M | 0.015 | 0.013 | 0.027 | 2.52 / 3.26 / 2.50 |

Most remaining errors are numbers written differently by the ASR ("9:30" as "9.30") and brand names inside Vietnamese sentences.

**Korean + English** ([report](reports/ko-student-eval.md); Korean CER counts Hangul syllables):

| Model | Params | Korean CER ↓ | English CER ↓ | Mixed CER ↓ (Hangul only) | UTMOS ↑ (ko / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-ko` M | 1.84M | **0.021** | 0.023 | **0.024** | **2.75 / 3.39 / 2.75** |
| `nu-ko` S | 0.83M | 0.045 | 0.023 | 0.055 | 2.68 / 3.18 / 2.65 |
| VoxCPM2 `nu-ko` (reference voice) | — | — | — | 0.016 | — / — / 3.92 |

Whisper writes most English words in Hangul ("Google Drive" → 구글 드라이브), so the plain CER of the mixed Korean set is 0.30–0.37 for every system, the reference voice included; the mixed column counts only the errors on the Korean characters.

**Chinese + English** ([report](reports/zh-student-eval.md); Mandarin CER counts Han characters):

| Model | Params | Mandarin CER ↓ | English CER ↓ | Mixed CER ↓ | UTMOS ↑ (zh / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-zh` M | 1.84M | **0.020** | **0.021** | 0.047 | **3.16 / 3.64 / 3.23** |
| `nu-zh` S | 0.83M | 0.042 | 0.034 | **0.032** | 2.89 / 3.35 / 2.96 |

Whisper sometimes writes an English word of a mixed sentence in Chinese characters (Samsung → 三星), so the mixed CER is an upper bound.

**Japanese + English** ([report](reports/ja-student-eval.md); Japanese CER on readings, both sides converted to kana):

| Model | Params | Japanese CER ↓ (reading) | English CER ↓ | Mixed CER ↓ (kana and kanji only) | UTMOS ↑ (ja / en / mixed) |
|---|---:|---:|---:|---:|---|
| `nu-ja` M | 1.84M | **0.050** | 0.023 | 0.054 | **2.57 / 3.22 / 2.61** |
| `nu-ja` S | 0.83M | 0.053 | **0.019** | **0.049** | 2.30 / 2.76 / 2.28 |
| VoxCPM2 `nu-ja` (reference voice) | — | 0.023 | — | 0.049 | 3.45 / — / 3.43 |

The Japanese references write some numbers in kanji (十五分) and Whisper writes digits, so the orthographic CER (0.097 M, 0.110 S, 0.064 for the reference voice) counts spelling, not speech; the reading CER compares kana readings and is counted in kana. On the mixed set Whisper writes most English words in katakana (password → パスワード), so the plain CER is 0.20–0.24 for every system. The main remaining error is a weak word-initial *r* (リビング heard as イビング).

## Speed

<!-- BEGIN:hardware -->
| Board | Chip | Lite model RTF | Quality model RTF |
|---|---|---|---|
| Waveshare ESP32-P4-86-Panel-ETH-2RO, ESP32-P4-NANO | ESP32-P4, 360 MHz, PIE SIMD | 0.17–0.18 | 0.26 |
| EchoEar 2.0, Waveshare ESP32-S3-Touch-LCD-2.8 | ESP32-S3, 240 MHz, 8 MB PSRAM | 0.29–0.30 | 0.49–0.51 |

Both models run on both chips. RTF below 1 means faster than real time.
<!-- END:hardware -->

Both chips use two cores and int8 SIMD kernels; all released pairs run at the same speed within about 0.02 RTF. Audio generated on the ESP32-P4 matches the C runtime on a PC. The ESP32-S3 needs at least 8 MB of PSRAM. Details, speech start, CPU load and memory: [reports/performance.md](reports/performance.md).

## Listen (generated on an ESP32-P4)

Audio is produced on the chip with the firmware's `dump` command (`lang auto` for vi-en, `lang ko`, `lang zh`, `lang ja` for the other pairs), sent to a PC over serial and only compressed to MP3; every clip was checked with ASR before publishing. The same clips are on the [website](https://tuanpmt.github.io/vtts/).

<!-- BEGIN:samples -->
🇻🇳 🇺🇸 **Việt–English**

| Sentence | nam-1 Quality | nam-1 Lite | nu-10 Quality | nu-10 Lite |
|---|---|---|---|---|
| Xin chào, tôi là giọng đọc tiếng Việt và tiếng Anh chạy hoàn toàn trên chip ESP32. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-intro.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-intro.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-intro.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-intro.mp3) |
| Đã kết nối Bluetooth với AirPods, bạn có thể mở Spotify hoặc YouTube Music. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-bluetooth.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-bluetooth.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-bluetooth.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-bluetooth.mp3) |
| Cuộc họp trên Google Meet sẽ bắt đầu lúc 9 giờ, nhớ chuẩn bị file PowerPoint nhé. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-meeting.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-meeting.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-meeting.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-meeting.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on an ESP32 microcontroller. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-en-intro.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-en-intro.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-en-intro.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-en-intro.mp3) |
| Your package will arrive on Tuesday, November 18, between 2 and 4 p.m. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-en-package.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-en-package.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-en-package.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-en-package.mp3) |
| Mưa kéo dài hơn hai giờ khiến nhiều đường ở Long Thành, Nhơn Trạch ngập gần nửa mét, xe chết máy, người dân phải dắt bộ, sáng 15/11. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-news.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-news.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-news.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-news.mp3) |
| Pin còn 15%, nhiệt độ phòng là 28°C. Báo thức đã được đặt lúc 6 giờ 30 sáng mai. | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-numbers.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-numbers.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-numbers.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-numbers.mp3) |
| Bạn có muốn bật đèn phòng khách không? | [▶ nam-1 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-m-question.mp3) | [▶ nam-1 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nam1-s-question.mp3) | [▶ nu-10 Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-m-question.mp3) | [▶ nu-10 Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nu10-s-question.mp3) |

🇰🇷 🇺🇸 **한국어–English**

| Sentence | nu-ko Quality | nu-ko Lite |
|---|---|---|
| 안녕하세요, 저는 ESP32 칩에서 완전히 실행되는 한국어와 영어 음성입니다. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-intro.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-intro.mp3) |
| 오늘 오후 3시에 Zoom 회의가 있어요. PowerPoint 파일을 미리 보내 주세요. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-zoom.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-zoom.mp3) |
| 스마트폰을 Wi-Fi에 연결했어요. 이제 Netflix를 볼 수 있어요. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-wifi.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-wifi.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on an ESP32 microcontroller. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-en-intro.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-en-package.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-en-package.mp3) |
| 서울은 오늘 오후부터 비가 내리고, 내일 아침 기온은 영하 3도까지 떨어지겠습니다. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-news.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-news.mp3) |
| 배터리가 15% 남았고, 실내 온도는 28도입니다. 알람은 내일 아침 6시 30분에 맞춰져 있어요. | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-numbers.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-numbers.mp3) |
| 거실 불을 켜 드릴까요? | [▶ nu-ko Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-m-question.mp3) | [▶ nu-ko Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuko-s-question.mp3) |

🇨🇳 🇺🇸 **中文–English**

| Sentence | nu-zh Quality | nu-zh Lite |
|---|---|---|
| 你好，我是完全运行在ESP32芯片上的中文和英文语音。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-intro.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-intro.mp3) |
| 已经通过Bluetooth连接到AirPods，你可以打开Spotify或者YouTube Music。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-bluetooth.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-bluetooth.mp3) |
| 下午三点有一个Zoom会议，请提前把PowerPoint文件发给我。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-meeting.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-meeting.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on a tiny microcontroller. | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-en-intro.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-en-package.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-en-package.mp3) |
| 北京今天下午有小雨，明天早上最低气温零下三度，出门请注意保暖。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-news.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-news.mp3) |
| 电池还剩15%，室内温度是28度。闹钟已经设在明天早上6点30分。 | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-numbers.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-numbers.mp3) |
| 要帮你打开客厅的灯吗？ | [▶ nu-zh Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-m-question.mp3) | [▶ nu-zh Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuzh-s-question.mp3) |

🇯🇵 🇺🇸 **日本語–English**

| Sentence | nu-ja Quality | nu-ja Lite |
|---|---|---|
| こんにちは。私はESP32チップの上だけで動く、日本語と英語の音声です。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-intro.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-intro.mp3) |
| 今日の午後3時からZoomの会議があります。PowerPointのファイルを先に送ってください。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-zoom.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-zoom.mp3) |
| スマートフォンをWi-Fiに接続しました。これでNetflixが見られます。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-wifi.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-wifi.mp3) |
| Hello! I am a text-to-speech voice that runs entirely on an ESP32 microcontroller. | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-en-intro.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-en-intro.mp3) |
| Your package has arrived at the front door. Would you like me to turn on the porch light? | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-en-package.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-en-package.mp3) |
| 東京は今日の午後から雨が降り、明日の朝の気温は2度まで下がる見込みです。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-news.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-news.mp3) |
| バッテリーの残りは15%で、室温は28度です。アラームは明日の朝6時30分にセットされています。 | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-numbers.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-numbers.mp3) |
| 部屋の電気をつけましょうか？ | [▶ nu-ja Quality](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-m-question.mp3) | [▶ nu-ja Lite](https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/audio/p4-nuja-s-question.mp3) |
<!-- END:samples -->
