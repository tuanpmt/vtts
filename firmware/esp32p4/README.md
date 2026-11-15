# Firmware benchmark ESP32-P4

Chạy toàn bộ chuỗi trên chip: văn bản → ID (front-end C) → tổng hợp streaming (runtime C, int8) và in RTF, RMS, bộ nhớ.

```bash
. ~/esp/esp-idf/export.sh
cp <model int8>.vtts main/model.vtts
idf.py set-target esp32p4 build
idf.py -p /dev/ttyUSB0 flash monitor   # khi đã có board
```

Dòng `REPORT` cho mỗi câu: thời lượng audio, thời gian tổng hợp, RTF (dưới 1.0 là nhanh hơn thời gian thực).
