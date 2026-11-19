import pytest

from vtts.frontend.lo.g2p_lo import (
    lao_syllable_tokens,
    parse_word,
    prepare,
    run_syllables,
    segment,
    tone,
    unreadable_lo,
    word_set,
)
from vtts.frontend.phoneme_set import TOKENS_LOEN


def syl(text):
    return " | ".join(" ".join(t.split(":")[-1] if not t.startswith("LO:T") else t[3:] for t in s)
                      for s in lao_syllable_tokens(text))


@pytest.mark.parametrize("word, reading", [
    ("ສະບາຍດີ", "s a T6 | b aa j T1 | d ii T1"),
    ("ຂອບໃຈ", "kh oor p T4 | c a j T1"),
    ("ຄວາມ", "kh w aa m T2"),       # cluster ຄວ
    ("ກວ່າ", "k w aa T3"),
    ("ສວນ", "s ua n T1"),            # -ວ- is the vowel ua
    ("ໜຶ່ງ", "n ue ng T3"),          # ໜ = ຫນ: high class
    ("ຫຼາຍ", "l aa j T1"),           # ຫຼ
    ("ເຂົ້າ", "kh a w T4"),
    ("ພໍ່", "ph oor T3"),
    ("ນ້ຳ", "n a m T5"),
    ("ນ້ໍາ", "n a m T5"),            # ໍ + າ written apart
    ("ຄົນ", "kh o n T2"),
    ("ເມືອງ", "m uea ng T2"),
    ("ຂຽນ", "kh ia n T1"),
    ("ເດັກ", "d e k T6"),
    ("ລົດ", "l o t T3"),
    ("ຕົວ", "t ua T1"),
])
def test_readings(word, reading):
    assert syl(word) == reading


def test_tone_table():
    # live, no mark: high/middle low rising, low high rising
    assert tone("H", "", True, False) == tone("M", "", True, False) == 1 and tone("L", "", True, False) == 2
    # dead short: high/middle mid rising, low mid; dead long: high low falling, middle/low high falling
    assert tone("H", "", False, True) == tone("M", "", False, True) == 6 and tone("L", "", False, True) == 3
    assert tone("H", "", False, False) == 4 and tone("M", "", False, False) == tone("L", "", False, False) == 5
    # mai ek: mid; mai tho: high class low falling, others high falling
    assert {tone(c, "່", True, False) for c in "HML"} == {3}
    assert tone("H", "້", True, False) == 4 and tone("L", "້", True, False) == tone("M", "້", True, False) == 5


def test_repeat_mark_repeats_the_word():
    assert syl("ໄວໆ") == "w a j T2 | w a j T2"
    reps = run_syllables("ທຸກໆມື້")
    assert len(reps) == 3 and reps[0] == reps[1]


def test_prepare_and_cancel_mark():
    assert prepare("ໜ້າ") == "ຫນ້າ" and prepare("ນ້ໍາ") == "ນ້ຳ"
    assert len(parse_word("ກອລ໌ຟ")) == 1  # golf: ລ under ໌ is silent


def test_word_list_and_segmentation():
    assert len(word_set()) > 5000
    run = prepare("ຂ້ອຍກິນເຂົ້າໜຽວຢູ່ຕະຫຼາດເຊົ້າ")
    pieces = segment(run)
    assert "".join(pieces) == run and len(pieces) >= 4 and "ປະເທດລາວ" in word_set()


def test_tokens_in_set_and_unreadable():
    valid = set(TOKENS_LOEN)
    for s in lao_syllable_tokens("ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ"):
        assert set(s) <= valid
    assert unreadable_lo("ສະບາຍດີ Café") == [] and unreadable_lo("Москва") == list("Москва")
