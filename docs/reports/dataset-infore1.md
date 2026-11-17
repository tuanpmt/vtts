# InfoRe1 dataset report

Dataset used for the Vietnamese prototype voice.

## Summary

| Step | Utterances | Hours |
|---|---:|---:|
| Source (`doof-ferb/infore1_25hours`) | 14,935 | 24.54 |
| After filtering | 13,780 | ~22.7 |
| Train | 13,455 | 22.20 |
| Validation | 275 | 0.43 |
| Held-out (evaluation, 3–10 s per utterance) | 50 | 0.08 |

Audio preparation: convert to 22,050 Hz mono, trim leading and trailing silence (−40 dB threshold, 50 ms padding), normalize RMS to −23 dBFS with peaks at most −1 dBFS. No utterance had broken audio or a missing transcript.

## Filtering

Scoring: ASR `vinai/PhoWhisper-small` (6 times faster than the large model and good enough for filtering) and DNSMOS OVRL per utterance.

| Reason for removal | Utterances | Threshold |
|---|---:|---|
| Low DNSMOS | 623 | OVRL < 2.42 (5th percentile) |
| Contains a word that must be spelled letter by letter | 357 | a word that is not a Vietnamese syllable and not in the loanword table |
| Transcript disagrees with ASR | 174 | CER > 0.10 |
| Too short | 1 | < 1 s |

**The DNSMOS threshold was lowered from 3.0 (as planned) to 2.42.** The median DNSMOS of all of InfoRe1 is only 2.88, so a 3.0 threshold would have removed about 60% of the data. The new threshold removes only the worst 5%.

**Words that must be spelled out**: lines containing standalone words such as `hlv` or `usd`, or foreign proper names written as one word, are removed, because the spelled-out label ("hát e lờ vê") does not match what the speaker actually said ("huấn luyện viên").

## Utterances removed by CER (10 examples)

Most are **false rejections**: the ASR writes loanwords in English spelling while the transcript writes them as they are read in Vietnamese. A few are real errors: truncated audio or a repeated transcript.

| CER | ID | Transcript | ASR output | Verdict |
|---:|---|---|---|---|
| 0.54 | infore_13364 | hiện tại rô nan đô và men đét chưa đưa ra bình luận… | hiện tại ronaldo và mandel chưa đưa ra bình luận… | false rejection |
| 0.52 | infore_11723 | nên mua ghế mát xa loại nào… | nên mua ghế massage loại nào… | false rejection |
| 0.51 | infore_08252 | làm sạch đồng hồ mạ vàng… (repeated twice) | làm sạch đồng hồ mạ vàng… (once) | repeated transcript, correct rejection |
| 0.47 | infore_13727 | …có thể ghé đến nha khoa kim để được… | …có thể ghé đến. | truncated audio, correct rejection |
| 0.46 | infore_12176 | …người khác mát xa lưng… | …người khác massage lưng… | false rejection |
| 0.44 | infore_14021 | …phải ký cam mổ mở thì mới phẫu thuật… | …phải ký cam mổ. | truncated audio, correct rejection |
| 0.42 | infore_02939 | trước khi mát xa mặt… các cơ | trước khi massage mặt… các cô | mostly false |
| 0.41 | infore_04271 | …bao cao su đôn dên | …bao cao su donetsk | false rejection |
| 0.41 | infore_12616 | …vi ta min e và vi ta min c… | …vitamin e và vitamin c… | false rejection |
| 0.38 | infore_05505 | sửa ti vi sam sung… | sửa tivi samsung… | false rejection |

Since only 1.2% of the data is lost, no immediate fix is needed. A later improvement: add common loanwords (massage, vitamin, samsung…) to the loanword table so that both the transcript and the ASR map to the same reading.

## Tone distribution (train set, syllable counts)

| ngang (level) | huyền (falling) | sắc (rising) | hỏi (dipping) | ngã (broken) | nặng (heavy) |
|---:|---:|---:|---:|---:|---:|
| 70,946 | 51,431 | 62,666 | 28,002 | 14,287 | 47,446 |

The ngã tone is the rarest (5.5%) but still has more than 14 thousand samples, enough to learn.
