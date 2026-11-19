"""Multi-resolution spectrogram discriminator (as described for UnivNet / Vocos) and a
combined MPD + MRD wrapper with the VITS discriminator interface:
forward(y, y_hat) -> (real_logits, fake_logits, real_fmaps, fake_fmaps)."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F
from torch.nn.utils import weight_norm

RESOLUTIONS = ((512, 128, 512), (1024, 256, 1024), (2048, 512, 2048))
# high-band discriminators: shorter windows (finer time grid) on the band above 4 kHz
HB_RESOLUTIONS = ((256, 64, 256), (512, 128, 512), (1024, 256, 1024))
LOG_SCALE = 0.1


class SpecDiscriminator(nn.Module):
    """2-D conv stack over |STFT| [T, F]. lo_bin > 0 keeps only bins >= lo_bin; log_mag uses
    log(|STFT|) so quiet bands (the 5-10 kHz noise floor) are not invisible next to formants."""

    def __init__(self, n_fft: int, hop: int, win: int, ch: int = 32, lo_bin: int = 0,
                 log_mag: bool = False):
        super().__init__()
        self.n_fft, self.hop, self.win = n_fft, hop, win
        self.lo_bin, self.log_mag = lo_bin, log_mag
        self.register_buffer("window", torch.hann_window(win), persistent=False)
        self.convs = nn.ModuleList([
            weight_norm(nn.Conv2d(1, ch, (3, 9), padding=(1, 4))),
            weight_norm(nn.Conv2d(ch, ch, (3, 9), stride=(1, 2), padding=(1, 4))),
            weight_norm(nn.Conv2d(ch, ch, (3, 9), stride=(1, 2), padding=(1, 4))),
            weight_norm(nn.Conv2d(ch, ch, (3, 9), stride=(1, 2), padding=(1, 4))),
            weight_norm(nn.Conv2d(ch, ch, (3, 3), padding=(1, 1))),
        ])
        self.post = weight_norm(nn.Conv2d(ch, 1, (3, 3), padding=(1, 1)))

    def forward(self, y: torch.Tensor):
        spec = torch.stft(y.squeeze(1).float(), self.n_fft, self.hop, self.win, self.window,
                          return_complex=True).abs()[:, self.lo_bin:]  # [B, F, T]
        if self.log_mag:
            # scaled down to keep the feature-matching term moderate (smoke run, 50 steps:
            # l_fm 14 unscaled, about 10 at 0.1, against 0.2 without these discriminators)
            spec = LOG_SCALE * torch.log(spec.clamp_min(1e-5))
        x = spec.transpose(1, 2).unsqueeze(1)  # [B, 1, T, F]
        fmap = []
        for c in self.convs:
            x = F.leaky_relu(c(x), 0.1)
            fmap.append(x)
        x = self.post(x)
        fmap.append(x)
        return torch.flatten(x, 1, -1), fmap


class MultiResolutionDiscriminator(nn.Module):
    def __init__(self, resolutions=RESOLUTIONS):
        super().__init__()
        self.discs = nn.ModuleList(SpecDiscriminator(*r) for r in resolutions)

    def forward(self, y, y_hat):
        rr, ff, fr, fg = [], [], [], []
        for d in self.discs:
            a, fa = d(y)
            b, fb = d(y_hat)
            rr.append(a); ff.append(b); fr.append(fa); fg.append(fb)
        return rr, ff, fr, fg


class HighBandDiscriminator(MultiResolutionDiscriminator):
    """Log-magnitude spectrogram discriminators restricted to frequencies >= lo_hz."""

    def __init__(self, resolutions=HB_RESOLUTIONS, lo_hz: float = 4000.0, sr: int = 22050):
        nn.Module.__init__(self)
        self.discs = nn.ModuleList(
            SpecDiscriminator(*r, lo_bin=round(lo_hz * r[0] / sr), log_mag=True)
            for r in resolutions)


class CombinedDiscriminator(nn.Module):
    def __init__(self, *discs: nn.Module):
        super().__init__()
        self.discs = nn.ModuleList(discs)

    def forward(self, y, y_hat):
        out = ([], [], [], [])
        for d in self.discs:
            for acc, part in zip(out, d(y, y_hat)):
                acc.extend(part)
        return out
