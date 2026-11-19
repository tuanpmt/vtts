import pytest

from vtts.frontend.da.normalize_da import cardinal, normalize_da, year


@pytest.mark.parametrize("n, words", [
    (0, "nul"), (1, "en"), (17, "sytten"), (21, "enogtyve"), (50, "halvtreds"), (60, "tres"),
    (75, "femoghalvfjerds"), (80, "firs"), (99, "nioghalvfems"), (100, "hundrede"),
    (101, "hundrede og en"), (250, "to hundrede og halvtreds"), (1000, "tusind"),
    (2026, "to tusind og seksogtyve"), (1250, "tusind to hundrede og halvtreds"),
    (1_000_000, "en million"), (3_500_000, "tre millioner fem hundrede tusind"),
    (2_000_000_000, "to milliarder"), (-4, "minus fire"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


def test_year():
    assert year(1984) == "nitten hundrede og fireogfirs"
    assert year(1900) == "nitten hundrede"
    assert year(2026) == "to tusind og seksogtyve"


@pytest.mark.parametrize("text, out", [
    ("Mødet er kl. 14.30 den 5. marts 2026.",
     "mødet er klokken fjorten tredive den femte marts to tusind og seksogtyve ."),
    ("Det koster 12,50 kr.", "det koster tolv kroner og halvtreds øre ."),
    ("Det koster 1 kr. og 50 øre.", "det koster en krone og halvtreds øre ."),
    ("Ring på +45 12 34 56 78.",
     "ring på plus femogfyrre tolv fireogtredive seksoghalvtreds otteoghalvfjerds ."),
    ("Han er født 1. maj 1990.", "han er født første maj nitten hundrede og halvfems ."),
    ("25 km/t og 3,5 % og -4 °C.",
     "femogtyve kilometer i timen og tre komma fem procent og minus fire grader ."),
    ("f.eks. USB og NATO, ESP32.", "for eksempel u es be og nato , e es pe tre to ."),
    ("Dato: 2026-03-05 og 5/3/2026.",
     "dato : femte marts to tusind og seksogtyve og femte marts to tusind og seksogtyve ."),
    ("Kampen sluttede 2-1.", "kampen sluttede to til en ."),
    ("Klokken 8:05.", "klokken otte nul fem ."),
    ("Det kostede 5 € og 3 $.", "det kostede fem euro og tre dollar ."),
    ("Der bor 5.950.000 mennesker.", "der bor fem millioner ni hundrede og halvtreds tusind mennesker ."),
])
def test_normalize(text, out):
    assert normalize_da(text) == out
