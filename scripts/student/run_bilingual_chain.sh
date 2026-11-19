#!/bin/bash
# Bilingual prosody student from scratch: front (with F0/energy targets) -> decoder -> joint + MRD,
# then int8 export. A new teacher has a new latent space, so the decoder is trained too.
# Run from anywhere; paths are relative to the repo root.
# usage: scripts/student/run_bilingual_chain.sh PRESET DEVICE SHARDS OUT [FRONT_STEPS DEC_STEPS JOINT_STEPS]
# env TRAIN_ARGS: extra train_student.py flags for every stage, e.g. TRAIN_ARGS="--fast --prefetch 2";
# DEC_TRAIN_ARGS: only for the dec stage, e.g. DEC_TRAIN_ARGS=--compile (RTX 5090: dec 105 -> 74 ms/step)
set -euo pipefail
cd "$(dirname "$0")/../.."
P=$1; DEV=$2; SH=$3; OUT=$4; FS=${5:-10000}; DS=${6:-30000}; JS=${7:-20000}
mkdir -p "$OUT"
# one chain per output dir: a second caller waits for the first, and a finished chain is skipped
if command -v flock >/dev/null 2>&1; then exec 9>"$OUT/.lock"; flock 9; fi
if [ -f "$OUT/CHAIN_DONE" ]; then echo "CHAIN DONE $P (already)"; exit 0; fi
last() { ls "$OUT"/$1_*.pt 2>/dev/null | tail -1; }
# uv where it is installed, else the repo's virtualenv (rented GPU boxes have only .venv)
if command -v uv >/dev/null 2>&1; then PY=(uv run python); else PY=(.venv/bin/python); fi
# each stage resumes from its newest checkpoint, so the chain can be restarted
"${PY[@]}" scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage front ${TRAIN_ARGS:-} --max-steps "$FS" --batch-size 32 --device "$DEV"
"${PY[@]}" scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage dec ${TRAIN_ARGS:-} ${DEC_TRAIN_ARGS:-} --max-steps "$DS" --batch-size 16 --device "$DEV" --init "$(last front)"
"${PY[@]}" scripts/student/train_student.py --preset "$P" --shards "$SH" --out "$OUT" --stage joint ${TRAIN_ARGS:-} --max-steps "$JS" --batch-size 16 --device "$DEV" --init "$(last dec)" --disc mpd+mrd
"${PY[@]}" scripts/student/export_student.py --front "$(last front)" --dec "$(last dec)" --joint "$(last joint)" --out "$OUT/$P.q8.vtts" --int8 \
  --save-pt "$OUT/$P.student.pt"
touch "$OUT/CHAIN_DONE"
echo "CHAIN DONE $P"
