#!/bin/bash
# E1: joint stage 100k steps (M-vocos-p-bi, 20k sentences), int8 snapshots every 10k
# (the 20k snapshot is the v0.4.0 recipe; 60k and 100k are the two asked lengths).
# usage: scripts/student/experiments/e1_long_joint.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e1 "$@"
