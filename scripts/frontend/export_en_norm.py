"""Fixture for runtime/test/en_norm_test.c: English text and its normalize_en output.

Usage: uv run python scripts/frontend/export_en_norm.py --sentences data/bilingual/sentences.jsonl \
   --out runtime/test/en_norm.tsv [--limit 3000]
"""

import argparse
import json
import random
from pathlib import Path

from vtts.frontend.en.normalize_en import normalize_en

EDGE = [
    "It costs $5, or $1.50, or $0.99, or $1,250.75, or €3 and £1.", "$2 million and $3.5 billion and $7 thousand.",
    "$1millionaire", "Meet at 9:30, 9:30 a.m., 9:30pm, 12:00, 7:05 PM or 10:00am.", "At 10:300 or 1:2 or 123:45.",
    "On 11/17/2026, 1/2, 13/45, 12/31/99, 1/2/202 and 01/02.", "The 5 March meeting, the 21 December party.",
    "On March 5th, May 1, June 2nd, March 2026, April 30th, Oct 5.", "Call at 3pm, 3 p.m., 11 AM or 7am.",
    "Growth was 15%, 3.5 % and 1,000%.", "Drive 5km, 1 km, 1.0 kg, 10 KB, 30°C, 1°, 5 mph and 2 km/h.",
    "The 1st, 2nd, 3rd, 21st, 112th and 1000th time.", "In 1999, 2005, 2020, 1100, 1999.5 and 20199.",
    "It fell to -5 degrees and rose to +3.", "Order 3x faster, 4K TV, 2FA and 5G.", "Pi is 3.14159 and e is 2.71.",
    "Numbers 1,234,567 and 12,34 and 123456789012345678901234.", "Dr. Smith, Mr. Lee, Mrs. Kim, Ms. Ho, Prof. X, St. Paul, Jr. and Sr.",
    "etc. vs. e.g. i.e.", "USB, NASA, ChatGPT, iPhone, HTMLParser, IoT, AirPods, DON'T, McDonald's.",
    "ESP32-P4, RTX3060, MP3, U23 and VN123.", "Rock & roll, C++ and me@example.", "Well-known x-ray e-mail.",
    "Wait... what?! Yes; no: maybe, ok.", "", "...", "1", "A", "a-b-c", "'quoted' words", "50 % off", "$",
    "12:5", "1/2/2026x", "May 5thx", "July 4th, 1776.", "At 5 p.m. on Jan. 3", "9.30 pm", "2 x 3 = 6",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=3000)
    ap.add_argument("--fuzz", type=int, default=20000)
    a = ap.parse_args()
    rows = [json.loads(x) for x in a.sentences.read_text(encoding="utf-8").splitlines() if x.strip()]
    en = [r["text"] for r in rows if r["lang"] == "en"]
    rnd = random.Random(0)
    texts = EDGE + rnd.sample(en, min(a.limit, len(en)))
    # random strings dense in the characters the regex passes react to
    atoms = list("0123456789") * 4 + list(":/.,$%-'&+@ ") * 2 + ["°", "°C", "€", "£", " am", "pm", "a.m.",
             "P.M.", "st", "nd", "th", "km", "Km", "mph", "km/h", "kb", " ", "  ", "May", "March", "June ",
             "Dr.", "e.g.", "ESP", "USB", "Ab", "x", "million", " billion", "thousand", "ab", "Z", "é", "ạ"]
    for _ in range(a.fuzz):
        texts.append("".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 14))))
    lines = [f"{t}\t{normalize_en(t)}" for t in texts if "\t" not in t and "\n" not in t]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} cases to {a.out}")


if __name__ == "__main__":
    main()
