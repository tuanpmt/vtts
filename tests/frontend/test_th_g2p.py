"""Thai spelling rules (th/g2p_th.py): token set, syllables, classes, tones, finals, words."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.th.g2p_th import (
    override_table,
    parse_word,
    run_syllables,
    segment,
    silence,
    syllables_at,
    tone,
    unreadable_th,
    word_syllables,
)


def read(text):
    """'initials-vowel-final+tone' per syllable, e.g. 'khr-a-p4'."""
    return " ".join("".join(s.initials) + "-" + s.vowel + ("-" + s.final if s.final else "")
                    + str(s.tone) for s in run_syllables(text))


def tones(text):
    return [s.tone for s in run_syllables(text)]


def test_token_set_then():
    assert ps.TOKENS_THEN[:107] == ps.TOKENS_V2
    assert len(set(ps.TOKENS_THEN)) == len(ps.TOKENS_THEN) == ps.VOCAB_SIZE_THEN == 162
    assert ps.PAIR_MODES["th"] == ps.TOKEN_SET_THEN == "th-en"
    idx = ps.token_index("th-en")
    assert idx["TH:I:p"] == 107 and idx["TH:T5"] == 161
    assert [t for t in ps.TOKENS_THEN if t.startswith("TH:T")] == [f"TH:T{i}" for i in range(1, 6)]
    assert len(ps.TH_INITIALS) == 21 and len(ps.TH_VOWELS) == 21 and len(ps.TH_FINALS) == 8


def test_every_syllable_token_is_in_the_set():
    idx = ps.token_index("th-en")
    for s in run_syllables("เมื่อวานนี้ฉันไปซื้อเสื้อผ้าที่ตลาดกับเพื่อนสนิทสองคนแล้วกินก๋วยเตี๋ยว"):
        assert all(t in idx for t in s.tokens())


@pytest.mark.parametrize("word, expected", [
    # mid class: live mid, dead low; marks 1-4 give low, falling, high, rising
    ("กา", 1), ("กะ", 2), ("กาก", 2), ("ก่า", 2), ("ก้า", 3), ("ก๊า", 4), ("ก๋า", 5),
    # high class: live rising, dead low; mai ek low, mai tho falling
    ("ขา", 5), ("ขะ", 2), ("ขาก", 2), ("ข่า", 2), ("ข้า", 3),
    # low class: live mid, dead short high, dead long falling; mai ek falling, mai tho high
    ("คา", 1), ("คะ", 4), ("คาก", 3), ("ค่า", 3), ("ค้า", 4),
])
def test_tone_from_class_mark_and_syllable_type(word, expected):
    assert tones(word) == [expected]


@pytest.mark.parametrize("word, expected", [
    ("นาม", [1]), ("นาก", [3]), ("นัก", [4]), ("เด็ก", [2]), ("เล็ก", [4]), ("ชอบ", [3]),
    ("ไม่", [3]), ("น้ำ", [4]), ("ใหม่", [2]), ("ไหน", [5]), ("ของ", [5]), ("หรือ", [5]),
])
def test_live_and_dead_syllables(word, expected):
    assert tones(word) == expected


def test_tone_table():
    assert tone("M", "", True, False) == 1 and tone("H", "", True, False) == 5
    assert tone("L", "", False, True) == 4 and tone("L", "", False, False) == 3
    assert tone("L", "่", True, False) == 3 and tone("H", "้", True, False) == 3


@pytest.mark.parametrize("word, expected", [
    ("สนุก", "s-a2 n-u-k2"),        # ส leads น: high-class tone
    ("หนังสือ", "n-a-ng5 s-uue5"),   # ห leads น (silent ห)
    ("ขนม", "kh-a2 n-o-m5"),
    ("อร่อย", "?-a2 r-oor-j2"),      # mid-class leader
    ("ถนน", "th-a2 n-o-n5"),
    ("สบาย", "s-a2 b-aa-j1"),        # บ is not a sonorant: no leading
    ("เสมอ", "s-a2 m-ooe5"),         # preposed vowel before a leading consonant
    ("แสดง", "s-a2 d-aae-ng1"),
    ("เฉพาะ", "ch-a2 ph-or4"),
])
def test_unwritten_vowels_and_leading_consonants(word, expected):
    assert read(word) == expected


@pytest.mark.parametrize("word, expected", [
    ("ปลา", "pl-aa1"), ("ความ", "khw-aa-m1"), ("ครับ", "khr-a-p4"), ("เพลง", "phl-ee-ng1"),
    ("จริง", "c-i-ng1"), ("ทราย", "s-aa-j1"), ("สร้าง", "s-aa-ng3"), ("ศรี", "s-ii5"),
])
def test_clusters_and_silent_r(word, expected):
    assert read(word) == expected


@pytest.mark.parametrize("word, final", [
    ("บาท", "t"), ("รถ", "t"), ("กาส", "t"), ("ราช", "t"), ("โชค", "k"), ("เลข", "k"),
    ("ภาพ", "p"), ("ลาภ", "p"), ("คุณ", "n"), ("การ", "n"), ("กาล", "n"), ("กาญ", "n"),
    ("ลม", "m"), ("ทาง", "ng"), ("ขาว", "w"), ("สาย", "j"),
])
def test_finals_collapse_to_six_sounds_and_glides(word, final):
    assert parse_word(word)[-1].final == final


@pytest.mark.parametrize("word, expected", [
    ("เรือ", "r-uea1"), ("เมีย", "m-ia1"), ("ตัว", "t-ua1"), ("ขวด", "kh-ua-t2"),
    ("เกาะ", "k-or2"), ("เดิน", "d-ooe-n1"), ("เลย", "l-ooe-j1"), ("ทำ", "th-a-m1"),
    ("เขา", "kh-a-w5"), ("ไทย", "th-a-j1"), ("คน", "kh-o-n1"), ("นคร", "n-a4 kh-oor-n1"),
    ("กรรม", "k-a-m1"), ("ฤดู", "r-ue4 d-uu1"), ("อังกฤษ", "?-a-ng1 kr-i-t2"),
])
def test_vowels(word, expected):
    assert read(word) == expected


@pytest.mark.parametrize("word, silent", [
    ("จันทร์", "จัน"), ("ศาสตร์", "ศาส"), ("สัตว์", "สัต"), ("อาจารย์", "อาจาร"), ("องค์", "อง"),
    ("ฤทธิ์", "ฤท"), ("พันธุ์", "พัน"), ("บุตร", "บุต"), ("เมตร", "เมต"),
])
def test_silent_letters(word, silent):
    assert silence(word) == silent


def test_repetition_mark_repeats_the_word():
    assert read("เด็กๆ") == "d-e-k2 d-e-k2"
    assert read("ช้าๆ") == read("ช้าช้า")


def test_segmentation_of_common_phrases():
    assert segment("วันนี้อากาศดีมาก") == ["วันนี้", "อากาศ", "ดี", "มาก"]
    assert segment("ประเทศไทย") == ["ประเทศ", "ไทย"]
    assert segment("ขอบคุณมากค่ะ") == ["ขอบคุณ", "มาก", "ค่ะ"]
    assert segment("ไปโรงเรียน") == ["ไป", "โรงเรียน"]
    assert read("สวัสดีครับ") == "s-a2 w-a-t2 d-ii1 khr-a-p4"


def test_text_outside_the_word_list_is_read_together():
    words = frozenset(["ไป"])
    assert segment("ไปสนุก", words) == ["ไป", "สนุก"]  # one unknown piece: leading rule kept


def test_overrides_are_single_syllable_respellings():
    table = override_table()
    assert len(table) >= 50
    for word, pieces in table.items():
        for p in pieces:
            assert any(j == len(p) and len(s) == 1 for j, s, _ in syllables_at(p, 0)), (word, p)
    assert [s.vowel for s in word_syllables("ได้")] == ["aa"]
    assert read("บริษัท") == "b-oor1 r-i4 s-a-t2"
    assert read("ราชการ") == "r-aa-t3 ch-a4 k-aa-n1"


def test_unreadable_letters():
    assert unreadable_th("สวัสดี Москва") == list("Москва")
    assert unreadable_th("สวัสดี Café ๑๒ บาท") == []
