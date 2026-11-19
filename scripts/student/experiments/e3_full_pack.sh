#!/bin/bash
# E3: distillation pack from every sentence of the corpus (57,883 rows) instead of 20k;
# joint 60k with snapshots every 10k (compare at equal steps with E1).
# usage: scripts/student/experiments/e3_full_pack.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e3 "$@"
