#!/usr/bin/env bash
# Build/flash with ESP-IDF v6.1 (installed by EIM). Copies the int8 models into main/ and builds the
# front-end blobs (main/lex_en.bin, main/lex_zh.bin) once.
# usage: [BOARD=<id>] ./build.sh S_MODEL.vtts M_MODEL.vtts [idf.py args...]   (default: build)
#   BOARD is a folder in components/bsp/boards/ (default: esp32-p4-86-panel-eth-2ro); each board builds in build_<id>/
#   with sdkconfig.<id>. Boards: see components/bsp/README.md.
set -euo pipefail
cd "$(dirname "$0")"
BOARD=${BOARD:-esp32-p4-86-panel-eth-2ro}
BDIR=components/bsp/boards/$BOARD
if [ ! -f "$BDIR/board.cmake" ]; then
    echo "unknown BOARD=$BOARD; available: $(ls components/bsp/boards | tr '\n' ' ')" >&2
    exit 2
fi
TARGET=$(sed -n 's/^set(BSP_TARGET \([a-z0-9]*\))$/\1/p' "$BDIR/board.cmake")
cp "$1" main/model_s.vtts
cp "$2" main/model_m.vtts
shift 2
# English lexicon for bilingual models (VLEX, ~1.9 MB): built once from the pinned CMUdict
[ -f main/lex_en.bin ] || (cd ../.. && uv run python scripts/frontend/build_lexicon.py --out firmware/esp32/main/lex_en.bin)
# Mandarin readings for zh-en models (ZLEX, ~116 KB): built once from the zh tables of the Python front-end
[ -f main/lex_zh.bin ] || (cd ../.. && uv run python scripts/frontend/build_zh_blob.py --out firmware/esp32/main/lex_zh.bin)
# Japanese readings and NFKC data for ja-en models (JLEX, ~720 KB): built once from the ja tables
[ -f main/lex_ja.bin ] || (cd ../.. && uv run python scripts/frontend/build_ja_blob.py --out firmware/esp32/main/lex_ja.bin)
ACTIVATE="$HOME/.espressif/tools/activate_idf_v6.1.sh"
while IFS='=' read -r key value; do
    case "$key" in
        PATH) export PATH="$value:$PATH" ;;
        SYSTEM_PATH | "") ;;
        *) export "$key=$value" ;;
    esac
done < <(bash "$ACTIVATE" -e)
CFG=sdkconfig.$BOARD
export VTTS_BOARD=$BOARD
ARGS=(-B "build_$BOARD" -D "SDKCONFIG=$CFG" -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;$BDIR/sdkconfig.defaults"
      -D "VTTS_BOARD=$BOARD")
[ -f "$CFG" ] || idf.py "${ARGS[@]}" set-target "$TARGET"
idf.py "${ARGS[@]}" "${@:-build}"
