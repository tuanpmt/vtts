# Hiệu năng trên chip

Số đo chi tiết của runtime int8 trên ESP32-P4 và ESP32-S3. README chỉ giữ bảng tóm tắt.

## ESP32-P4

Chip rev 1.3, 360 MHz, PSRAM 32 MB. Đo trên Waveshare ESP32-P4-NANO; ESP32-P4-86-Panel dùng cùng chip và cùng firmware, cho cùng số đo.

| Model | RTF (2 lõi, PIE SIMD) | Bắt đầu phát | Flash | RAM làm việc |
|---|---:|---:|---:|---:|
| S-vocos | 0.20–0.24 | 0.3–0.5 s | 1.1 MB | ~0.4 MB (streaming) |
| M-vocos v0.2 | 0.34–0.42 | 1.2–1.3 s | 2.6 MB | ~0.6 MB (streaming) |

Tải CPU khi vừa tổng hợp vừa phát loa (đoạn bản tin thời tiết 5 câu, trung bình suốt thời gian phát; core0 gồm cả task console và task đẩy audio ra loa):

| Model | Core 0 | Core 1 | Số lần ngắt quãng |
|---|---:|---:|---:|
| S-vocos | 21% | 16% | 0 |
| M-vocos v0.2 | 35% | 28% | 0 |

### Tối ưu runtime (v0.3.0)

Model và file `.vtts` giữ nguyên, audio gần như giống hệt bản cũ (tương quan 0.9998).

| Model | RTF v0.2.0 | RTF v0.3.0 | Nhanh hơn | Bắt đầu phát |
|---|---:|---:|---:|---:|
| S-vocos | 0.41–0.45 | 0.20–0.22 | ~2,1 lần | 0.6–0.9 s → 0.3 s |
| M-vocos v0.2 | 0.79–0.94 | 0.34–0.42 | ~2,3 lần | 2.4 s → 1.2 s |

Những thay đổi chính:
- GELU dùng bảng tra thay cho `tanhf`.
- Kernel int8 tính nhiều frame trong một lần gọi, vòng lặp pipeline bằng lệnh `esp.vmulas.s8.xacc.ld.ip` của PIE.
- iSTFT dùng FFT thực nửa kích thước.
- Depthwise conv, LayerNorm, lượng tử hoá activation và iSTFT chia cho cả 2 lõi.

## ESP32-S3

Waveshare ESP32-S3-Touch-LCD-2.8: ESP32-S3R8, 240 MHz, PSRAM octal 8 MB, flash 16 MB. Firmware và hai model giống bản P4. Kernel int8 dùng lệnh SIMD 128-bit `ee.vmulas.s8.accx`.

| Model | RTF (2 lõi, SIMD) | Bắt đầu phát | CPU core0 / core1 khi phát | Số lần ngắt quãng |
|---|---:|---:|---:|---:|
| S-vocos | 0.42–0.47 | ~0.8 s | 40% / 29% | 0 |
| M-vocos v0.2 | 0.85–0.99 | ~2.4 s | 75% / 62% | 0 |

- Audio từ S3 khớp với runtime chạy trên máy tính: tương quan 1.000000 với S, 0.999992 với M.
- Model M vẫn nhanh hơn thời gian thực nhưng sát giới hạn. Trên S3 nên dùng S nếu cần phản hồi nhanh hoặc phải chạy thêm việc khác.
- Cần PSRAM ít nhất 8 MB: hai model được chép vào PSRAM, vùng làm việc khoảng 1.9 MB. Board PSRAM 2 MB không đủ.
- Không dùng lệnh gộp `ee.vmulas.s8.accx.ld.ip`. Khi cả hai lõi cùng chạy lệnh này, tổng nhận được đôi khi sai; chạy một lõi thì luôn đúng. Kernel hiện tại dùng nạp rồi nhân-cộng, cho kết quả đúng trên hai lõi. `selftest` của firmware có bài kiểm tra hai lõi chạy kernel cùng lúc.

## Cách đo

- `bench`: tổng hợp 4 câu cố định, không phát loa, in RTF cho từng câu.
- `prof`: thời gian theo từng tầng của model.
- Khi phát loa, firmware in `first chunk`, `playback started`, số lần ngắt quãng và tải CPU từng lõi sau mỗi câu.
- RTF trên dòng `SAID` (khi phát loa) gồm cả thời gian chờ bộ đệm phát, nên cao hơn RTF thật. RTF thật lấy từ `bench` hoặc `dump`.
