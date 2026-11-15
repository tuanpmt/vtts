"""Convert npz distillation shards to mmap'able .npy directories.

Usage: uv run python scripts/student/convert_shards.py --src data/distill/shards --dst data/distill/mm [--delete-src]
"""

import argparse
from pathlib import Path

from vtts.student.distill_data import convert_to_mmap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--dst", type=Path, required=True)
    ap.add_argument("--delete-src", action="store_true", help="delete each npz after converting it")
    a = ap.parse_args()
    if a.delete_src:
        for p in sorted(a.src.glob("shard_*.npz")):
            tmp = a.src / "_one"
            tmp.mkdir(exist_ok=True)
            (tmp / p.name).symlink_to(p.resolve())
            convert_to_mmap(tmp, a.dst)
            (tmp / p.name).unlink()
            p.unlink()
            print("converted", p.name, flush=True)
        tmp = a.src / "_one"
        if tmp.exists():
            tmp.rmdir()
    else:
        convert_to_mmap(a.src, a.dst)


if __name__ == "__main__":
    main()
