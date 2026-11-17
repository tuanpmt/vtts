#!/usr/bin/env bash
# Build/flash with ESP-IDF v6.1 (installed by EIM). Copies the int8 models into main/.
# usage: [BOARD=nano] ./build.sh S_MODEL.vtts M_MODEL.vtts [idf.py args...]   (default: build)
#   BOARD=panel (default): Waveshare ESP32-P4-86-Panel, 32 MB flash, build dir build/
#   BOARD=nano:            Waveshare ESP32-P4-NANO, 16 MB flash, build dir build_nano/
#   BOARD=s3:              Waveshare ESP32-S3-Touch-LCD-2.8, 16 MB flash, build dir build_s3/
#   BOARD=echoear:         EchoEar 2.0 (ESP32-S3, 16 MB flash, 8 MB PSRAM), build dir build_echoear/
set -euo pipefail
cd "$(dirname "$0")"
cp "$1" main/model_s.vtts
cp "$2" main/model_m.vtts
shift 2
ACTIVATE="$HOME/.espressif/tools/activate_idf_v6.1.sh"
while IFS='=' read -r key value; do
    case "$key" in
        PATH) export PATH="$value:$PATH" ;;
        SYSTEM_PATH | "") ;;
        *) export "$key=$value" ;;
    esac
done < <(bash "$ACTIVATE" -e)
case "${BOARD:-panel}" in
    panel) CFG=sdkconfig; ARGS=(-B build) ;;
    nano) CFG=sdkconfig.nano
          ARGS=(-B build_nano -D SDKCONFIG=sdkconfig.nano -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.nano") ;;
    s3) CFG=sdkconfig.s3; TARGET=esp32s3
        ARGS=(-B build_s3 -D SDKCONFIG=sdkconfig.s3) ;;
    echoear) CFG=sdkconfig.echoear; TARGET=esp32s3
        ARGS=(-B build_echoear -D SDKCONFIG=sdkconfig.echoear -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.echoear") ;;
    *) echo "unknown BOARD=$BOARD (panel | nano | s3 | echoear)" >&2; exit 2 ;;
esac
[ -f "$CFG" ] || idf.py "${ARGS[@]}" set-target "${TARGET:-esp32p4}"
idf.py "${ARGS[@]}" "${@:-build}"
