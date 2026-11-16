# Firmware benchmark ESP32-P4

Chạy toàn bộ chuỗi trên chip: văn bản → ID (front-end C) → tổng hợp streaming (runtime C, int8) và in RTF, RMS, bộ nhớ.

Board hỗ trợ: Waveshare ESP32-P4-86-Panel (flash 32 MB) và ESP32-P4-NANO (flash 16 MB). Hai board nối codec ES8311 giống nhau, khác nhau ở dung lượng flash.

```bash
# cần ESP-IDF v6.1; build.sh tự nạp môi trường và chép hai model vào main/
./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor             # 86-Panel
BOARD=nano ./build.sh S_MODEL.vtts M_MODEL.vtts -p PORT flash monitor  # NANO
```

Dòng `REPORT` cho mỗi câu: thời lượng audio, thời gian tổng hợp, RTF (dưới 1.0 là nhanh hơn thời gian thực).
