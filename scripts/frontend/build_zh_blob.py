"""Build the ZLEX blob (Mandarin reading tables) for the device front-end.

Usage: uv run python scripts/frontend/build_zh_blob.py --out zh_lex.bin

Source: the same tables the Python front-end reads, src/vtts/frontend/lexicons/zh/chars.tsv and
phrases.tsv (overrides.tsv is already folded into both by scripts/frontend/build_zh_lexicon.py).
The C reader (runtime/src/vtts_text_zh.c, vtts_zlex_init) reads the blob in place: no malloc,
no copies, so it can be mapped straight from flash.

Format ZLEX version 1, little-endian, every table 4-byte aligned:

  Header (48 bytes):
    magic "ZLEX", version u16 = 1, header size u16 = 48,
    n_syl u32, n_chars u32, n_phr2 u32, n_phr3 u32, n_phr4 u32,
    syl_off u32, chars_off u32, phr2_off u32, phr3_off u32, phr4_off u32.
  Syllables (at syl_off): n_syl entries of 4 bytes [initial u8][final u8][tone u8][0], where
    initial is 0 (none) or 1 + its index in ZH_INITIALS, final is its index in ZH_FINALS and tone
    is 1..5 (5 = neutral), all from vtts.frontend.phoneme_set. The tokens of a syllable are
    [ZI:initial] ZF:final ZTtone, exactly pinyin.syllable_tokens of its numbered pinyin.
  Characters (at chars_off): n_chars keys u16 (code point - 0x4E00, ascending), then n_chars
    syllable indices u16 in the same order: the default reading of each character of chars.tsv.
  Phrases of length L = 2, 3, 4 (at phrL_off): n_phrL records of 4L bytes sorted by key:
    L keys u16 (code point - 0x4E00) then L syllable indices u16 (one per character, in order).
    Records compare as sequences of u16 keys (= code point order), so a reader finds a phrase
    by binary search. A syllable index 0xFFFF would mean "no reading" (never produced: the
    builder rejects invalid syllables).

Readings are resolved like g2p_zh.read_han: forward maximum matching over the phrases (4, 3,
then 2 characters), else the character's default, else the character is skipped.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from vtts.frontend.phoneme_set import ZH_FINALS, ZH_INITIALS
from vtts.frontend.zh.g2p_zh import MAX_PHRASE, char_table, phrase_table
from vtts.frontend.zh.pinyin import split_syllable, syllable_tokens

MAGIC, VERSION = b"ZLEX", 1
HEADER = struct.Struct("<4sHHIIIIIIIIII")
BASE = 0x4E00
NO_READING = 0xFFFF


def syllable_entry(syl: str) -> tuple[int, int, int]:
    """(initial + 1 or 0, final index, tone) of a numbered pinyin syllable."""
    parts = split_syllable(syl[:-1])
    if parts is None or syl[-1] not in "12345" or not syllable_tokens(syl):
        raise ValueError(f"invalid syllable {syl!r}")
    ini, fin = parts
    return (ZH_INITIALS.index(ini) + 1 if ini else 0, ZH_FINALS.index(fin), int(syl[-1]))


def _key(ch: str) -> int:
    k = ord(ch) - BASE
    if not 0 <= k <= 0x51FF:
        raise ValueError(f"character outside U+4E00..U+9FFF: {ch!r}")
    return k


def build_zlex() -> bytes:
    chars, phrases = char_table(), phrase_table()
    entries = sorted({syllable_entry(s) for s in chars.values()}
                     | {syllable_entry(s) for r in phrases.values() for s in r})
    sid = {e: i for i, e in enumerate(entries)}

    def idx(syl: str) -> int:
        return sid[syllable_entry(syl)]

    syl_blob = b"".join(struct.pack("<BBBB", i, f, t, 0) for i, f, t in entries)
    keys = sorted(chars, key=ord)
    char_blob = struct.pack(f"<{len(keys)}H", *map(_key, keys))
    char_blob += struct.pack(f"<{len(keys)}H", *(idx(chars[k]) for k in keys))
    phr_blobs, counts = [], []
    for n in range(2, MAX_PHRASE + 1):
        rows = sorted((tuple(map(_key, k)), tuple(idx(s) for s in r))
                      for k, r in phrases.items() if len(k) == n)
        for k, r in rows:
            if len(r) != n:
                raise ValueError(f"phrase reading length differs from its key: {k}")
        phr_blobs.append(b"".join(struct.pack(f"<{2 * n}H", *k, *r) for k, r in rows))
        counts.append(len(rows))
    offs, pos = [], HEADER.size
    for part in [syl_blob, char_blob, *phr_blobs]:
        offs.append(pos)
        pos += len(part) + (-len(part)) % 4
    head = HEADER.pack(MAGIC, VERSION, HEADER.size, len(entries), len(keys), *counts, *offs)
    out = bytearray(head)
    for part in [syl_blob, char_blob, *phr_blobs]:
        out += part + b"\0" * ((-len(part)) % 4)
    return bytes(out)


def read_zlex(blob: bytes) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Decode a blob back into (chars, phrases) tables of numbered pinyin (self-check)."""
    magic, ver, hsize, n_syl, n_chars, *rest = HEADER.unpack_from(blob)
    counts, offs = rest[:3], rest[3:]
    if magic != MAGIC or ver != VERSION or hsize != HEADER.size:
        raise ValueError("not a ZLEX v1 blob")
    syls = []
    for i in range(n_syl):
        ini, fin, tone, _ = struct.unpack_from("<BBBB", blob, offs[0] + 4 * i)
        syls.append((ZH_INITIALS[ini - 1] if ini else "", ZH_FINALS[fin], tone))
    keys = struct.unpack_from(f"<{n_chars}H", blob, offs[1])
    vals = struct.unpack_from(f"<{n_chars}H", blob, offs[1] + 2 * n_chars)
    chars = {chr(BASE + k): syls[v] for k, v in zip(keys, vals)}
    phrases = {}
    for n, cnt, off in zip(range(2, MAX_PHRASE + 1), counts, offs[2:]):
        for r in range(cnt):
            rec = struct.unpack_from(f"<{2 * n}H", blob, off + 4 * n * r)
            phrases["".join(chr(BASE + k) for k in rec[:n])] = tuple(syls[v] for v in rec[n:])
    return chars, phrases


def _check(blob: bytes) -> None:
    def tokens(s):
        ini, fin, tone = s
        return ([f"ZI:{ini}"] if ini else []) + [f"ZF:{fin}", f"ZT{tone}"]

    chars, phrases = read_zlex(blob)
    want_c, want_p = char_table(), phrase_table()
    assert chars.keys() == want_c.keys() and phrases.keys() == want_p.keys()
    assert all(tokens(chars[k]) == syllable_tokens(v) for k, v in want_c.items())
    assert all([tokens(s) for s in phrases[k]] == [syllable_tokens(s) for s in v]
               for k, v in want_p.items())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    blob = build_zlex()
    _check(blob)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(blob)
    _, _, _, n_syl, n_chars, p2, p3, p4, *_ = HEADER.unpack_from(blob)
    print(f"wrote {a.out} ({len(blob)} bytes: {n_syl} syllables, {n_chars} characters, "
          f"{p2 + p3 + p4} phrases)")


if __name__ == "__main__":
    main()
