"""Build the JLEX blob (Japanese reading tables and NFKC data) for the device front-end.

Usage: uv run python scripts/frontend/build_ja_blob.py --out ja_lex.bin

Source: the tables the Python front-end reads, src/vtts/frontend/lexicons/ja/words.tsv,
after_kanji.tsv, after_katakana.tsv and kanji.tsv (overrides.tsv is already folded into them by
scripts/frontend/build_ja_lexicon.py), and Python's unicodedata for unicodedata.normalize("NFKC")
of normalize_ja. The C reader (runtime/src/vtts_text_ja.c, vtts_jlex_init) reads the blob in
place: no malloc, no copies, so it can be mapped straight from flash.

Format JLEX version 1, little-endian, every section 4-byte aligned:

  Header (128 bytes):
    0   magic "JLEX", version u16 = 1, header size u16 = 128
    8   max_len u32: longest key (code points) of words, after_kanji and after_katakana (the
        longest match window of g2p_ja); block u32: entries per block (16)
    16  four tables (words, after_kanji, after_katakana, kanji), 20 bytes each:
        n u32, n_blocks u32, index_off u32, data_off u32, data_size u32
    96  NFKC: n_dec u32, dec_off u32, dec_data_off u32, dec_data_size u32, n_ccc u32, ccc_off u32,
        n_comp u32
    124 comp_off u32
  Tables: keys are UTF-8, sorted bytewise (= code point order), in blocks of `block` entries.
    index (n_blocks u32): offset of each block in the data. In a block, the first entry is
    [key length u8][key][reading length u8][reading], the next ones
    [shared prefix length u8][suffix length u8][suffix][reading length u8][reading].
    A reading is katakana as bytes: code point - 0x30A0 (ァ = 0x01 .. ー = 0x5C).
  NFKC (the Unicode version of the Python that built the blob):
    dec: n_dec entries of 8 bytes sorted by code point: [code point | byte length << 21 u32]
      [offset u32 into dec_data]: unicodedata.normalize("NFKD", ch) as UTF-8, for every code
      point it changes except the Hangul syllables (composed and decomposed by arithmetic).
    ccc: n_ccc entries u32 [code point | combining class << 24], sorted, for every class > 0.
    comp: n_comp entries of 12 bytes [first u32][second u32][composite u32], sorted by (first,
      second): the primary composites (canonical pairs that NFC recomposes).
  A reader computes NFKC as decomposition, canonical ordering and canonical composition.

Lookups are exact-key binary searches over the first key of each block and a scan inside it;
g2p_ja's forward longest match tries the lengths from max_len down.
"""

from __future__ import annotations

import argparse
import struct
import sys
import unicodedata
from pathlib import Path

from vtts.frontend.ja.g2p_ja import CONTEXTS, tables

MAGIC, VERSION, HEADER_SIZE, BLOCK = b"JLEX", 1, 128, 16
TABLES = ("words", "after_kanji", "after_katakana", "kanji")
KANA0 = 0x30A0


def _reading(r: str) -> bytes:
    out = bytes(ord(c) - KANA0 for c in r)
    if not out or not all(0 < b < 0x60 for b in out) or len(out) > 255:
        raise ValueError(f"reading is not katakana: {r!r}")
    return out


def pack_table(table: dict[str, str]) -> tuple[bytes, bytes, int]:
    """(index, data, n_blocks) of one table."""
    rows = sorted((k.encode("utf-8"), _reading(v)) for k, v in table.items())
    index, data = bytearray(), bytearray()
    prev = b""
    for i, (key, reading) in enumerate(rows):
        if len(key) > 255:
            raise ValueError(f"key too long: {key.decode()!r}")
        if i % BLOCK == 0:
            index += struct.pack("<I", len(data))
            data += bytes([len(key)]) + key
        else:
            shared = 0
            while shared < min(len(prev), len(key)) and prev[shared] == key[shared]:
                shared += 1
            data += bytes([shared, len(key) - shared]) + key[shared:]
        data += bytes([len(reading)]) + reading
        prev = key
    return bytes(index), bytes(data), len(index) // 4


def nfkc_tables() -> tuple[bytes, bytes, int, bytes, int, bytes, int]:
    """(dec entries, dec data, n_dec, ccc entries, n_ccc, comp entries, n_comp)."""
    dec, dec_data, ccc, comp = bytearray(), bytearray(), bytearray(), []
    n_dec = n_ccc = 0
    for cp in range(sys.maxunicode + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        if not 0xAC00 <= cp <= 0xD7A3:
            d = unicodedata.normalize("NFKD", ch)
            if d != ch:
                b = d.encode("utf-8")
                dec += struct.pack("<II", cp | len(b) << 21, len(dec_data))
                dec_data += b
                n_dec += 1
        cc = unicodedata.combining(ch)
        if cc:
            ccc += struct.pack("<I", cp | cc << 24)
            n_ccc += 1
        parts = unicodedata.decomposition(ch).split()
        if len(parts) == 2 and not parts[0].startswith("<"):
            a, b2 = (int(p, 16) for p in parts)
            if unicodedata.normalize("NFC", chr(a) + chr(b2)) == ch:
                comp.append((a, b2, cp))
    comp.sort()
    comp_b = b"".join(struct.pack("<III", *c) for c in comp)
    return bytes(dec), bytes(dec_data), n_dec, bytes(ccc), n_ccc, comp_b, len(comp)


def _align(b: bytes) -> bytes:
    return b + b"\0" * ((-len(b)) % 4)


def build_jlex() -> bytes:
    t = tables()
    sources = [t.words, *(t.after[c] for c in CONTEXTS), t.kanji]
    assert [*CONTEXTS] == ["kanji", "katakana"]
    parts: list[bytes] = []
    pos = HEADER_SIZE
    fields: list[int] = []

    def add(b: bytes) -> int:
        nonlocal pos
        off = pos
        parts.append(_align(b))
        pos += len(parts[-1])
        return off

    for table in sources:
        index, data, n_blocks = pack_table(table)
        fields += [len(table), n_blocks, add(index), add(data), len(data)]
    dec, dec_data, n_dec, ccc, n_ccc, comp, n_comp = nfkc_tables()
    fields += [n_dec, add(dec), add(dec_data), len(dec_data), n_ccc, add(ccc), n_comp, add(comp)]
    head = MAGIC + struct.pack("<HHII", VERSION, HEADER_SIZE, t.max_len, BLOCK) + struct.pack(f"<{len(fields)}I", *fields)
    assert len(head) == HEADER_SIZE, len(head)
    return head + b"".join(parts)


def read_jlex(blob: bytes) -> list[dict[str, str]]:
    """Decode the four tables back (self-check)."""
    if blob[:4] != MAGIC or struct.unpack_from("<HH", blob, 4) != (VERSION, HEADER_SIZE):
        raise ValueError("not a JLEX v1 blob")
    out = []
    for k in range(len(TABLES)):
        n, n_blocks, index_off, data_off, data_size = struct.unpack_from("<5I", blob, 16 + 20 * k)
        data = blob[data_off:data_off + data_size]
        table: dict[str, str] = {}
        for b in range(n_blocks):
            p = struct.unpack_from("<I", blob, index_off + 4 * b)[0]
            key = b""
            for e in range(min(BLOCK, n - b * BLOCK)):
                if e == 0:
                    key = data[p + 1:p + 1 + data[p]]
                    p += 1 + data[p]
                else:
                    shared, sl = data[p], data[p + 1]
                    key = key[:shared] + data[p + 2:p + 2 + sl]
                    p += 2 + sl
                rl = data[p]
                table[key.decode("utf-8")] = "".join(chr(KANA0 + c) for c in data[p + 1:p + 1 + rl])
                p += 1 + rl
        out.append(table)
    return out


def _check(blob: bytes) -> None:
    t = tables()
    want = [t.words, *(t.after[c] for c in CONTEXTS), t.kanji]
    got = read_jlex(blob)
    for name, a, b in zip(TABLES, got, want):
        assert a == b, f"table {name} does not round-trip"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    blob = build_jlex()
    _check(blob)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(blob)
    counts = [struct.unpack_from("<I", blob, 16 + 20 * k)[0] for k in range(len(TABLES))]
    sizes = [struct.unpack_from("<I", blob, 16 + 20 * k + 16)[0] for k in range(len(TABLES))]
    n_dec, _, _, dec_size, n_ccc, _, n_comp = struct.unpack_from("<7I", blob, 96)
    print(f"wrote {a.out} ({len(blob)} bytes: " + ", ".join(f"{n} {name} ({s} B)" for name, n, s in
                                                            zip(TABLES, counts, sizes))
          + f"; NFKC {n_dec} decompositions ({8 * n_dec + dec_size} B), {n_ccc} classes, {n_comp} pairs)")


if __name__ == "__main__":
    main()
