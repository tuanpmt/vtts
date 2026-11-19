#!/bin/bash
# Student quality experiment (docs/design/plans/2026-11-19-student-quality-experiments.md):
# distillation pack -> front -> dec -> joint in SNAP-step segments, an int8 export after each
# segment, then the final int8 model. Restartable: the pack is reused once READY, every stage
# resumes from its newest checkpoint and existing snapshot exports are skipped.
#
# usage: scripts/student/run_experiment.sh EXP TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
#   EXP: e0 (v0.4.0 recipe) | e1 | e2a | e2b | e3 | e4 | e5 (see the case below)
#   TEACHER_G.pt: generator-only teacher checkpoint ({"g", "config", "step"}), e.g.
#                 artifacts/teacher/nu10_vien_b32_g.pt
#   SENTENCES.jsonl: {"text", "lang"} rows, e.g. data/bilingual/sentences.jsonl (57,883 rows)
# Every setting can be overridden from the environment (PRESET LIMIT FS DS JS SNAP DEC_DISC
# JOINT_DISC HF HF_LO PACK PACK_DEVICE PROSODY_WORKERS EVAL), e.g. FS=50 DS=50 JS=50 SNAP=25 for
# a smoke run; DRY_RUN=1 only prints the resolved settings. EVAL=hf scores each snapshot with the 5-10 kHz metrics (CPU, no ASR); EVAL=full
# also runs ASR + UTMOS (needs a free GPU / time).
# Outputs in OUT: PRESET.q8.vtts (final), snapshots/PRESET-joint_NNNNNNN.q8.vtts (every SNAP
# steps), {front,dec,joint}_*.pt (joint: every SNAP kept), log.jsonl (training), run.log,
# experiment.env, CHAIN_DONE.
set -euo pipefail
cd "$(dirname "$0")/../.."
EXP=$1; G=$2; SENT=$3; OUT=$4; DEV=${5:-cuda}
KNOBS="PRESET LIMIT FS DS JS SNAP DEC_DISC JOINT_DISC HF HF_LO"
# set NAME=VALUE unless NAME is already set (environment first, then the experiment, then the
# defaults); plain bash 3.2 so it also runs on macOS
put() { local kv k; for kv in "$@"; do k=${kv%%=*}; [ -n "${!k:-}" ] || printf -v "$k" '%s' "${kv#*=}"; done; }
case $EXP in
  e0) ;;                                    # v0.4.0 recipe (baseline reproduction)
  e1) put JS=100000 ;;                      # longer joint: snapshots 10k..100k
  e2a) put HF=2 ;;                          # + high-band STFT loss (dec and joint)
  e2b) put HF=2 DEC_DISC=mpd+mrd-hf JOINT_DISC=mpd+mrd-hf ;;  # + high-band discriminators
  e3) put LIMIT=all JS=60000 ;;             # whole corpus as the distillation pack
  e4) put PRESET=L-vocos-p-bi JS=60000 ;;   # L student (ESP32-P4 only)
  e5) put LIMIT=all JS=100000 HF=2 DEC_DISC=mpd+mrd-hf JOINT_DISC=mpd+mrd-hf ;;  # combination: edit after the E1-E4 decision
  *) echo "unknown experiment $EXP" >&2; exit 2 ;;
esac
# v0.4.0 recipe (run_bilingual_chain.sh): 20k sentences, front 10k bs32, dec 30k bs16 with MPD,
# joint 20k bs16 with MPD + MRD
put PRESET=M-vocos-p-bi LIMIT=20000 FS=10000 DS=30000 JS=20000 SNAP=10000 DEC_DISC=mpd \
    JOINT_DISC=mpd+mrd HF=0 HF_LO=4000
if [ -n "${DRY_RUN:-}" ]; then for k in $KNOBS; do echo "$k=${!k}"; done; exit 0; fi

mkdir -p "$OUT/snapshots"
exec > >(tee -a "$OUT/run.log") 2>&1
# one run per output dir: a second caller waits, a finished run is skipped
if command -v flock >/dev/null 2>&1; then exec 9>"$OUT/.lock"; flock 9; fi
if [ -f "$OUT/CHAIN_DONE" ]; then echo "CHAIN DONE $EXP (already)"; exit 0; fi
if command -v uv >/dev/null 2>&1; then PY=(uv run --extra gpu python); else PY=(.venv/bin/python); fi
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-8} MKL_NUM_THREADS=${MKL_NUM_THREADS:-8} NUMBA_NUM_THREADS=${NUMBA_NUM_THREADS:-8}
for k in $KNOBS; do echo "$k=${!k}"; done > "$OUT/experiment.env"
echo "EXP=$EXP TEACHER=$G SENTENCES=$SENT DEVICE=$DEV" >> "$OUT/experiment.env"
echo "== $EXP $(date -u +%FT%TZ): $(tr '\n' ' ' < "$OUT/experiment.env")"

# ---- distillation pack (shared between runs with the same teacher and limit) ----
PACK=${PACK:-$(dirname "$OUT")/pack-$(basename "$G" .pt)-$LIMIT}
mkdir -p "$PACK"
if command -v flock >/dev/null 2>&1; then exec 8>"$PACK.lock"; flock 8; fi
if [ ! -f "$PACK/READY" ]; then
  LIM=(); [ "$LIMIT" = all ] || LIM=(--limit "$LIMIT")
  "${PY[@]}" scripts/student/build_distill_pack.py --ckpt "$G" --sentences "$SENT" ${LIM[@]+"${LIM[@]}"} \
    --out "$PACK/shards" --device "${PACK_DEVICE:-$DEV}"
  "${PY[@]}" scripts/student/convert_shards.py --src "$PACK/shards" --dst "$PACK/mm" --delete-src
  nice -n 10 "${PY[@]}" scripts/student/add_prosody.py --root "$PACK/mm" --workers "${PROSODY_WORKERS:-8}"
  touch "$PACK/READY"
fi
if command -v flock >/dev/null 2>&1; then flock -u 8; fi

# ---- training ----
last() { ls "$OUT"/$1_*.pt 2>/dev/null | tail -1; }
T() { "${PY[@]}" scripts/student/train_student.py --preset "$PRESET" --shards "$PACK/mm" --out "$OUT" --device "$DEV" "$@"; }
export_model() {  # $1 = output .vtts
  "${PY[@]}" scripts/student/export_student.py --front "$(last front)" --dec "$(last dec)" --joint "$(last joint)" --out "$1" --int8
}
T --stage front --max-steps "$FS" --batch-size 32
T --stage dec --max-steps "$DS" --batch-size 16 --init "$(last front)" --disc "$DEC_DISC" --hf-weight "$HF" --hf-lo-hz "$HF_LO"
steps=""; for ((s = SNAP; s < JS; s += SNAP)); do steps="$steps $s"; done; steps="$steps $JS"
for s in $steps; do
  snap=$OUT/snapshots/$PRESET-joint_$(printf %07d "$s").q8.vtts
  [ -f "$snap" ] && continue
  T --stage joint --max-steps "$s" --batch-size 16 --init "$(last dec)" --disc "$JOINT_DISC" \
    --hf-weight "$HF" --hf-lo-hz "$HF_LO" --keep-every "$SNAP"
  export_model "$snap"
  case ${EVAL:-none} in
    hf) "${PY[@]}" scripts/eval/student_quality.py --model "$snap" --out "${snap%.q8.vtts}-eval" --no-asr ;;
    full) "${PY[@]}" scripts/eval/student_quality.py --model "$snap" --out "${snap%.q8.vtts}-eval" ;;
  esac
done
cp "$snap" "$OUT/$PRESET.q8.vtts"
touch "$OUT/CHAIN_DONE"
echo "CHAIN DONE $EXP $PRESET -> $OUT/$PRESET.q8.vtts"
