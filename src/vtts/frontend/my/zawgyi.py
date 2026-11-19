"""Zawgyi detection and conversion to Unicode, and the canonical order of Burmese marks.

Much Burmese text was typed with the Zawgyi font encoding, which reuses Myanmar code points for
glyph shapes and stores the vowel sign ေ and the medial ြ before their consonant. Both functions
are table-driven (the C port follows them):

- is_zawgyi(text): signals that only Zawgyi text has (code points U+1033 U+1034 and U+105A-U+1097,
  which Burmese Unicode text does not use; ေ or the Zawgyi medial ra written before a consonant;
  the Zawgyi asat U+1039 not followed by a consonant) against signals of Unicode text (U+103E,
  U+103F, Unicode kinzi င်္, ၎င်း); Zawgyi when its signals outnumber the Unicode ones.
- zawgyi_to_unicode(text): every Zawgyi code point is mapped to its Unicode sequence (ZG_MAP);
  marks written before a consonant (ေ, medial ra) move after it, kinzi written after its
  consonant moves before it, and each cluster is put in canonical order (canonical_order).

canonical_order(text) also cleans Unicode text: within each cluster (a consonant or independent
vowel and the marks after it) the marks are sorted in the storage order of Unicode Technical Note
11 (stacked consonant, medials ျ ြ ွ ှ, ေ, upper vowels, lower vowels, ါ ာ, ံ, ့, ်, း).
"""

from __future__ import annotations

CONSONANTS = frozenset(chr(c) for c in range(0x1000, 0x1022)) | {"ဥ", "ဧ", "ဩ", "ဿ"}
INDEPENDENT = frozenset("\u1023\u1024\u1026\u102a")
VIRAMA, ASAT, KINZI = "္", "်", "င်္"
# Storage rank of each mark inside a cluster (UTN #11); a stacked consonant (virama + consonant)
# has rank 1 and keeps its consonant.
RANK = {"ျ": 2, "ြ": 3, "ွ": 4, "ှ": 5, "ေ": 6, "ိ": 7, "ီ": 7,
        "ဲ": 7, "ု": 8, "ူ": 8, "ါ": 9, "ာ": 9, "ံ": 10, "့": 11,
        "်": 12, "း": 13}

# Zawgyi code point -> Unicode sequence. "<" marks a sign written before its consonant (moved
# after it), ">" kinzi written after its consonant (moved before it, with the vowel that follows).
ZG_MAP = {
    "ဳ": "ု", "ဴ": "ူ", "္": "်", "်": "ျ",
    "ျ": "<ြ", "ြ": "ွ", "ွ": "ှ", "ၚ": "ါ်",
    "ၠ": "္က", "ၡ": "္ခ", "ၢ": "္ဂ",
    "ၣ": "္ဃ", "ၤ": ">", "ၥ": "္စ", "ၦ": "္ဆ",
    "ၧ": "္ဆ", "ၨ": "္ဇ", "ၩ": "္ဈ",
    "ၪ": "ဉ", "ၫ": "ည", "ၬ": "္ဋ", "ၭ": "္ဌ",
    "ၮ": "ဍ္ဍ", "ၯ": "ဍ္ဎ", "ၰ": "္ဏ",
    "ၱ": "္တ", "ၲ": "္တ", "ၳ": "္ထ",
    "ၴ": "္ထ", "ၵ": "္ဒ", "ၶ": "္ဓ",
    "ၷ": "္န", "ၸ": "္ပ", "ၹ": "္ဖ",
    "ၺ": "္ဗ", "ၻ": "္ဘ", "ၼ": "္မ",
    "ၽ": "ျ", "ၾ": "<ြ", "ၿ": "<ြ", "ႀ": "<ြ",
    "ႁ": "<ြ", "ႂ": "<ြ", "ႃ": "<ြ", "ႄ": "<ြ",
    "ႅ": "္လ", "ႆ": "ဿ", "ႇ": "ှ", "ႈ": "ှု",
    "ႉ": "ှူ", "ႊ": "ွှ", "ႋ": ">ိ", "ႌ": ">ီ",
    "ႍ": ">ံ", "ႎ": "ိံ", "ႏ": "န", "႐": "ရ",
    "႑": "ဏ္ဍ", "႒": "ဋ္ဌ", "႓": "္ဘ",
    "႔": "့", "႕": "့", "႖": "္တွ",
    "႗": "ဋ္ဋ", "ေ": "<ေ",
}


def _is_mark(ch: str) -> bool:
    return ch in RANK or ch == VIRAMA


def canonical_order(text: str) -> str:
    """Marks of every cluster in storage order (a repeated mark is dropped, a virama before no
    consonant too); kinzi stays before its consonant; ဥ + ် ာ ္ is ဉ, ဥ + ီ is ဦ, စ + ျ is ဈ (also
    stacked). Text outside clusters is unchanged."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith(KINZI, i) and i + 3 < n and text[i + 3] in CONSONANTS:
            out.append(KINZI)
            i += 3
            continue
        if ch not in CONSONANTS and ch not in INDEPENDENT:
            out.append(ch)
            i += 1
            continue
        j = i + 1
        marks: list[tuple[int, int, int, str]] = []  # (segment, rank, position, mark)
        seg = 0  # marks after an asat stay after it (ကျွန်ုပ်, ယောက်ျား)
        while j < n:
            x = text[j]
            if x == VIRAMA and j + 1 < n and text[j + 1] in CONSONANTS:
                marks.append((seg, 1, len(marks), x + text[j + 1]))
                j += 2
            elif x in RANK:
                if all(m != x for _, _, _, m in marks):
                    # ့ right after ် goes before it (Zawgyi typing order)
                    back = int(x == "့" and bool(marks) and marks[-1][3] == ASAT)
                    marks.append((seg - back, RANK[x], len(marks), x))
                    seg += x == ASAT
                j += 1
            elif x == VIRAMA:
                j += 1
            else:
                break
        marks.sort()
        body = "".join(m for _, _, _, m in marks)
        body = body.replace("\u1039\u1005\u103b", "\u1039\u1008")
        if ch == "\u1025" and body[:1] in (ASAT, "\u102c", VIRAMA):
            ch = "\u1009"
        elif ch == "\u1025" and body.startswith("\u102e"):
            ch, body = "\u1026", body[1:]
        elif ch == "\u1005" and body.startswith("\u103b"):
            ch, body = "\u1008", body[1:]
        out.append(ch + body)
        i = j
    return "".join(out)


def is_zawgyi(text: str) -> bool:
    """Whether text (Myanmar script) is in the Zawgyi encoding."""
    zg = uni = 0
    prev = ""
    for k, ch in enumerate(text):
        o = ord(ch)
        nxt = text[k + 1] if k + 1 < len(text) else ""
        if o in (0x1033, 0x1034) or 0x105A <= o <= 0x1097:
            zg += 1
        elif ch in ("ေ", "ျ") and nxt in CONSONANTS and not (prev in CONSONANTS or _is_mark(prev)):
            zg += 1  # ေ / Zawgyi ra before its consonant
        elif ch == VIRAMA and nxt not in CONSONANTS:
            zg += 1  # Zawgyi asat
        elif ch in ("ှ", "ဿ"):
            uni += 1
        elif ch == VIRAMA and prev == ASAT and k >= 2 and text[k - 2] == "င":
            uni += 1  # Unicode kinzi
        elif ch == "၎" and nxt == "င":
            uni += 1
        prev = ch
    return zg > uni


def zawgyi_to_unicode(text: str) -> str:
    """Zawgyi text in Unicode (see the module docstring). Also: ၀ between non-digits is ဝ, ၄ before
    င is ၎, a lone ၎ is ၎င်း, a space before ့ is dropped."""
    out: list[str] = []
    pre = ""            # marks written before the next consonant (ေ, medial ra)
    cur: list[str] | None = None  # the current cluster: [kinzi, base, marks]
    n = len(text)

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            out.append(canonical_order(cur[0] + cur[1] + cur[2]))
            cur = None

    for k, ch in enumerate(text):
        prv = text[k - 1] if k else ""
        nxt = text[k + 1] if k + 1 < n else ""
        if ch == "\u1040" and not ("\u1040" <= prv <= "\u1049") and not ("\u1040" <= nxt <= "\u1049"):
            ch = "\u101d"  # zero written for wa
        elif ch == "\u1044" and nxt == "\u1004":
            ch = "\u104e"
        elif ch == " " and nxt in ("\u1037", "\u1094", "\u1095") and cur is not None:
            continue
        m = ZG_MAP.get(ch, ch)
        if ch == "\u104e" and nxt != "\u1004":
            m = "\u104e\u1004\u103a\u1038"
        if m.startswith("<"):
            flush()
            pre += m[1:]
            continue
        if m.startswith(">"):
            if cur is not None:
                cur[0] = KINZI
                cur[2] += m[1:]
            continue
        if m[0] in CONSONANTS or m[0] in INDEPENDENT:
            flush()
            cur = ["", m[0], pre + m[1:]]
            pre = ""
            continue
        if cur is not None and all(_is_mark(c) or c in CONSONANTS for c in m):
            cur[2] += m
            continue
        flush()
        out.append(pre + m)
        pre = ""
    flush()
    out.append(pre)
    return "".join(out)


def to_unicode(text: str) -> str:
    """Burmese text in Unicode canonical order (converted from Zawgyi when it is Zawgyi)."""
    if is_zawgyi(text):
        return zawgyi_to_unicode(text)
    return canonical_order(text)
