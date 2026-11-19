#!/bin/bash
# E4: L-vocos-p-bi (3.48M parameters, vocoder 224 x 8 blocks), ESP32-P4 only, estimated
# RTF 0.38-0.40 (scripts/student/estimate_rtf.py --bench); joint 60k with snapshots every 10k.
# usage: scripts/student/experiments/e4_large_p4.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e4 "$@"
