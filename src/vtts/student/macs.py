"""Analytic multiply-accumulate counts per second of audio."""

from __future__ import annotations

from .config import StudentConfig


def count_macs(c: StudentConfig, tokens_per_second: float = 14.0) -> dict[str, float]:
    fps = c.sample_rate / c.hop
    dur = tokens_per_second * c.d_depth * c.d_hidden * c.d_hidden * c.d_kernel
    ac = (tokens_per_second * c.a_token_depth * c.a_hidden ** 2 * c.a_kernel
          + fps * c.a_frame_depth * c.a_hidden ** 2 * c.a_kernel + fps * c.a_hidden * c.latent)
    if c.prosody:
        ac += fps * (c.p_depth * c.a_hidden ** 2 * c.a_kernel + c.a_hidden * 2 + 2 * c.a_hidden * 3)
    if c.decoder == "vocos":
        n_fft = 4 * c.hop
        per_frame = (c.latent * c.v_dim * 7
                     + c.v_blocks * (c.v_dim * 7 + 2 * c.v_dim * c.v_dim * c.v_mult)
                     + c.v_dim * (n_fft + 2))
        dec = fps * per_frame
        return {"duration": dur, "acoustic": ac, "decoder": dec, "per_second": dur + ac + dec}
    dec = fps * c.latent * c.c0 * 7
    ch, rate = c.c0, fps
    for u, k in zip(c.upsample, c.upsample_kernel):
        dec += ch * (ch // 2) * k * rate  # transposed conv: every input sample touches k taps
        ch //= 2
        rate *= u
        dec += len(c.res_dilations) * ch * ch * c.res_kernel * rate
    out_ch = 1 if c.decoder == "hifigan" else c.n_fft + 2
    dec += ch * out_ch * 7 * rate
    return {"duration": dur, "acoustic": ac, "decoder": dec, "per_second": dur + ac + dec}


# ESP32-P4 `bench` RTF of the v0.4.0 vi-en models (docs/reports/performance.md): S-vocos-p-bi
# 0.17-0.19, M-vocos-p-bi 0.25-0.27. A straight line through the midpoints against
# count_macs()["per_second"] (62.1 and 140.9 MMAC/s) separates the per-second cost that does not
# grow with the model (iSTFT, overlap-add, tokens, float glue: the intercept) from the cost per
# MAC (the slope). Larger widths keep more of the time in the int8 kernels, whose throughput
# per MAC improves with longer dot products, so the estimate is on the safe side for wider models.
P4_CALIBRATION = ((62.1, 0.18), (140.9, 0.26))


def estimate_p4_rtf(c: StudentConfig, calibration=P4_CALIBRATION) -> float:
    (m0, r0), (m1, r1) = calibration
    slope = (r1 - r0) / (m1 - m0)
    return r0 + slope * (count_macs(c)["per_second"] / 1e6 - m0)
