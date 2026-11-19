"""Build the RLEX blob (Russian stress tables) for the device front-end.

Usage: uv run python scripts/frontend/build_ru_blob.py --out ru_lex.bin

Source: the tables the Python front-end reads, src/vtts/frontend/lexicons/ru/overrides.tsv,
stress.tsv and stress_suffixes.tsv (g2p_ru.stressed). The C reader (runtime/src/vtts_text_ru.c,
vtts_rlex_init) reads the blob in place: no malloc, no copies, so it can be mapped from flash.

Letters are one byte: а..я = 1..32 (U+0430..U+044F), ё = 33.

Format RLEX version 1, little-endian, every section 4-byte aligned:

  Header (96 bytes):
    0   magic "RLEX", version u16 = 1, header size u16 = 96
    8   block u32: entries per block (16); root u32: stressed vowel counted from the end for a word
        no ending matches (the "-" entry of stress_suffixes.tsv); max_suffix u32: longest ending
    20  three tables (overrides, words, suffixes), 20 bytes each:
        n u32, n_blocks u32, index_off u32, data_off u32, data_size u32
  Tables: keys sorted bytewise, in blocks of `block` entries; index (n_blocks u32): offset of each
    block in the data. In a block the first entry is [key length u8][key], the next ones
    [shared prefix length u8][suffix length u8][suffix]; then the value.
    overrides, words: key = the word with ё written е; value [stress u8][yo u8]: the index of the
      stressed letter in the word (255: none) and of a letter е written ё (255: none).
    suffixes: key = the ending reversed (последний letter first); value [back u8]: the stressed
      vowel counted from the end of the word.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from vtts.frontend.lexicons import load_table

MAGIC, VERSION, HEADER_SIZE, BLOCK = b"RLEX", 1, 96, 16


def code(ch: str) -> int:
    if ch == "ё":
        return 33
    c = ord(ch) - 0x430 + 1
    if not 1 <= c <= 32:
        raise ValueError(f"not a Russian letter: {ch!r}")
    return c


def enc(word: str) -> bytes:
    return bytes(code(ch) for ch in word)


def word_value(key: str, marked: str) -> bytes:
    """[stress index][yo index] of a marked word (с+ло́во written with + before the vowel)."""
    k = marked.index("+")
    plain = marked.replace("+", "")
    if plain.replace("ё", "е") != key or len(plain) > 250 or plain.count("ё") > 1:
        raise ValueError(f"bad entry {key!r} {marked!r}")
    yo = plain.index("ё") if "ё" in plain else 255
    return bytes([k, yo])


def table(entries: list[tuple[bytes, bytes]]) -> tuple[bytes, bytes, int]:
    entries.sort()
    index, data = [], bytearray()
    prev = b""
    for i, (key, val) in enumerate(entries):
        if len(key) > 255:
            raise ValueError("key too long")
        if i % BLOCK == 0:
            index.append(len(data))
            data += bytes([len(key)]) + key
        else:
            shared = 0
            while shared < min(len(prev), len(key), 255) and prev[shared] == key[shared]:
                shared += 1
            data += bytes([shared, len(key) - shared]) + key[shared:]
        data += val
        prev = key
    return struct.pack(f"<{len(index)}I", *index), bytes(data), len(index)


def build() -> bytes:
    over = [(enc(k), word_value(k, v)) for k, v in load_table("ru", "overrides").items()]
    words = [(enc(k), word_value(k, v)) for k, v in load_table("ru", "stress").items()]
    suf = load_table("ru", "stress_suffixes")
    root = int(suf["-"])
    sufs = [(enc(k[1:][::-1]), bytes([int(v)])) for k, v in suf.items() if k != "-"]
    max_suffix = max(len(k) for k, _ in sufs)
    parts = []
    off = HEADER_SIZE
    body = bytearray()
    for entries in (over, words, sufs):
        index, data, nb = table(entries)
        index_off = off + len(body)
        body += index
        while len(body) % 4:
            body += b"\0"
        data_off = off + len(body)
        body += data
        while len(body) % 4:
            body += b"\0"
        parts.append(struct.pack("<5I", len(entries), nb, index_off, data_off, len(data)))
    head = MAGIC + struct.pack("<HH", VERSION, HEADER_SIZE) + struct.pack("<3I", BLOCK, root, max_suffix)
    head += b"".join(parts)
    head += b"\0" * (HEADER_SIZE - len(head))
    return head + bytes(body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    blob = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(blob)
    print(f"{a.out}: {len(blob)} bytes")


if __name__ == "__main__":
    main()
