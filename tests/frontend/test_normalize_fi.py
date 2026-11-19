import pytest

from vtts.frontend.fi.normalize_fi import (
    ELATIVE,
    ILLATIVE,
    cardinal,
    inflect,
    normalize_fi,
    ordinal,
)


@pytest.mark.parametrize("n, words", [
    (0, "nolla"), (1, "yksi"), (10, "kymmenen"), (11, "yksitoista"), (19, "yhdeksäntoista"),
    (20, "kaksikymmentä"), (21, "kaksikymmentäyksi"), (99, "yhdeksänkymmentäyhdeksän"),
    (100, "sata"), (101, "satayksi"), (234, "kaksisataakolmekymmentäneljä"), (1000, "tuhat"),
    (1001, "tuhatyksi"), (2026, "kaksituhattakaksikymmentäkuusi"), (10000, "kymmenentuhatta"),
    (1_000_000, "miljoona"), (2_500_000, "kaksi miljoonaa viisisataatuhatta"),
    (10 ** 9, "miljardi"), (3 * 10 ** 9, "kolme miljardia"), (-7, "miinus seitsemän"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [
    (1, "ensimmäinen"), (2, "toinen"), (3, "kolmas"), (10, "kymmenes"), (11, "yhdestoista"),
    (12, "kahdestoista"), (20, "kahdeskymmenes"), (21, "kahdeskymmenesensimmäinen"),
    (22, "kahdeskymmenestoinen"), (100, "sadas"), (200, "kahdessadas"), (1000, "tuhannes"),
])
def test_ordinal(n, words):
    assert ordinal(n) == words


def test_inflected_for_ranges():
    assert inflect(20, ELATIVE) == "kahdestakymmenestä"
    assert inflect(15, ILLATIVE) == "viiteentoista"


@pytest.mark.parametrize("text, out", [
    ("Hei, mitä kuuluu?", "hei , mitä kuuluu ?"),
    ("Olen 21 vuotta vanha.", "olen kaksikymmentäyksi vuotta vanha ."),
    ("Hän syntyi 3. toukokuuta 1950.", "hän syntyi kolmas toukokuuta tuhatyhdeksänsataaviisikymmentä ."),
    ("1. maailmansota", "ensimmäinen maailmansota"),
    ("Päivä 3.5.2026", "päivä kolmas toukokuuta kaksituhattakaksikymmentäkuusi"),
    ("2026-11-19", "yhdeksästoista marraskuuta kaksituhattakaksikymmentäkuusi"),
    ("klo 14.30", "kello neljätoista kolmekymmentä"),
    ("kello 9", "kello yhdeksän"),
    ("klo 9.05", "kello yhdeksän nolla viisi"),
    ("14:30", "neljätoista kolmekymmentä"),
    ("Hinta on 12,50 €.", "hinta on kaksitoista euroa viisikymmentä senttiä ."),
    ("1 € ja 5 €", "yksi euro ja viisi euroa"),
    ("$20", "kaksikymmentä dollaria"),
    ("15 %", "viisitoista prosenttia"),
    ("1 %", "yksi prosentti"),
    ("3,5 km", "kolme pilkku viisi kilometriä"),
    ("1 km", "yksi kilometri"),
    ("25 °C", "kaksikymmentäviisi astetta"),
    ("1 000 000 asukasta", "miljoona asukasta"),
    ("040 123 4567", "nolla neljä nolla yksi kaksi kolme neljä viisi kuusi seitsemän"),
    ("+358 40 123 4567", "plus kolme viisi kahdeksan neljä nolla yksi kaksi kolme neljä viisi kuusi seitsemän"),
    ("-5 astetta", "miinus viisi astetta"),
    ("vuosina 1939–1945", ("vuosina tuhannestayhdeksästäsadastakolmestakymmenestäyhdeksästä "
                           "tuhanteenyhdeksäänsataanneljäänkymmeneenviiteen")),
    ("esim. kissa, jne.", "esimerkiksi kissa , ja niin edelleen ."),
    ("n. 50 henkeä", "noin viisikymmentä henkeä"),
    ("ESP32-P4", "ee äs pee kolme kaksi pee neljä"),
    ("USB ja Nato", "uu äs bee ja nato"),
    ("3 kpl", "kolme kappaletta"),
    ("Kissa & koira", "kissa ja koira"),
])
def test_normalize(text, out):
    assert normalize_fi(text) == out
