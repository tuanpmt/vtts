"""Student model. Ops are limited to what the C runtime implements."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from .config import StudentConfig

LRELU = 0.1


class ConvBlock(nn.Module):
    """Conv1d -> ReLU -> LayerNorm over channels, with residual."""

    def __init__(self, ch: int, k: int):
        super().__init__()
        self.conv = nn.Conv1d(ch, ch, k, padding=k // 2)
        self.norm = nn.LayerNorm(ch)

    def forward(self, x):
        y = F.relu(self.conv(x))
        return x + self.norm(y.transpose(1, 2)).transpose(1, 2)


class DurationModel(nn.Module):
    def __init__(self, c: StudentConfig):
        super().__init__()
        self.emb = nn.Embedding(c.vocab, c.d_hidden)
        self.blocks = nn.ModuleList(ConvBlock(c.d_hidden, c.d_kernel) for _ in range(c.d_depth))
        self.out = nn.Linear(c.d_hidden, 1)

    def forward(self, ids):  # [B, N] -> log duration [B, N]
        x = self.emb(ids).transpose(1, 2)
        for b in self.blocks:
            x = b(x)
        return self.out(x.transpose(1, 2)).squeeze(-1)


def expand(x: torch.Tensor, durations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """x [B, C, N], durations [B, N] (int) -> frames [B, C, T] and position features [B, 2, T]."""
    outs, feats = [], []
    for b in range(x.shape[0]):
        d = durations[b].clamp(min=0)
        idx = torch.repeat_interleave(torch.arange(len(d), device=x.device), d)
        outs.append(x[b][:, idx])
        start = torch.cumsum(d, 0) - d
        pos = torch.arange(int(d.sum()), device=x.device) - start[idx]
        frac = (pos.float() + 0.5) / d[idx].float()
        feats.append(torch.stack([frac, torch.log(d[idx].float())]))
    t = max(o.shape[1] for o in outs)
    out = torch.stack([F.pad(o, (0, t - o.shape[1])) for o in outs])
    feat = torch.stack([F.pad(f, (0, t - f.shape[1])) for f in feats])
    return out, feat


class AcousticModel(nn.Module):
    def __init__(self, c: StudentConfig):
        super().__init__()
        self.cfg = c
        self.emb = nn.Embedding(c.vocab, c.a_hidden)
        self.token_blocks = nn.ModuleList(ConvBlock(c.a_hidden, c.a_kernel) for _ in range(c.a_token_depth))
        self.pos = nn.Linear(2, c.a_hidden)
        if c.prosody:
            self.pitch_blocks = nn.ModuleList(ConvBlock(c.a_hidden, c.a_kernel) for _ in range(c.p_depth))
            self.pitch_out = nn.Conv1d(c.a_hidden, 2, 1)       # normalized log-F0, energy
            self.pitch_emb = nn.Conv1d(2, c.a_hidden, 3, padding=1)
        self.frame_blocks = nn.ModuleList(ConvBlock(c.a_hidden, c.a_kernel) for _ in range(c.a_frame_depth))
        self.out = nn.Conv1d(c.a_hidden, c.latent, 1)
        self.expressiveness = 1.0  # inference: scales the predicted (normalized) log-F0

    def forward(self, ids, durations, prosody=None):
        """Returns (latent, predicted prosody or None). `prosody` [B, 2, T] forces the
        conditioning (teacher forcing in training)."""
        x = self.emb(ids).transpose(1, 2)
        for b in self.token_blocks:
            x = b(x)
        x, feat = expand(x, durations)
        x = x + self.pos(feat.transpose(1, 2)).transpose(1, 2)
        pred = None
        if self.cfg.prosody:
            p = x
            for b in self.pitch_blocks:
                p = b(p)
            pred = self.pitch_out(p)
            use = prosody
            if use is None:
                use = torch.cat([pred[:, :1] * self.expressiveness, pred[:, 1:]], dim=1)
            x = x + self.pitch_emb(use)
        for b in self.frame_blocks:
            x = b(x)
        return self.out(x), pred


class ResBlock(nn.Module):
    def __init__(self, ch: int, k: int, dilations: tuple[int, ...]):
        super().__init__()
        self.convs = nn.ModuleList(
            nn.Conv1d(ch, ch, k, dilation=d, padding=d * (k - 1) // 2) for d in dilations)

    def forward(self, x):
        for c in self.convs:
            x = x + c(F.leaky_relu(x, LRELU))
        return x


class ConvNeXtBlock(nn.Module):
    def __init__(self, dim: int, mult: int):
        super().__init__()
        self.dw = nn.Conv1d(dim, dim, 7, padding=3, groups=dim)
        self.norm = nn.LayerNorm(dim)
        self.pw1 = nn.Linear(dim, dim * mult)
        self.pw2 = nn.Linear(dim * mult, dim)
        self.gamma = nn.Parameter(torch.full((dim,), 0.1))

    def forward(self, x):  # [B, C, T]
        y = self.norm(self.dw(x).transpose(1, 2))
        y = self.pw2(F.gelu(self.pw1(y), approximate="tanh")) * self.gamma
        return x + y.transpose(1, 2)


class VocosDecoder(nn.Module):
    """All weights at frame rate; waveform from an iSTFT with n_fft = 4 * hop."""

    def __init__(self, c: StudentConfig):
        super().__init__()
        self.cfg = c
        self.n_fft = 4 * c.hop
        self.pre = nn.Conv1d(c.latent, c.v_dim, 7, padding=3)
        self.norm = nn.LayerNorm(c.v_dim)
        self.blocks = nn.ModuleList(ConvNeXtBlock(c.v_dim, c.v_mult) for _ in range(c.v_blocks))
        self.final_norm = nn.LayerNorm(c.v_dim)
        self.head = nn.Linear(c.v_dim, self.n_fft + 2)
        self.register_buffer("window", torch.hann_window(self.n_fft), persistent=False)

    def forward(self, z):
        x = self.norm(self.pre(z).transpose(1, 2)).transpose(1, 2)
        for b in self.blocks:
            x = b(x)
        h = self.head(self.final_norm(x.transpose(1, 2))).transpose(1, 2).float()  # iSTFT needs fp32
        n = self.n_fft // 2 + 1
        mag = torch.exp(h[:, :n].clamp(max=6.0))
        spec = torch.polar(mag, h[:, n:])
        wav = torch.istft(spec, self.n_fft, self.cfg.hop, self.n_fft, self.window, center=True,
                          length=z.shape[-1] * self.cfg.hop)
        return torch.tanh(wav).unsqueeze(1)


class Decoder(nn.Module):
    def __init__(self, c: StudentConfig):
        super().__init__()
        self.cfg = c
        self.pre = nn.Conv1d(c.latent, c.c0, 7, padding=3)
        self.ups, self.res = nn.ModuleList(), nn.ModuleList()
        ch = c.c0
        for u, k in zip(c.upsample, c.upsample_kernel):
            self.ups.append(nn.ConvTranspose1d(ch, ch // 2, k, stride=u, padding=(k - u) // 2))
            ch //= 2
            self.res.append(ResBlock(ch, c.res_kernel, c.res_dilations))
        out_ch = 1 if c.decoder == "hifigan" else c.n_fft + 2  # (n_fft/2+1) mag + same phase
        self.post = nn.Conv1d(ch, out_ch, 7, padding=3)
        if c.decoder == "istft":
            self.register_buffer("window", torch.hann_window(c.n_fft), persistent=False)

    def forward(self, z):
        x = self.pre(z)
        for up, res in zip(self.ups, self.res):
            x = res(up(F.leaky_relu(x, LRELU)))
        x = self.post(F.leaky_relu(x, 0.01)).float()  # tanh/iSTFT in fp32 under AMP
        if self.cfg.decoder == "hifigan":
            return torch.tanh(x)
        n = self.cfg.n_fft // 2 + 1
        mag = torch.exp(x[:, :n].clamp(max=6.0))
        phase = torch.pi * torch.sin(x[:, n:])
        spec = torch.polar(mag, phase)
        wav = torch.istft(spec, self.cfg.n_fft, self.cfg.istft_hop, self.cfg.n_fft, self.window,
                          center=True, length=x.shape[-1] * self.cfg.istft_hop)
        return torch.tanh(wav).unsqueeze(1)


class Student(nn.Module):
    def __init__(self, cfg: StudentConfig):
        super().__init__()
        self.cfg = cfg
        self.duration = DurationModel(cfg)
        self.acoustic = AcousticModel(cfg)
        self.decoder = VocosDecoder(cfg) if cfg.decoder == "vocos" else Decoder(cfg)

    def forward_duration(self, ids):
        return self.duration(ids)

    @property
    def expressiveness(self) -> float:
        return self.acoustic.expressiveness

    @expressiveness.setter
    def expressiveness(self, v: float) -> None:
        self.acoustic.expressiveness = float(v)

    def forward_latent(self, ids, durations):
        return self.acoustic(ids, durations)[0]

    def forward_latent_train(self, ids, durations, prosody):
        return self.acoustic(ids, durations, prosody)

    def decode(self, z):
        return self.decoder(z)

    def measure_decoder_macs(self, frames: int) -> float:
        """Count conv MACs of the decoder with forward hooks (used to check the analytic counter)."""
        total = 0.0

        def hook(mod, inp, out):
            nonlocal total
            if isinstance(mod, nn.ConvTranspose1d):
                total += inp[0].shape[1] * mod.out_channels * mod.kernel_size[0] * inp[0].shape[-1]
            elif isinstance(mod, nn.Conv1d):
                total += (mod.in_channels // mod.groups) * mod.out_channels * mod.kernel_size[0] \
                    * out.shape[-1]
            elif isinstance(mod, nn.Linear):
                total += mod.in_features * mod.out_features * out.shape[:-1].numel()

        hs = [m.register_forward_hook(hook) for m in self.decoder.modules()
              if isinstance(m, (nn.Conv1d, nn.ConvTranspose1d, nn.Linear))]
        with torch.no_grad():
            self.decoder(torch.zeros(1, self.cfg.latent, frames))
        for h in hs:
            h.remove()
        return total


def durations_from_log(log_dur: torch.Tensor, length_scale: float, max_duration: int) -> torch.Tensor:
    """Same rule as the C runtime: round-half-even(exp(log_dur) * scale), clamped to [1, max]."""
    return torch.clamp(torch.round(torch.exp(log_dur) * length_scale), 1, max_duration).long()
