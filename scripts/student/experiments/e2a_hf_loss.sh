#!/bin/bash
# E2a: + high-band STFT loss (bins >= 4 kHz, weight 2) in dec and joint; inference unchanged.
# usage: scripts/student/experiments/e2a_hf_loss.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e2a "$@"
