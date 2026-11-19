#!/bin/bash
# E5: the options that pass the decision rule, combined (placeholder: full pack + HF loss +
# high-band discriminators + joint 100k on M). Edit the e5 line of run_experiment.sh or override
# PRESET= LIMIT= JS= HF= DEC_DISC= JOINT_DISC= from the environment.
# usage: scripts/student/experiments/e5_combined.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e5 "$@"
