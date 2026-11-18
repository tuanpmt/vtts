"""Teacher training list from a synthesis run: OUT/pre/train.csv with uid|text|dur|lang.

Usage: uv run python scripts/data/synth_to_csv.py --sentences data/bilingual/sentences.jsonl \
       --synth data/bilingual/synth --out data/bilingual/pre
Only ids whose manifest status is ok and whose audio file exists are listed. Rows of a pair
language are left out when the text holds characters its front-end cannot read
(vtts.data.train_list.UNREADABLE: Han characters without a reading for zh, Hanja or bare jamo for
ko, kanji without a reading for ja, letters of other scripts for the Latin-script pairs), so the
ids always match the audio. --reject leaves out ids listed by scripts/data/asr_filter.py.
"""

import argparse
import json
from pathlib import Path

from vtts.data.train_list import unreadable as is_unreadable


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=Path, required=True)
    ap.add_argument("--synth", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reject", type=Path, default=None,
                    help="file of ids to leave out (e.g. SYNTH/rejected.txt from asr_filter.py)")
    a = ap.parse_args()
    rejected = set(a.reject.read_text().split()) if a.reject else set()
    text = {}
    for line in a.sentences.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            text[r["id"]] = (r["text"], r["lang"])
    dur = {}
    for line in (a.synth / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["status"] == "ok" and (a.synth / "audio" / f"{r['id']}.flac").exists():
                dur[r["id"]] = r["dur"]
    a.out.mkdir(parents=True, exist_ok=True)
    unreadable = {i for i, (t, lang) in text.items() if is_unreadable(t, lang)}
    if unreadable:
        print(f"{len(unreadable)} pair-language sentences left out (characters without a reading)")
    rows = [f"{i}|{text[i][0]}|{d:.3f}|{text[i][1]}" for i, d in dur.items()
            if i in text and "|" not in text[i][0] and i not in unreadable and i not in rejected]
    (a.out / "train.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    hours = sum(dur[r.split("|")[0]] for r in rows) / 3600
    print(f"{len(rows)} rows, {hours:.1f} h")


if __name__ == "__main__":
    main()
