"""Build the VITS generator / discriminator and load a Piper warm-start checkpoint."""

from __future__ import annotations

from pathlib import Path

import torch

from .config import TeacherConfig
from .vits.models import MultiPeriodDiscriminator, SynthesizerTrn


def build_generator(cfg: TeacherConfig) -> SynthesizerTrn:
    return SynthesizerTrn(
        n_vocab=cfg.n_vocab, spec_channels=cfg.spec_channels,
        segment_size=cfg.segment_size // cfg.hop_length, inter_channels=cfg.inter_channels,
        hidden_channels=cfg.hidden_channels, filter_channels=cfg.filter_channels,
        n_heads=cfg.n_heads, n_layers=cfg.n_layers, kernel_size=cfg.kernel_size,
        p_dropout=cfg.p_dropout, resblock=cfg.resblock,
        resblock_kernel_sizes=cfg.resblock_kernel_sizes,
        resblock_dilation_sizes=cfg.resblock_dilation_sizes, upsample_rates=cfg.upsample_rates,
        upsample_initial_channel=cfg.upsample_initial_channel,
        upsample_kernel_sizes=cfg.upsample_kernel_sizes, n_speakers=1, gin_channels=0,
        use_sdp=cfg.use_sdp)


def build_discriminator(cfg: TeacherConfig) -> MultiPeriodDiscriminator:
    return MultiPeriodDiscriminator(use_spectral_norm=False)


def load_warmstart(g: SynthesizerTrn, d: MultiPeriodDiscriminator, ckpt: Path) -> None:
    """Load weights only (fresh optimizer and step), strictly: a project checkpoint
    (keys g / d) or a Piper Lightning checkpoint (keys model_g.* / model_d.*)."""
    raw = torch.load(ckpt, map_location="cpu", weights_only=False)
    if "g" in raw and "d" in raw:
        g.load_state_dict(raw["g"], strict=True)
        d.load_state_dict(raw["d"], strict=True)
        return
    sd = raw["state_dict"]
    g.load_state_dict({k[8:]: v for k, v in sd.items() if k.startswith("model_g.")}, strict=True)
    d.load_state_dict({k[8:]: v for k, v in sd.items() if k.startswith("model_d.")}, strict=True)
