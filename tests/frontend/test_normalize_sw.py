import pytest

from vtts.frontend.sw.normalize_sw import cardinal, normalize_sw


@pytest.mark.parametrize("n, words", [
    (0, "sifuri"), (1, "moja"), (10, "kumi"), (11, "kumi na moja"), (21, "ishirini na moja"),
    (99, "tisini na tisa"), (100, "mia moja"), (101, "mia moja na moja"), (120, "mia moja ishirini"),
    (125, "mia moja ishirini na tano"), (1000, "elfu moja"), (1001, "elfu moja na moja"),
    (1250, "elfu moja mia mbili hamsini"), (2026, "elfu mbili na ishirini na sita"),
    (25_000, "elfu ishirini na tano"), (100_000, "laki moja"),
    (250_000, "laki mbili na elfu hamsini"), (1_000_000, "milioni moja"),
    (3_500_000, "milioni tatu laki tano"), (10 ** 9, "bilioni moja"), (-7, "hasi saba"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("text, out", [
    ("Habari yako?", "habari yako ?"),
    # numbers, decimals, ranges
    ("Watu 21 walifika.", "watu ishirini na moja walifika ."),
    ("3.14 na 1,250", "tatu nukta moja nne na elfu moja mia mbili hamsini"),
    ("-5", "hasi tano"), ("10-20", "kumi hadi ishirini"),
    # money, percent, units: the word comes first
    ("Bei ni TSh 5,000.", "bei ni shilingi elfu tano ."), ("5,000/=", "shilingi elfu tano"),
    ("KSh 1,500.50", "shilingi elfu moja mia tano na senti hamsini"), ("$20", "dola ishirini"),
    ("15%", "asilimia kumi na tano"), ("asilimia 75%", "asilimia sabini na tano"),
    ("5 km", "kilomita tano"), ("25°C", "nyuzi joto ishirini na tano"), ("kg 2", "kilo mbili"), ("km 190", "kilomita mia moja tisini"),
    # times are not converted to Swahili time
    ("14:30", "saa kumi na nne na nusu"), ("saa 9:15", "saa tisa na robo"),
    ("saa 3:05 asubuhi", "saa tatu na dakika tano asubuhi"), ("7:00", "saa saba"),
    # dates (day first), ordinals
    ("19/11/2026", "tarehe kumi na tisa novemba elfu mbili na ishirini na sita"),
    ("tarehe 1/1/2000", "tarehe moja januari elfu mbili"),
    ("wa 1 na ya 2", "wa kwanza na ya pili"), ("nafasi ya 3", "nafasi ya tatu"),
    # phone numbers
    ("0712 345 678", "sifuri saba moja mbili tatu nne tano sita saba nane"),
    # codes, acronyms, abbreviations, apostrophes
    ("CCM na TANESCO", "si si em na tanesco"), ("ESP32-P4", "i es pi tatu mbili pi nne"),
    ("Bw. Juma na Bi. Amina", "bwana juma na bibi amina"), ("vitabu, kalamu, n.k.", "vitabu , kalamu , na kadhalika ."),
    ("ng’ombe", "ng'ombe"), ("Juma & Amina", "juma na amina"),
])
def test_normalize_sw(text, out):
    assert normalize_sw(text) == out


def test_no_digits_left():
    for text in ["1", "123456789012345678", "3.5%", "wa 2", "10:00", "99 km", "TSh0.50", "1,234,567.89"]:
        assert not any(ch.isdigit() for ch in normalize_sw(text)), text


def test_numbers_with_both_marks_do_not_raise():
    # read like the C front-end: commas group the integer part, marks in the decimals are skipped
    assert normalize_sw("1.234,5") == "moja nukta mbili tatu nne tano"
    assert normalize_sw("21,234.531,234.5").startswith("elfu ishirini na moja mia mbili thelathini na nne nukta")
