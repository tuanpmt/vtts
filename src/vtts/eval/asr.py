"""Vietnamese ASR for intelligibility scoring (PhoWhisper by default)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from vtts.data.audio import resample


def default_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class AsrTranscriber:
    def __init__(self, model_id: str = "vinai/PhoWhisper-large", device: str | None = None):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        self.device = device or default_device()
        dtype = torch.float16 if self.device in ("cuda", "mps") else torch.float32
        self.processor = WhisperProcessor.from_pretrained(model_id)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_id, dtype=dtype)
        self.model.to(self.device).eval()
        self.dtype = dtype

    def _load(self, path: Path) -> np.ndarray:
        x, sr = sf.read(path, dtype="float32", always_2d=True)
        return resample(x.mean(axis=1), sr, 16000)

    def transcribe(self, paths: list[Path], batch_size: int = 8) -> list[str]:
        import torch

        out: list[str] = []
        for i in range(0, len(paths), batch_size):
            audio = [self._load(Path(p)) for p in paths[i: i + batch_size]]
            feats = self.processor(audio, sampling_rate=16000, return_tensors="pt").input_features
            with torch.inference_mode():
                ids = self.model.generate(feats.to(self.device, self.dtype), max_new_tokens=200)
            out += [t.strip() for t in self.processor.batch_decode(ids, skip_special_tokens=True)]
        return out
