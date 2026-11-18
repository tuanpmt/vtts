"""Deterministic teacher inference: text -> 22.05 kHz float32 audio."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from vtts.frontend.g2p import encode, g2p
from vtts.frontend.phoneme_set import PAIR_MODES
from vtts.frontend.text import split_sentences, text_to_ids

from .config import TeacherConfig
from .model import build_generator

SEED = 1234
GAP_SECONDS = 0.15


class Teacher:
    def __init__(self, g, cfg: TeacherConfig, device: str):
        self.g, self.cfg, self.device = g, cfg, device

    @classmethod
    def load(cls, ckpt: Path, device: str = "cpu") -> Teacher:
        st = torch.load(ckpt, map_location=device, weights_only=False)
        known = TeacherConfig.__dataclass_fields__
        cfg = TeacherConfig(**{k: v for k, v in st.get("config", {}).items() if k in known})
        cfg.noise_scale = TeacherConfig.noise_scale  # inference setting, not a training property
        g = build_generator(cfg)
        g.load_state_dict(st["g"])
        g.to(device).eval()
        return cls(g, cfg, device)

    @torch.inference_mode()
    def synthesize_ids(self, ids: list[int]) -> np.ndarray:
        torch.manual_seed(SEED)
        x = torch.tensor([ids], dtype=torch.long, device=self.device)
        y = self.g.infer(x, torch.tensor([len(ids)], device=self.device),
                         noise_scale=self.cfg.noise_scale, length_scale=self.cfg.length_scale,
                         noise_scale_w=self.cfg.noise_scale_w)[0]
        return y[0, 0].float().cpu().numpy().astype(np.float32)

    def synthesize(self, text: str, lang: str | None = None) -> np.ndarray:
        """lang None: token set v1 (Vietnamese models); "vi" | "en" | "mixed": token set v2,
        with mixed text read in "vi" mode as in training (teacher/data.encode_text); "zh", "ko",
        "ja": the pair token sets zh-en, ko-en, ja-en (main-language and mixed text alike)."""
        gap = np.zeros(int(GAP_SECONDS * self.cfg.sample_rate), dtype=np.float32)
        if lang is None:
            chunks = [encode(g2p(chunk)) for chunk in split_sentences(text)]
        else:
            chunks = text_to_ids(text, lang if lang == "en" or lang in PAIR_MODES else "vi")
        parts: list[np.ndarray] = []
        for ids in chunks:
            if parts:
                parts.append(gap)
            parts.append(self.synthesize_ids(ids))
        return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
