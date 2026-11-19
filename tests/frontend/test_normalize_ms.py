import pytest

from vtts.frontend.ms.normalize_ms import cardinal, normalize_ms, ordinal


@pytest.mark.parametrize("n, words", [
    (0, "sifar"), (1, "satu"), (8, "lapan"), (10, "sepuluh"), (11, "sebelas"), (12, "dua belas"),
    (18, "lapan belas"), (20, "dua puluh"), (28, "dua puluh lapan"), (100, "seratus"),
    (115, "seratus lima belas"), (1000, "seribu"), (2026, "dua ribu dua puluh enam"),
    (11000, "sebelas ribu"), (1_000_000, "sejuta"), (1_500_000, "sejuta lima ratus ribu"),
    (2_500_000, "dua juta lima ratus ribu"), (10 ** 9, "satu bilion"), (10 ** 12, "satu trilion"),
    (-7, "negatif tujuh"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [(1, "pertama"), (2, "kedua"), (8, "kelapan"),
                                      (21, "kedua puluh satu")])
def test_ordinal(n, words):
    assert ordinal(n) == words


@pytest.mark.parametrize("text, out", [
    ("Apa khabar?", "apa khabar ?"),
    # numbers: Malaysian marks (comma for thousands, point for decimals)
    ("Ada 21 orang dan 1,250 kerusi.", "ada dua puluh satu orang dan seribu dua ratus lima puluh kerusi ."),
    ("1.000.000 penduduk", "sejuta penduduk"),
    ("nilai 3.14 atau 0.5", "nilai tiga perpuluhan satu empat atau sifar perpuluhan lima"),
    ("-5 darjah", "negatif lima darjah"),
    ("10-20 orang", "sepuluh hingga dua puluh orang"),
    # dates and times
    ("Tarikh 31/08/1957.", "tarikh tiga puluh satu ogos seribu sembilan ratus lima puluh tujuh ."),
    ("2026-11-19", "sembilan belas november dua ribu dua puluh enam"),
    ("19 Nov 2026", "sembilan belas november dua ribu dua puluh enam"),
    ("pada 1 Mac", "pada satu mac"),
    ("pukul 8.30 pagi", "pukul lapan tiga puluh minit pagi"),
    ("3.45 petang", "tiga empat puluh lima minit petang"),
    ("jam 07:00", "jam tujuh"),
    # money, percent, units
    ("Harganya RM12.50.", "harganya dua belas ringgit lima puluh sen ."),
    ("RM0.50", "lima puluh sen"),
    ("RM 1.5 juta", "satu perpuluhan lima juta ringgit"),
    ("RM450,000", "empat ratus lima puluh ribu ringgit"),
    ("80 sen", "lapan puluh sen"),
    ("US$20", "dua puluh dolar amerika"),
    ("Diskaun 15%.", "diskaun lima belas peratus ."),
    ("Jaraknya 5 km, suhu 30 °C.", "jaraknya lima kilometer , suhu tiga puluh darjah selsius ."),
    ("90 km/j", "sembilan puluh kilometer sejam"),
    # ordinals, phone numbers, reduplication
    ("Johan ke-1 dan ke-3.", "johan pertama dan ketiga ."),
    ("Telefon 012-345 6789.", "telefon kosong satu dua tiga empat lima enam tujuh lapan sembilan ."),
    ("+60 12 345 6789", "tambah enam kosong satu dua tiga empat lima enam tujuh lapan sembilan"),
    ("budak2 bermain", "budak budak bermain"),
    # codes, acronyms, abbreviations, symbols
    ("KTM dan LRT", "ké ti ém dan él ar ti"),
    ("ESP32-P4", "i és pi tiga dua pi empat"),
    ("parti UMNO", "parti umno"),
    ("Jln. Ampang No. 5", "jalan ampang nombor lima"),
    ("En. Ali dan Pn. Siti", "encik ali dan puan siti"),
    ("Syarikat ABC Sdn. Bhd.", "syarikat éi bi si sendirian berhad ."),
    ("buah, sayur, dll.", "buah , sayur , dan lain lain ."),
    ("yg penting", "yang penting"),
    ("Ali & Abu", "ali dan abu"),
])
def test_normalize_ms(text, out):
    assert normalize_ms(text) == out


def test_no_digits_left():
    for text in ["1", "123456789012345678", "3.5%", "ke-2", "10:00", "99 km", "RM0.5", "anak2",
                 "1,234,567.89", "8.30 pagi"]:
        assert not any(ch.isdigit() for ch in normalize_ms(text)), text


def test_no_raise_on_mixed_marks_and_month_lookalikes():
    """A comma group before several points reads the integer part without the commas; a month
    matched by re.IGNORECASE whose lower() is not a key (ſep, İ) is left as written."""
    assert normalize_ms("1,500.300.200") == ("seribu lima ratus perpuluhan tiga kosong kosong dua kosong "
                                             "kosong")
    assert normalize_ms("5 ſep 2020").startswith("lima ſep")
    assert normalize_ms("5 Kok 2020") == "lima kok dua ribu dua puluh"
