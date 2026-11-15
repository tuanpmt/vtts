#!/usr/bin/env bash
# Build/flash with ESP-IDF v6.1 (installed by EIM). Copies the int8 models into main/.
# usage: ./build.sh S_MODEL.vtts M_MODEL.vtts [idf.py args...]   (default: build)
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
[ -f sdkconfig ] || idf.py set-target esp32p4
idf.py "${@:-build}"
