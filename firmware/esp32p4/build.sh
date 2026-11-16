#!/usr/bin/env bash
# Build/flash with ESP-IDF v6.1 (installed by EIM). Copies the int8 models into main/.
# usage: [BOARD=nano] ./build.sh S_MODEL.vtts M_MODEL.vtts [idf.py args...]   (default: build)
#   BOARD=panel (default): Waveshare ESP32-P4-86-Panel, 32 MB flash, build dir build/
#   BOARD=nano:            Waveshare ESP32-P4-NANO, 16 MB flash, build dir build_nano/
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
    *) echo "unknown BOARD=$BOARD (panel | nano)" >&2; exit 2 ;;
esac
[ -f "$CFG" ] || idf.py "${ARGS[@]}" set-target esp32p4
idf.py "${ARGS[@]}" "${@:-build}"
