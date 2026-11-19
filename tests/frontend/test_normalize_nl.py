import pytest

from vtts.frontend.nl.normalize_nl import cardinal, normalize_nl, ordinal, year


@pytest.mark.parametrize("n, words", [
    (0, "nul"), (1, "één"), (7, "zeven"), (13, "dertien"), (20, "twintig"), (21, "eenentwintig"),
    (22, "tweeëntwintig"), (23, "drieëntwintig"), (99, "negenennegentig"), (100, "honderd"),
    (101, "honderdeen"), (250, "tweehonderdvijftig"), (1000, "duizend"), (1001, "duizendeen"),
    (2026, "tweeduizendzesentwintig"), (21000, "eenentwintigduizend"),
    (1_000_000, "één miljoen"), (2_500_000, "twee miljoen vijfhonderdduizend"),
    (3_000_000_000, "drie miljard"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [
    (1, "eerste"), (2, "tweede"), (3, "derde"), (4, "vierde"), (8, "achtste"), (11, "elfde"),
    (18, "achttiende"), (20, "twintigste"), (21, "eenentwintigste"), (100, "honderdste"),
    (101, "honderdeerste"), (1000, "duizendste"),
])
def test_ordinal(n, words):
    assert ordinal(n) == words


def test_year():
    assert year(1999) == "negentienhonderdnegenennegentig" and year(1900) == "negentienhonderd"


@pytest.mark.parametrize("text, out", [
    ("Hallo, wereld!", "hallo , wereld !"),
    ("In 1999 kwam hij.", "in negentienhonderdnegenennegentig kwam hij ."),
    ("Het kost € 5,50.", "het kost vijf euro en vijftig cent ."),
    ("Het kost 5,- per stuk.", "het kost vijf euro per stuk ."),
    ("Het kost 3 euro.", "het kost drie euro ."),
    ("Om 14:30 uur.", "om veertien uur dertig ."),
    ("Om 9.30 uur begint het.", "om negen uur dertig begint het ."),
    ("Op 3-5-2026.", "op drie mei tweeduizendzesentwintig ."),
    ("Op 2026-05-03.", "op drie mei tweeduizendzesentwintig ."),
    ("De 2e en de 21ste keer.", "de tweede en de eenentwintigste keer ."),
    ("Het is 1.250.000 en 3,14.", "het is één miljoen tweehonderdvijftigduizend en drie komma veertien ."),
    ("0,05 procent", "nul komma nul vijf procent"),
    ("75% en 2‰", "vijfenzeventig procent en twee promille"),
    ("10-20 km", "tien tot twintig kilometer"),
    ("1 km en 5 min", "één kilometer en vijf minuten"),
    ("-5 °C", "min vijf graden celsius"),
    ("Bel 06-12345678.", "bel nul zes één twee drie vier vijf zes zeven acht ."),
    ("+31 20 123 4567", "plus drie één twee nul één twee drie vier vijf zes zeven"),
    ("ESP32-P4 en USB, NAVO.", "ee es pee drie twee pee vier en uu es bee , navo ."),
    ("bijv. dit, o.a. dat.", "bijvoorbeeld dit , onder andere dat ."),
    ("'s Avonds en auto's, zo'n 5km.", "'s avonds en auto's , zo'n vijf kilometer ."),
    ("Ja... nee — misschien.", "ja , nee , misschien ."),
    ("Jan & Piet", "jan en piet"),
    ("4G en 3D", "vier gee en drie dee"),
])
def test_normalize(text, out):
    assert normalize_nl(text) == out


def test_split_sentences_keeps_abbreviations():
    from vtts.frontend.lang import split_sentences_raw

    assert split_sentences_raw("Dr. Jansen komt o.a. morgen. Dan gaan we.", "nl") == [
        "Dr. Jansen komt o.a. morgen.", "Dan gaan we."]
    assert split_sentences_raw("Het werk van J. S. Bach. Mooi!", "nl") == ["Het werk van J. S. Bach.", "Mooi!"]
    assert split_sentences_raw("Fruit enz. De rest.", "nl") == ["Fruit enz.", "De rest."]
