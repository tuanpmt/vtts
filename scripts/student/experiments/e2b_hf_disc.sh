#!/bin/bash
# E2b: E2a + high-band log-magnitude discriminators (3 resolutions, >= 4 kHz) in dec and joint.
# usage: scripts/student/experiments/e2b_hf_disc.sh TEACHER_G.pt SENTENCES.jsonl OUT [DEVICE]
# Settings and outputs: scripts/student/run_experiment.sh;
# plan: docs/design/plans/2026-11-19-student-quality-experiments.md
exec "$(dirname "$0")/../run_experiment.sh" e2b "$@"
