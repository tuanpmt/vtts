import pytest

from vtts.frontend.no.normalize_no import cardinal, normalize_no, ordinal, year


@pytest.mark.parametrize("n, words", [
    (0, "null"), (1, "en"), (7, "sju"), (13, "tretten"), (20, "tjue"), (21, "tjueen"), (99, "nittini"),
    (100, "hundre"), (105, "hundre og fem"), (250, "to hundre og femti"), (1000, "tusen"),
    (1250, "tusen to hundre og femti"), (2026, "to tusen og tjueseks"), (1_000_000, "en million"),
    (2_500_000, "to millioner fem hundre tusen"), (3_000_000_000, "tre milliarder"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [
    (1, "første"), (2, "andre"), (3, "tredje"), (4, "fjerde"), (12, "tolvte"), (13, "trettende"),
    (17, "syttende"), (20, "tjuende"), (21, "tjueførste"), (30, "trettiende"), (100, "hundrede"),
    (101, "hundre og første"), (1000, "tusende"),
])
def test_ordinal(n, words):
    assert ordinal(n) == words


def test_year():
    assert year(1999) == "nitten nittini" and year(1900) == "nitten hundre" and year(1905) == "nitten hundre og fem"


@pytest.mark.parametrize("text, out", [
    ("Hei, verden!", "hei , verden !"),
    ("I 1999 kom han.", "i nitten nittini kom han ."),
    ("Det koster 12,50 kr.", "det koster tolv kroner og femti øre ."),
    ("Det koster 50,- stykket.", "det koster femti kroner stykket ."),
    ("kr 99", "nittini kroner"),
    ("Kl. 14.30 i dag.", "klokken fjorten tretti i dag ."),
    ("Klokka 9:05.", "klokka ni null fem ."),
    ("Den 17. mai 2026.", "den syttende mai to tusen og tjueseks ."),
    ("Den 17.05.2026.", "den syttende mai to tusen og tjueseks ."),
    ("Han kom på 3. plass.", "han kom på tredje plass ."),
    ("Det er 1 250 000 og 3,14.", "det er en million to hundre og femti tusen og tre komma fjorten ."),
    ("75 % og 2 ‰", "syttifem prosent og to promille"),
    ("10-20 km", "ti til tjue kilometer"),
    ("-5 °C", "minus fem grader celsius"),
    ("+47 912 34 567", "pluss fire sju ni en to tre fire fem seks sju"),
    ("ESP32-P4 med USB, NATO.", "e ess pe tre to pe fire med u ess be , nato ."),
    ("f.eks. dette, bl.a. det.", "for eksempel dette , blant annet det ."),
    ("Ja... nei — kanskje.", "ja , nei , kanskje ."),
])
def test_normalize(text, out):
    assert normalize_no(text) == out


def test_split_sentences_keeps_ordinals_and_abbreviations():
    from vtts.frontend.lang import split_sentences_raw

    assert split_sentences_raw("Den 17. mai feirer vi. Det er gøy.", "no") == [
        "Den 17. mai feirer vi.", "Det er gøy."]
    assert split_sentences_raw("Han kom bl.a. i går. Så gikk vi.", "no") == ["Han kom bl.a. i går.", "Så gikk vi."]
    assert split_sentences_raw("Det var i 1999. Så kom 2000.", "no") == ["Det var i 1999.", "Så kom 2000."]
