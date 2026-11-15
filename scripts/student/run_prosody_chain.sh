#!/bin/bash
# Prosody v2 student: front (with F0/energy targets) -> reuse a trained decoder -> joint + MRD.
# Run from anywhere; paths are relative to the repo root.
# usage: scripts/student/run_prosody_chain.sh PRESET DEVICE SHARDS OUT DECODER_INIT.pt [FRONT_STEPS JOINT_STEPS]
set -euo pipefail
cd "$(dirname "$0")/../.."
P=$1; DEV=$2; SH=$3; OUT=$4; DEC=$5; FS=${6:-10000}; JS=${7:-20000}
mkdir -p "$OUT"
last() { ls "$OUT"/$1_*.pt 2>/dev/null | tail -1; }
uv run python scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage front --max-steps "$FS" --batch-size 32 --device "$DEV"
uv run python scripts/student/merge_student.py --front "$(last front)" --decoder "$DEC" --out "$OUT/init_joint.pt"
uv run python scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage joint --max-steps "$JS" --batch-size 16 --device "$DEV" --init "$OUT/init_joint.pt" --disc mpd+mrd
uv run python scripts/student/export_student.py --front "$(last front)" --dec "$OUT/init_joint.pt" --joint "$(last joint)" --out "$OUT/$P.q8.vtts" --int8
echo "CHAIN DONE $P"
