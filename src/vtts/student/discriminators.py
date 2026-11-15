"""Multi-resolution spectrogram discriminator (as described for UnivNet / Vocos) and a
combined MPD + MRD wrapper with the VITS discriminator interface:
forward(y, y_hat) -> (real_logits, fake_logits, real_fmaps, fake_fmaps)."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F
from torch.nn.utils import weight_norm

RESOLUTIONS = ((512, 128, 512), (1024, 256, 1024), (2048, 512, 2048))


class SpecDiscriminator(nn.Module):
    def __init__(self, n_fft: int, hop: int, win: int, ch: int = 32):
        super().__init__()
        self.n_fft, self.hop, self.win = n_fft, hop, win
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
                          return_complex=True).abs()  # [B, F, T]
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
