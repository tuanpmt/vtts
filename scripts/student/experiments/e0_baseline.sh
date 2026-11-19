#!/bin/bash
# E0: v0.4.0 recipe (M-vocos-p-bi, 20k sentences, joint 20k), the reference run.
# usage: scripts/student/experiments/e0_baseline.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e0 "$@"
