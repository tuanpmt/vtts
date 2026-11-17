"""Write the C front-end parity fixture: sentences the device front-end supports + expected ids.

Usage: uv run python scripts/frontend/export_text_parity.py --sentences FILE... --out runtime/test/text_parity.tsv
       uv run python scripts/frontend/export_text_parity.py --v2 --sentences data/bilingual/sentences.jsonl \
           eval/sets/*.jsonl --out runtime/test/text_parity_v2.tsv
--v2 writes "mode<TAB>text<TAB>ids" lines (phoneme set v2) for vi, en and auto mode.
"""

import argparse
import re
from pathlib import Path

from vtts.frontend.text import text_to_ids

# not implemented on the device front-end (documented in runtime/README.md)
UNSUPPORTED = re.compile(
    r"@|https?://|www\.|\$|\d{4}-\d{2}-\d{2}|(?<!\d)0\d{2,3}[. ]?\d{3}[. ]?\d{3,4}"
    r"|\d\s?(?:đ|đồng|vnđ|vnd|usd|km|kg|cm|mm|ml|m|g|l|°)(?![^\W\d_])", re.IGNORECASE)


def supported(text: str) -> bool:
    return not UNSUPPORTED.search(text)


V2_EDGE = [
    "Đã kết nối Bluetooth với AirPods, pin còn 80%.", "Mở Spotify và play playlist Chill Vibes nhé.",
    "Chip ESP32-P4 chạy nhanh hơn ESP32-S3.", "Your package arrives on Tuesday, November 18, at 2:30 p.m.",
    "Cuộc họp trên Google Meet lúc 9 giờ, nhớ file PowerPoint nhé.", "It costs $5.50 and weighs 2 kg.",
    "Bật wifi rồi mở app YouTube.", "OK, xong rồi!", "Smartphone và smarthome.", "USB, NASA và iPhone 15.",
    "Gọi cho anh Nam lúc 7:30 sáng mai.", "Meeting with Lan at 3pm tomorrow.", "Tốc độ 150 Mbps, ping 20 ms.",
    "Hello. Xin chào! How are you? Bạn khỏe không;", "TP.HCM và HN.", "e-mail, x-ray, well-known.",
    "Don't stop. It's 5 o'clock.", "...", "", "a", "Đ", "100%", "ChatGPT, McDonald's và IoT.",
    "Câu rất dài " + "một hai ba bốn năm sáu bảy tám chín mười " * 6 + "hết.",
    "A very long English sentence " + "with many words that keep going on and on " * 6 + "until the end.",
]


def v2_lines(paths: list[Path], limit: int | None) -> list[str]:
    import json
    import random

    rows = []
    for p in paths:
        for x in p.read_text(encoding="utf-8").splitlines():
            if x.strip():
                rows.append(json.loads(x))
    rnd = random.Random(0)
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    cases = [("vi", t) for t in V2_EDGE] + [("en", t) for t in V2_EDGE] + [("auto", t) for t in V2_EDGE]
    for r in rows:
        mode = "en" if r.get("lang") == "en" else "vi"
        cases.append((mode, r["text"]))
        if rnd.random() < 0.3:
            cases.append(("auto", r["text"]))
    out = []
    for mode, text in cases:
        text = text.replace("\t", " ").replace("\n", " ")
        if mode != "en" and not supported(text):  # Vietnamese device normalizer subset, as for v1
            continue
        out.append(f"{mode}\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--sentences", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.v2:
        lines = v2_lines(a.sentences, a.limit)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    lines = []
    for f in a.sentences:
        for t in f.read_text(encoding="utf-8").splitlines():
            t = t.strip().replace("\t", " ")
            if t and supported(t):
                chunks = text_to_ids(t)
                lines.append(t + "\t" + ";".join(" ".join(map(str, c)) for c in chunks))
    if a.limit:
        lines = lines[: a.limit]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} cases to {a.out}")


if __name__ == "__main__":
    main()
