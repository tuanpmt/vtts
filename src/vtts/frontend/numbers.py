"""Read numbers aloud in standard Northern Vietnamese."""

from __future__ import annotations

import re

DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
_SCALES = ("", "nghìn", "triệu", "tỷ", "nghìn tỷ")
_LIMIT = 10**15
_THOUSANDS = re.compile(r"\d{1,3}(\.\d{3})+")


def read_digits(s: str) -> str:
    return " ".join(DIGITS[int(c)] for c in s)


def _read_group(value: int, leading: bool) -> list[str]:
    h, t, u = value // 100, value // 10 % 10, value % 10
    words: list[str] = []
    if h or not leading:
        words += [DIGITS[h], "trăm"]
    if t == 0:
        if u:
            words += (["linh"] if words else []) + [DIGITS[u]]
    elif t == 1:
        words.append("mười")
        if u:
            words.append("lăm" if u == 5 else DIGITS[u])
    else:
        words += [DIGITS[t], "mươi"]
        if u:
            words.append({1: "mốt", 4: "tư", 5: "lăm"}.get(u, DIGITS[u]))
    return words


def read_int(n: int) -> str:
    if n < 0:
        raise ValueError("read_int wants a non-negative int")
    if n >= _LIMIT:
        return read_digits(str(n))
    if n == 0:
        return DIGITS[0]
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    words: list[str] = []
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            continue
        words += _read_group(g, leading=not words)
        if _SCALES[idx]:
            words.append(_SCALES[idx])
    return " ".join(words)


def _read_fraction(frac: str) -> str:
    if not frac.isdigit():
        return _read_unsigned(frac)
    return read_digits(frac) if frac.startswith("0") else read_int(int(frac))


def _read_unsigned(tok: str) -> str:
    if "," in tok:
        whole, frac = tok.split(",", 1)
        return f"{_read_unsigned(whole)} phẩy {_read_fraction(frac)}"
    if _THOUSANDS.fullmatch(tok):
        return read_int(int(tok.replace(".", "")))
    if "." in tok:
        whole, frac = tok.split(".", 1)
        return f"{_read_unsigned(whole)} chấm {_read_fraction(frac)}"
    if len(tok) > 1 and tok.startswith("0"):
        return read_digits(tok)
    return read_int(int(tok))


def read_number_token(tok: str) -> str:
    """Read '-5', '1.000.000', '3,5', '1.5', '007' and plain integers."""
    if tok.startswith("-"):
        return "âm " + _read_unsigned(tok[1:])
    return _read_unsigned(tok)
