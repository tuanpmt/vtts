"""Teacher training data: ids from the project front-end, cached linear spectrograms."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from torch.utils.data import Dataset, Sampler

from vtts.frontend.g2p import encode, g2p
from vtts.frontend.normalize import normalize

from .config import TeacherConfig
from .vits.mel_processing import spectrogram_torch


def read_rows(csv: Path) -> list[tuple[str, str, float]]:
    rows = []
    for line in Path(csv).read_text(encoding="utf-8").splitlines():
        if line.strip():
            uid, text, dur = line.split("|")
            rows.append((uid, text, float(dur)))
    return rows


class TeacherDataset(Dataset):
    def __init__(self, csv: Path, wav_dir: Path, cache_dir: Path, cfg: TeacherConfig):
        self.rows = read_rows(csv)
        self.wav_dir, self.cache_dir, self.cfg = Path(wav_dir), Path(cache_dir), cfg
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def __len__(self) -> int:
        return len(self.rows)

    def frame_lengths(self) -> list[int]:
        return [int(d * self.cfg.sample_rate / self.cfg.hop_length) for _, _, d in self.rows]

    def __getitem__(self, i: int) -> dict:
        uid, text, _ = self.rows[i]
        ids = torch.tensor(encode(g2p(normalize(text))), dtype=torch.long)
        x, sr = sf.read(self.wav_dir / f"{uid}.wav", dtype="float32")
        if sr != self.cfg.sample_rate:
            raise ValueError(f"{uid}: sample rate {sr} != {self.cfg.sample_rate}")
        wav = torch.from_numpy(np.clip(x, -1.0, 1.0))[None]
        cache = self.cache_dir / f"{uid}.spec.pt"
        if cache.exists():
            spec = torch.load(cache)
        else:
            c = self.cfg
            spec = spectrogram_torch(wav, c.filter_length, c.sample_rate, c.hop_length,
                                     c.win_length, center=False)[0]
            torch.save(spec, cache)
        n = spec.shape[1]
        wav = wav[:, : n * self.cfg.hop_length]
        if wav.shape[1] < n * self.cfg.hop_length:
            wav = torch.nn.functional.pad(wav, (0, n * self.cfg.hop_length - wav.shape[1]))
        return {"id": uid, "ids": ids, "spec": spec, "wav": wav}


def collate(batch: list[dict], segment_frames: int = 32, hop: int = 256) -> dict:
    n_ids = max(len(b["ids"]) for b in batch)
    n_frames = max(max(b["spec"].shape[1] for b in batch), segment_frames)
    ids = torch.zeros(len(batch), n_ids, dtype=torch.long)
    spec = torch.zeros(len(batch), batch[0]["spec"].shape[0], n_frames)
    wav = torch.zeros(len(batch), 1, n_frames * hop)
    for k, b in enumerate(batch):
        ids[k, : len(b["ids"])] = b["ids"]
        spec[k, :, : b["spec"].shape[1]] = b["spec"]
        wav[k, :, : b["wav"].shape[1]] = b["wav"]
    return {
        "id": [b["id"] for b in batch],
        "ids": ids,
        "ids_lengths": torch.tensor([len(b["ids"]) for b in batch], dtype=torch.long),
        "spec": spec,
        "spec_lengths": torch.tensor([b["spec"].shape[1] for b in batch], dtype=torch.long),
        "wav": wav,
    }


class BucketSampler(Sampler[list[int]]):
    """Batches of similar length; buckets and batch order reshuffled every epoch."""

    def __init__(self, lengths: list[int], batch_size: int, n_buckets: int = 10, seed: int = 1234):
        self.lengths, self.batch_size, self.n_buckets, self.seed = lengths, batch_size, n_buckets, seed
        self.epoch = 0

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def _batches(self) -> list[list[int]]:
        rnd = random.Random(self.seed + self.epoch)
        order = sorted(range(len(self.lengths)), key=lambda i: self.lengths[i])
        size = -(-len(order) // self.n_buckets)
        batches = []
        for b in range(0, len(order), size):
            bucket = order[b: b + size]
            rnd.shuffle(bucket)
            batches += [bucket[i: i + self.batch_size] for i in range(0, len(bucket), self.batch_size)]
        rnd.shuffle(batches)
        return batches

    def __iter__(self):
        return iter(self._batches())

    def __len__(self) -> int:
        return len(self._batches())
