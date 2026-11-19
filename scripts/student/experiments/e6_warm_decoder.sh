#!/bin/bash
# E6: warm decoder. The student's decoder (vocoder) starts from an existing student of the same
# preset, INIT_FROM= (float checkpoint: OUT/PRESET.student.pt written at the end of a chain or
# experiment, or a joint_*.pt), so the dec stage runs 10k steps instead of 30k; joint 20k.
# INIT_FRONT=1 also starts the front stage from it (same token set only).
# usage: INIT_FROM=old/M-vocos-p-bi.student.pt scripts/student/experiments/e6_warm_decoder.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e6 "$@"
