#!/bin/bash
# Train one student preset end to end on a single device, exporting + evaluating after each GAN stage.
# usage: scripts/student/run_student_chain.sh PRESET DEVICE [FRONT_STEPS DEC_STEPS JOINT_STEPS]
set -euo pipefail
cd "$(dirname "$0")/../.."
P=$1; DEV=$2; FS=${3:-10000}; DS=${4:-30000}; JS=${5:-10000}
OUT=artifacts/student/$P
SH=${SHARDS:-data/distill/mm}
mkdir -p $OUT
last() { ls $OUT/$1_*.pt 2>/dev/null | tail -1; }
evaluate() {  # $1 = label; set NO_EVAL=1 to only export (evaluate elsewhere)
  local tag=$1 m=$OUT/$P-$1.q8.vtts
  uv run python scripts/student/export_student.py --front "$(last front)" --dec "$(last dec)" \
     ${JOINT:+--joint "$(last joint)"} --out $m --int8
  [ -n "${NO_EVAL:-}" ] && return 0
  uv run python scripts/student/render_student_c.py --model $m --set eval/sets/ood.jsonl --out $OUT/render-$tag-ood
  uv run python scripts/eval/eval_dir.py --system $P-$tag-c-int8 --set eval/sets/ood.jsonl \
     --audio $OUT/render-$tag-ood --out $OUT/eval-$tag-ood.json 2>&1 | grep -E "CER|group"
}
uv run python scripts/student/train_student.py --preset $P --shards $SH --out $OUT --stage front --max-steps $FS --batch-size 32 --device $DEV
uv run python scripts/student/train_student.py --preset $P --shards $SH --out $OUT --stage dec --max-steps $DS --batch-size 16 --device $DEV --init "$(last front)"
evaluate dec
JOINT=1 uv run python scripts/student/train_student.py --preset $P --shards $SH --out $OUT --stage joint --max-steps $JS --batch-size 16 --device $DEV --init "$(last dec)"
JOINT=1 evaluate joint
echo "CHAIN DONE $P"
