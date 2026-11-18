"""Train the VITS teacher.

Usage (GPU box):
  uv run python scripts/teacher/train_teacher.py --data data/infore1/final --wavs data/infore1/prepared/wavs \
     --out artifacts/teacher/run1 --warmstart artifacts/warmstart/epoch=4769-step=919580.ckpt \
     --max-steps 100000 --ckpt-every 5000

Several GPUs on one machine (DistributedDataParallel; --batch-size is per GPU):
  uv run torchrun --nproc_per_node 4 scripts/teacher/train_teacher.py ... --batch-size 16 --bf16
"""

import argparse
import os
from pathlib import Path

import torch
import torch.distributed as dist

from vtts.teacher.config import TeacherConfig
from vtts.teacher.train import train


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="dir with train.csv")
    ap.add_argument("--wavs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--max-batch-frames", type=int, default=None,
                    help="cap batch size x longest utterance (spectrogram frames) to bound GPU memory")
    ap.add_argument("--no-cache", action="store_true", help="compute spectrograms on the fly")
    ap.add_argument("--warmstart", type=Path, default=None)
    ap.add_argument("--max-steps", type=int, default=100_000)
    ap.add_argument("--ckpt-every", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--bf16", action="store_true", help="bf16 autocast (Ampere or newer) instead of fp16")
    ap.add_argument("--lr", type=float, default=None, help="learning rate (default from the config)")
    args = ap.parse_args()
    cfg = TeacherConfig(batch_size=args.batch_size)
    device = args.device
    if int(os.environ.get("WORLD_SIZE", "1")) > 1:  # launched by torchrun
        local = int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(local)
        dist.init_process_group("nccl")
        device = f"cuda:{local}"
        args.num_workers = max(1, args.num_workers // int(os.environ["WORLD_SIZE"]))
    train(cfg, args.data / "train.csv", args.wavs, None if args.no_cache else (args.cache or args.data / "spec_cache"), args.out,
          args.warmstart, args.max_steps, args.ckpt_every, device=device,
          num_workers=args.num_workers, max_batch_frames=args.max_batch_frames,
          amp_dtype="bf16" if args.bf16 else "fp16", learning_rate=args.lr)
    if dist.is_initialized():
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
