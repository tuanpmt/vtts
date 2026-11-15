"""Monotonic alignment search (VITS, Kim et al. 2021) with numba instead of Cython."""

import numba
import numpy as np
import torch


@numba.njit(cache=True)
def _maximum_path_each(path, value, t_y, t_x, max_neg_val=-1e9):
    for y in range(t_y):
        for x in range(max(0, t_x + y - t_y), min(t_x, y + 1)):
            v_cur = max_neg_val if x == y else value[y - 1, x]
            if x == 0:
                v_prev = 0.0 if y == 0 else max_neg_val
            else:
                v_prev = value[y - 1, x - 1]
            value[y, x] += max(v_prev, v_cur)
    index = t_x - 1
    for y in range(t_y - 1, -1, -1):
        path[y, index] = 1
        if index != 0 and (index == y or value[y - 1, index] < value[y - 1, index - 1]):
            index -= 1


@numba.njit(parallel=True, cache=True)
def _maximum_path_batch(paths, values, t_ys, t_xs):
    for i in numba.prange(paths.shape[0]):
        _maximum_path_each(paths[i], values[i], t_ys[i], t_xs[i])


def maximum_path(neg_cent: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """neg_cent: [b, t_t, t_s]; mask: [b, t_t, t_s] -> hard alignment path of the same shape."""
    device, dtype = neg_cent.device, neg_cent.dtype
    values = neg_cent.detach().cpu().numpy().astype(np.float32)
    paths = np.zeros(values.shape, dtype=np.int32)
    t_t = mask.sum(1)[:, 0].cpu().numpy().astype(np.int32)
    t_s = mask.sum(2)[:, 0].cpu().numpy().astype(np.int32)
    _maximum_path_batch(paths, values, t_t, t_s)
    return torch.from_numpy(paths).to(device=device, dtype=dtype)
