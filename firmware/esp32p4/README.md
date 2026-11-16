# Firmware ESP32-P4 và ESP32-S3

Chạy toàn bộ chuỗi trên chip: văn bản → ID (front-end C) → tổng hợp streaming (runtime C, int8) → loa. Lệnh `bench` in RTF, RMS và bộ nhớ.

Board hỗ trợ:

| Board | Chip | Flash / PSRAM | Loa | `BOARD=` |
|---|---|---|---|---|
| Waveshare ESP32-P4-86-Panel | ESP32-P4 | 32 MB / 32 MB | ES8311 | `panel` (mặc định) |
| Waveshare ESP32-P4-NANO | ESP32-P4 | 16 MB / 32 MB | ES8311 | `nano` |
| Waveshare ESP32-S3-Touch-LCD-2.8 | ESP32-S3R8 | 16 MB / 8 MB (octal) | PCM5101 | `s3` |

```bash
# cần ESP-IDF v6.1; build.sh tự nạp môi trường và chép hai model vào main/
./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor             # 86-Panel
BOARD=nano ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor  # NANO
BOARD=s3 ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor    # S3-Touch-LCD-2.8
```

Mỗi board có thư mục build và file `sdkconfig` riêng. Cấu hình chung nằm trong `sdkconfig.defaults`, phần riêng của từng chip nằm trong `sdkconfig.defaults.esp32p4` và `sdkconfig.defaults.esp32s3`.

Dòng `REPORT` cho mỗi câu: thời lượng audio, thời gian tổng hợp, RTF (dưới 1.0 là nhanh hơn thời gian thực).

`selftest` kiểm tra kernel SIMD với kết quả tính bằng C: một hàng, nhiều hàng, trọng số đọc từ model, và hai lõi chạy kernel cùng lúc. Trên S3, kernel không dùng lệnh gộp nhân-cộng-và-nạp (`ee.vmulas.s8.accx.ld.ip`). Khi cả hai lõi cùng chạy lệnh này, tổng nhận được đôi khi sai, dù chạy một lõi thì luôn đúng. Kernel hiện tại chỉ dùng nạp rồi nhân-cộng, và luôn cho kết quả đúng trên hai lõi.
