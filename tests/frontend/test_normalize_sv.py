import pytest

from vtts.frontend.sv.normalize_sv import cardinal, normalize_sv, ordinal, year


@pytest.mark.parametrize("n, words", [
    (0, "noll"), (1, "ett"), (7, "sju"), (13, "tretton"), (20, "tjugo"), (21, "tjugoett"),
    (99, "nittionio"), (100, "hundra"), (101, "hundraett"), (250, "tvåhundrafemtio"),
    (1000, "tusen"), (2026, "tvåtusentjugosex"), (1_000_000, "en miljon"),
    (2_500_000, "två miljoner femhundratusen"), (3_000_000_000, "tre miljarder"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [
    (1, "första"), (2, "andra"), (3, "tredje"), (4, "fjärde"), (12, "tolfte"), (13, "trettonde"),
    (20, "tjugonde"), (21, "tjugoförsta"), (30, "trettionde"), (100, "hundrade"), (101, "hundraförsta"),
    (1000, "tusende"),
])
def test_ordinal(n, words):
    assert ordinal(n) == words


def test_year():
    assert year(1999) == "nittonhundranittionio" and year(1900) == "nittonhundra"


@pytest.mark.parametrize("text, out", [
    ("Hej, världen!", "hej , världen !"),
    ("År 1999 kom han.", "år nittonhundranittionio kom han ."),
    ("Det kostar 12,50 kr.", "det kostar tolv kronor och femtio öre ."),
    ("Det kostar 50:- styck.", "det kostar femtio kronor styck ."),
    ("Det kostar 99 kr.", "det kostar nittionio kronor ."),
    ("€ 5,50", "fem euro och femtio cent"),
    ("Kl. 14.30 i dag.", "klockan fjorton trettio i dag ."),
    ("Klockan 9:05.", "klockan nio noll fem ."),
    ("Den 3 maj 2026.", "den tredje maj tvåtusentjugosex ."),
    ("Den 2026-05-03.", "den tredje maj tvåtusentjugosex ."),
    ("Den 2:a och 21:a gången.", "den andra och tjugoförsta gången ."),
    ("Det är 1 250 000 och 3,14.", "det är en miljon tvåhundrafemtiotusen och tre komma fjorton ."),
    ("75 % och 2 ‰", "sjuttiofem procent och två promille"),
    ("10-20 km", "tio till tjugo kilometer"),
    ("1 km och 5 min", "ett kilometer och fem minuter"),
    ("-5 °C", "minus fem grader celsius"),
    ("Ring 08-123 45 67.", "ring noll åtta ett två tre fyra fem sex sju ."),
    ("ESP32-P4 med USB, NATO.", "e ess pe tre två pe fyra med u ess be , nato ."),
    ("t.ex. detta, bl.a. det.", "till exempel detta , bland annat det ."),
    ("Ja... nej — kanske.", "ja , nej , kanske ."),
])
def test_normalize(text, out):
    assert normalize_sv(text) == out


def test_split_sentences_keeps_abbreviations():
    from vtts.frontend.lang import split_sentences_raw

    assert split_sentences_raw("Han kom bl.a. i går. Sedan gick vi.", "sv") == [
        "Han kom bl.a. i går.", "Sedan gick vi."]
    assert split_sentences_raw("Frukt osv. Resten.", "sv") == ["Frukt osv.", "Resten."]
