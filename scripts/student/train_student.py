"""Train a student stage.

Usage: uv run python scripts/student/train_student.py --preset S-vocos --shards data/distill/shards \
   --out artifacts/student/S-vocos --stage front --max-steps 30000 [--init FILE]
   [--disc mpd|mpd+mrd|mpd+mrd-hf] [--hf-weight W --hf-lo-hz 4000] [--keep-every N]
   [--fast] [--prefetch 2] [--amp auto|off|fp16|bf16] [--compile] [--init-decoder STUDENT.pt]
Speed flags (opt-in, see vtts.student.train.train): --fast (fused AdamW, no per-step host
sync, cuDNN autotuning), --prefetch N (background batch building), --compile (torch.compile).
"""

import argparse
from pathlib import Path

from vtts.student.config import PRESETS
from vtts.student.train import AMP_MODES, DISCS, train


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=sorted(PRESETS), required=True)
    ap.add_argument("--shards", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stage", choices=["front", "dec", "joint"], required=True)
    ap.add_argument("--max-steps", type=int, required=True)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--init", type=Path, default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--disc", choices=DISCS, default="mpd")
    ap.add_argument("--hf-weight", type=float, default=0.0,
                    help="GAN stages: weight of the STFT loss above --hf-lo-hz (0 = off)")
    ap.add_argument("--hf-lo-hz", type=float, default=4000.0)
    ap.add_argument("--ckpt-every", type=int, default=2000)
    ap.add_argument("--keep-every", type=int, default=0,
                    help="keep checkpoints at multiples of this step (0: only the newest 3)")
    ap.add_argument("--amp", choices=AMP_MODES, default="auto",
                    help="auto: fp16 + GradScaler on CUDA, fp32 elsewhere (the original recipe)")
    ap.add_argument("--fast", action="store_true", help="sync-free step with fused AdamW")
    ap.add_argument("--prefetch", type=int, default=0, help="batches built ahead in a thread")
    ap.add_argument("--compile", action="store_true", help="torch.compile decoder + discriminators")
    ap.add_argument("--init-decoder", type=Path, default=None,
                    help="fresh run: take the decoder weights from this student checkpoint")
    a = ap.parse_args()
    train(PRESETS[a.preset], a.shards, a.out, a.stage, a.max_steps, a.batch_size, a.lr,
          ckpt_every=a.ckpt_every, device=a.device, init=a.init, disc=a.disc,
          hf_weight=a.hf_weight, hf_lo_hz=a.hf_lo_hz, keep_every=a.keep_every, amp=a.amp,
          fast=a.fast, prefetch=a.prefetch, compile=a.compile, init_decoder=a.init_decoder)


if __name__ == "__main__":
    main()
