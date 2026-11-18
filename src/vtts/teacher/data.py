"""Teacher training data: ids from the project front-end, cached linear spectrograms."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from torch.utils.data import Dataset, Sampler

from vtts.data.audio import resample
from vtts.frontend.g2p import encode, g2p
from vtts.frontend.normalize import normalize
from vtts.frontend.phoneme_set import BOS, EOS, PAIR_MODES
from vtts.frontend.text import text_to_tokens, token_to_id_for

from .config import TeacherConfig
from .vits.mel_processing import spectrogram_torch


def read_rows(csv: Path) -> list[tuple[str, str, float, str | None, str | None]]:
    """uid|text|duration[|lang[|audio]]; lang (vi, en, mixed) selects phoneme set v2, a pair
    language (PAIR_MODES: zh, ko, ja, es ...) its pair token set. audio is the audio file relative to the wav directory
    (or absolute), for lists drawn from several synthesis runs (vtts.data.train_list); without it
    the file is WAVS/<uid>.wav or WAVS/<uid>.flac."""
    rows = []
    for line in Path(csv).read_text(encoding="utf-8").splitlines():
        if line.strip():
            uid, text, dur, *rest = line.split("|")
            lang = rest[0] if rest else None
            audio = rest[1] if len(rest) > 1 and rest[1] else None
            rows.append((uid, text, float(dur), lang, audio))
    return rows


def encode_text(text: str, lang: str | None) -> list[int]:
    """One id sequence for a training sentence: v1 when lang is None, the pair token set for a
    pair language (zh -> zh-en, ko -> ko-en, ja -> ja-en, es -> es-en ...; main-language text with
    English terms), else v2. English rows ("en") give the same ids in every pair token set, so a
    pair teacher trains on its own rows plus the vi-en English rows unchanged."""
    if lang is None:
        return encode(g2p(normalize(text)))
    mode = lang if lang == "en" or lang in PAIR_MODES else "vi"
    to_id = token_to_id_for(mode)
    toks = [t for chunk in text_to_tokens(text, mode) for t in chunk]
    return [to_id(BOS), *(to_id(t) for t in toks), to_id(EOS)]


class TeacherDataset(Dataset):
    def __init__(self, csv: Path, wav_dir: Path, cache_dir: Path | None, cfg: TeacherConfig):
        """cache_dir=None computes spectrograms on the fly (for corpora too large to cache)."""
        self.rows = read_rows(csv)
        self.wav_dir, self.cfg = Path(wav_dir), cfg
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def __len__(self) -> int:
        return len(self.rows)

    def frame_lengths(self) -> list[int]:
        return [int(d * self.cfg.sample_rate / self.cfg.hop_length) for _, _, d, _, _ in self.rows]

    def __getitem__(self, i: int) -> dict:
        uid, text, _, lang, audio = self.rows[i]
        ids = torch.tensor(encode_text(text, lang), dtype=torch.long)
        if audio is not None:
            path = self.wav_dir / audio  # an absolute audio path replaces wav_dir
        else:
            path = self.wav_dir / f"{uid}.wav"
            if not path.exists():
                path = self.wav_dir / f"{uid}.flac"
        x, sr = sf.read(path, dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        if sr != self.cfg.sample_rate:
            x = resample(x, sr, self.cfg.sample_rate)
        wav = torch.from_numpy(np.clip(x, -1.0, 1.0))[None]
        cache = self.cache_dir / f"{uid}.spec.pt" if self.cache_dir is not None else None
        if cache is not None and cache.exists():
            spec = torch.load(cache)
        else:
            c = self.cfg
            spec = spectrogram_torch(wav, c.filter_length, c.sample_rate, c.hop_length,
                                     c.win_length, center=False)[0]
            if cache is not None:
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
    """Batches of similar length; buckets and batch order reshuffled every epoch.

    With world_size > 1 (DistributedDataParallel) each rank gets a disjoint share of the batches.

    With max_frames, a batch also stops growing before (items x longest item) would exceed it,
    so buckets of long utterances get smaller batches instead of running out of GPU memory."""

    def __init__(self, lengths: list[int], batch_size: int, n_buckets: int = 10, seed: int = 1234,
                 max_frames: int | None = None, rank: int = 0, world_size: int = 1):
        self.lengths, self.batch_size, self.n_buckets, self.seed = lengths, batch_size, n_buckets, seed
        self.max_frames = max_frames
        self.rank, self.world_size = rank, world_size
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
            cur: list[int] = []
            longest = 0
            for i in bucket:
                grow = max(longest, self.lengths[i])
                if cur and (len(cur) == self.batch_size or
                            (self.max_frames and (len(cur) + 1) * grow > self.max_frames)):
                    batches.append(cur)
                    cur, grow = [], self.lengths[i]
                cur.append(i)
                longest = grow
            if cur:
                batches.append(cur)
        rnd.shuffle(batches)
        # multi-GPU: every rank builds the same list (same seed) and takes every world_size-th batch;
        # the tail is dropped so all ranks run the same number of steps
        n = len(batches) // self.world_size * self.world_size
        return batches[self.rank:n:self.world_size]

    def __iter__(self):
        return iter(self._batches())

    def __len__(self) -> int:
        return len(self._batches())
