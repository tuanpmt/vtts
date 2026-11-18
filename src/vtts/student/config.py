"""Student hyper-parameters and named presets."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class StudentConfig:
    size: str = "S"  # budget class: "S" or "M"
    vocab: int = 65
    sample_rate: int = 22050
    hop: int = 256
    latent: int = 192
    # duration
    d_hidden: int = 48
    d_depth: int = 3
    d_kernel: int = 5
    max_duration: int = 80
    # acoustic
    a_hidden: int = 64
    a_token_depth: int = 3
    a_frame_depth: int = 4
    a_kernel: int = 5
    # prosody (v2): frame-level log-F0 + energy predictor that conditions the acoustic model
    prosody: bool = False
    p_depth: int = 2
    # decoder
    decoder: str = "istft"  # "hifigan" | "istft" | "vocos"
    c0: int = 128
    upsample: tuple[int, ...] = (8, 8)
    upsample_kernel: tuple[int, ...] = (16, 16)
    res_dilations: tuple[int, ...] = (1, 3, 5)
    res_kernel: int = 3
    n_fft: int = 16  # istft only
    istft_hop: int = 4  # istft only
    # vocos only: ConvNeXt blocks at frame rate + iSTFT(n_fft=4*hop, hop)
    v_dim: int = 128
    v_blocks: int = 4
    v_mult: int = 3

    def __post_init__(self) -> None:
        total = 1
        for u in self.upsample:
            total *= u
        if self.decoder == "istft":
            total *= self.istft_hop
        if self.decoder == "vocos":
            total = self.hop
        if total != self.hop:
            raise ValueError(f"upsampling {total} != hop {self.hop}")


_S = StudentConfig()
PRESETS: dict[str, StudentConfig] = {
    "S-vocos": replace(_S, decoder="vocos", v_dim=112, v_blocks=4),
    "S-istft": replace(_S, c0=96),
    "S-hifigan": replace(_S, decoder="hifigan", c0=96, upsample=(8, 8, 4),
                         upsample_kernel=(16, 16, 8), res_dilations=(1, 3)),
    "M-vocos": replace(_S, size="M", decoder="vocos", d_hidden=64, a_hidden=96, v_dim=160,
                       v_blocks=6),
}
PRESETS["S-vocos-p"] = replace(PRESETS["S-vocos"], prosody=True)
PRESETS["M-vocos-p"] = replace(PRESETS["M-vocos"], prosody=True)
# bilingual Vietnamese + English (token set v2); -s3 halves the vocoder MLP for the ESP32-S3
PRESETS["M-vocos-p-bi"] = replace(PRESETS["M-vocos-p"], vocab=107)
PRESETS["S-vocos-p-bi"] = replace(PRESETS["S-vocos-p"], vocab=107)
PRESETS["M-vocos-p-bi-s3"] = replace(PRESETS["M-vocos-p-bi"], v_mult=2)

# Other pairs (main language + English): the vocabulary covers the pair's token set (shared ids
# 0..106 plus the language block); same model sizes as the vi-en presets.
def _pair_presets() -> None:
    from vtts.frontend.phoneme_set import TOKEN_SETS

    for pair in ("zh-en", "ko-en", "ja-en"):
        n = len(TOKEN_SETS[pair])
        PRESETS[f"M-vocos-p-{pair}"] = replace(PRESETS["M-vocos-p"], vocab=n)
        PRESETS[f"S-vocos-p-{pair}"] = replace(PRESETS["S-vocos-p"], vocab=n)
        PRESETS[f"M-vocos-p-{pair}-s3"] = replace(PRESETS[f"M-vocos-p-{pair}"], v_mult=2)


_pair_presets()
