import pytest

from vtts.frontend.id.normalize_id import cardinal, normalize_id, ordinal


@pytest.mark.parametrize("n, words", [
    (0, "nol"), (1, "satu"), (10, "sepuluh"), (11, "sebelas"), (12, "dua belas"),
    (19, "sembilan belas"), (20, "dua puluh"), (21, "dua puluh satu"), (100, "seratus"),
    (115, "seratus lima belas"), (250, "dua ratus lima puluh"), (1000, "seribu"),
    (1001, "seribu satu"), (2026, "dua ribu dua puluh enam"), (11000, "sebelas ribu"),
    (100_000, "seratus ribu"), (1_000_000, "satu juta"), (2_500_000, "dua juta lima ratus ribu"),
    (1_000_000_000, "satu miliar"), (10 ** 12, "satu triliun"), (-7, "minus tujuh"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [(1, "pertama"), (2, "kedua"), (3, "ketiga"),
                                      (10, "kesepuluh"), (21, "kedua puluh satu")])
def test_ordinal(n, words):
    assert ordinal(n) == words


@pytest.mark.parametrize("text, out", [
    ("Apa kabar?", "apa kabar ?"),
    # numbers
    ("Ada 21 orang dan 1.250 kursi.", "ada dua puluh satu orang dan seribu dua ratus lima puluh kursi ."),
    ("2.000.000 penduduk", "dua juta penduduk"),
    ("nilai 3,5 atau 2.75", "nilai tiga koma lima atau dua titik tujuh puluh lima"),
    ("-5 derajat", "minus lima derajat"),
    ("10-20 orang", "sepuluh sampai dua puluh orang"),
    # dates and times
    ("Tanggal 17/08/1945.", "tanggal tujuh belas agustus seribu sembilan ratus empat puluh lima ."),
    ("2026-11-18", "delapan belas november dua ribu dua puluh enam"),
    ("Pukul 14.30 WIB", "pukul empat belas lewat tiga puluh menit wé i bé"),
    ("jam 07:00 pagi", "jam tujuh pagi"),
    ("pukul 9:05", "pukul sembilan lewat lima menit"),
    # money, percent, units
    ("Harganya Rp50.000.", "harganya lima puluh ribu rupiah ."),
    ("Rp 1,5 juta", "satu koma lima juta rupiah"),
    ("$20", "dua puluh dolar"),
    ("Diskon 15%.", "diskon lima belas persen ."),
    ("Jaraknya 5 km, suhu 30 °C.", "jaraknya lima kilometer , suhu tiga puluh derajat celsius ."),
    ("80 km/jam", "delapan puluh kilometer per jam"),
    # ordinals, phone numbers, reduplication
    ("Juara ke-1 dan ke-3.", "juara pertama dan ketiga ."),
    ("Telepon 0812-3456-7890.", "telepon nol delapan satu dua tiga empat lima enam tujuh delapan sembilan nol ."),
    ("+62 812 3456 7890", "plus enam dua delapan satu dua tiga empat lima enam tujuh delapan sembilan nol"),
    ("Anak2 bermain.", "anak anak bermain ."),
    ("anak-anak", "anak anak"),
    # codes, acronyms, abbreviations, symbols
    ("KTP dan SIM", "ka té pé dan sim"),
    ("ESP32-P4", "é és pé tiga dua pé empat"),
    ("negara ASEAN", "negara asean"),
    ("buah, sayur, dll.", "buah , sayur , dan lain lain ."),
    ("Jl. Sudirman No. 5", "jalan sudirman nomor lima"),
    ("yg penting", "yang penting"),
    ("Budi & Ani", "budi dan ani"),
    ("Dia bilang… nanti", "dia bilang , nanti"),
    ("“Halo” (katanya)", "halo katanya"),
])
def test_normalize_id(text, out):
    assert normalize_id(text) == out


def test_no_digits_left():
    for text in ["1", "123456789012345678", "3,5%", "ke-2", "10:00", "99 km", "Rp0,5", "anak2"]:
        assert not any(ch.isdigit() for ch in normalize_id(text)), text
