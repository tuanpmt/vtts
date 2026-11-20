"""Record the device text mode a model starts in (optional dim text_mode, docs/model-format.md).

Usage: uv run python scripts/student/set_text_mode.py MODEL.vtts MODE [--out OUT.vtts]
E.g. MODE en for the English-only voice nu-en, which uses the vi-en token set: the firmware and
runtime/build/vtts_say then start in English instead of vi. MODE none removes the dim. The tensor
bytes are unchanged. Without --out the file is rewritten in place.
"""

import argparse
from pathlib import Path

from vtts.export.format import (
    pack_text_mode,
    read_tensors,
    token_set_of,
    unpack_text_mode,
    write_tensors,
)

MODES = {"v1": ("vi",), "vi-en": ("vi", "en", "auto")}  # other sets: their one main-language mode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("mode")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    dims, tensors = read_tensors(a.model)
    ts = token_set_of(dims)
    if a.mode == "none":
        dims.pop("text_mode", None)
    else:
        allowed = MODES.get(ts, (ts.split("-")[0],))
        if a.mode not in allowed:
            ap.error(f"token set {ts} has text modes {'|'.join(allowed)}, not {a.mode}")
        dims["text_mode"] = pack_text_mode(a.mode)
    out = a.out or a.model
    write_tensors(out, dims, tensors)
    print(f"wrote {out}: token set {ts}, text mode {unpack_text_mode(dims.get('text_mode', 0)) or 'default'}")


if __name__ == "__main__":
    main()
