#!/bin/bash
# Bilingual prosody student from scratch: front (with F0/energy targets) -> decoder -> joint + MRD,
# then int8 export. A new teacher has a new latent space, so the decoder is trained too.
# Run from anywhere; paths are relative to the repo root.
# usage: scripts/student/run_bilingual_chain.sh PRESET DEVICE SHARDS OUT [FRONT_STEPS DEC_STEPS JOINT_STEPS]
set -euo pipefail
cd "$(dirname "$0")/../.."
P=$1; DEV=$2; SH=$3; OUT=$4; FS=${5:-10000}; DS=${6:-30000}; JS=${7:-20000}
mkdir -p "$OUT"
last() { ls "$OUT"/$1_*.pt 2>/dev/null | tail -1; }
# each stage resumes from its newest checkpoint, so the chain can be restarted
uv run python scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage front --max-steps "$FS" --batch-size 32 --device "$DEV"
uv run python scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage dec --max-steps "$DS" --batch-size 16 --device "$DEV" --init "$(last front)"
uv run python scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage joint --max-steps "$JS" --batch-size 16 --device "$DEV" --init "$(last dec)" --disc mpd+mrd
uv run python scripts/student/export_student.py --front "$(last front)" --dec "$(last dec)" --joint "$(last joint)" --out "$OUT/$P.q8.vtts" --int8
echo "CHAIN DONE $P"
