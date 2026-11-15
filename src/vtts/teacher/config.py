"""Teacher hyper-parameters ("medium" Piper/VITS layout)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TeacherConfig:
    # audio / features
    sample_rate: int = 22050
    filter_length: int = 1024
    hop_length: int = 256
    win_length: int = 1024
    mel_channels: int = 80
    mel_fmin: float = 0.0
    mel_fmax: float | None = None
    # model
    n_vocab: int = 256  # embedding rows; project ids use < 65, table kept for warm-start
    inter_channels: int = 192
    hidden_channels: int = 192
    filter_channels: int = 768
    n_heads: int = 2
    n_layers: int = 6
    kernel_size: int = 3
    p_dropout: float = 0.1
    resblock: str = "2"
    resblock_kernel_sizes: tuple[int, ...] = (3, 5, 7)
    resblock_dilation_sizes: tuple[tuple[int, ...], ...] = ((1, 2), (2, 6), (3, 12))
    upsample_rates: tuple[int, ...] = (8, 8, 4)
    upsample_initial_channel: int = 256
    upsample_kernel_sizes: tuple[int, ...] = (16, 16, 8)
    use_sdp: bool = True
    segment_size: int = 8192  # samples
    # training
    learning_rate: float = 2e-4
    betas: tuple[float, float] = (0.8, 0.99)
    eps: float = 1e-9
    lr_decay: float = 0.999875
    c_mel: float = 45.0
    c_kl: float = 1.0
    batch_size: int = 16
    # inference
    noise_scale: float = 0.333  # measured: CER 0.029 vs 0.062 at 0.667 (teacher B @15k)
    noise_scale_w: float = 0.8
    length_scale: float = 1.0

    @property
    def spec_channels(self) -> int:
        return self.filter_length // 2 + 1
