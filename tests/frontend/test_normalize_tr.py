import pytest

from vtts.frontend.tr.normalize_tr import cardinal, normalize_tr, ordinal


@pytest.mark.parametrize("n, words", [
    (0, "sıfır"), (1, "bir"), (10, "on"), (11, "on bir"), (21, "yirmi bir"), (99, "doksan dokuz"),
    (100, "yüz"), (101, "yüz bir"), (200, "iki yüz"), (1000, "bin"), (1001, "bin bir"),
    (2026, "iki bin yirmi altı"), (21000, "yirmi bir bin"), (100000, "yüz bin"),
    (1_000_000, "bir milyon"), (2_500_000, "iki milyon beş yüz bin"), (10 ** 9, "bir milyar"),
    (-7, "eksi yedi"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [
    (1, "birinci"), (2, "ikinci"), (3, "üçüncü"), (4, "dördüncü"), (6, "altıncı"), (9, "dokuzuncu"),
    (10, "onuncu"), (20, "yirminci"), (40, "kırkıncı"), (100, "yüzüncü"), (1000, "bininci"),
    (21, "yirmi birinci"),
])
def test_ordinal(n, words):
    assert ordinal(n) == words


@pytest.mark.parametrize("text, out", [
    ("İstanbul'da 2026'da 21 kişi vardı.", "istanbul'da iki bin yirmi altıda yirmi bir kişi vardı ."),
    ("Saat 14:30'da, saat 9.15'te.", "saat on dört otuzda , saat dokuz on beşte ."),
    ("19.11.2026 tarihinde", "on dokuz kasım iki bin yirmi altı tarihinde"),
    ("%25 indirim, 50% oranında.", "yüzde yirmi beş indirim , yüzde elli oranında ."),
    ("12,50 TL ve 50 ₺ ve $5.", "on iki lira elli kuruş ve elli lira ve beş dolar ."),
    ("5. sınıf ve 1'inci ve 4'üncü.", "beşinci sınıf ve birinci ve dördüncü ."),
    ("Hız 120 km/h, 25 °C, 3,5 km.",
     "hız saatte yüz yirmi kilometre , yirmi beş derece , üç virgül beş kilometre ."),
    ("0532 123 45 67 numarası", "sıfır beş üç iki bir iki üç dört beş altı yedi numarası"),
    ("THY ve NATO, ESP32 ile.", "te he ye ve nato , e se pe üç iki ile ."),
    ("Dr. Ahmet vb. kişiler.", "doktor ahmet ve benzeri kişiler ."),
    ("IŞIK ve İLK ışık.", "ışık ve ilk ışık ."),
    ("1.000.000 lira, 1999 yılı", "bir milyon lira , bin dokuz yüz doksan dokuz yılı"),
    ("sayfa 10-20 arası", "sayfa on ile yirmi arası"),
    ("Sıcaklık -5 derece.", "sıcaklık eksi beş derece ."),
    ("Rock & roll…", "rock ve roll ,"),
])
def test_normalize(text, out):
    assert normalize_tr(text) == out
