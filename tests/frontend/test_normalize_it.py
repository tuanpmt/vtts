import pytest

from vtts.frontend.it.normalize_it import cardinal, normalize_it, ordinal


@pytest.mark.parametrize("n, words", [
    (0, "zero"), (1, "uno"), (11, "undici"), (17, "diciassette"), (21, "ventuno"),
    (23, "ventitré"), (28, "ventotto"), (30, "trenta"), (33, "trentatré"), (99, "novantanove"),
    (100, "cento"), (101, "cento uno"), (180, "cento ottanta"), (200, "duecento"),
    (777, "settecento settantasette"), (1000, "mille"), (1001, "mille uno"),
    (2026, "duemila ventisei"), (21000, "ventunomila"), (100000, "centomila"),
    (1234, "mille duecento trentaquattro"), (1_000_000, "un milione"), (10 ** 12, "un bilione"),
    (2_500_000, "due milioni cinquecentomila"), (10 ** 9, "un miliardo"), (-7, "meno sette"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, fem, words", [
    (1, False, "primo"), (2, True, "seconda"), (3, False, "terzo"), (10, False, "decimo"),
    (11, False, "undicesimo"), (21, False, "ventunesimo"), (23, True, "ventitreesima"),
    (26, False, "ventiseiesimo"), (100, False, "centesimo"), (1000, False, "millesimo"),
])
def test_ordinal(n, fem, words):
    assert ordinal(n, fem) == words


@pytest.mark.parametrize("text, out", [
    ("Ho 21 anni e 1 euro.", "ho ventun anni e un euro ."),
    ("101 e 180, 1 di loro.", "cento uno e cento ottanta , uno di loro ."),
    ("Costa 12,50 € o $5.", "costa dodici euro e cinquanta centesimi o cinque dollari ."),
    ("Il 5/3/2026 alle 14:30.", "il cinque marzo duemila ventisei alle quattordici e trenta ."),
    ("Alle 9.15 arriva.", "alle nove e quindici arriva ."),
    ("Il 3º posto, la 2ª volta.", "il terzo posto , la seconda volta ."),
    ("Il 25% e 3,5 km.", "il venticinque per cento e tre virgola cinque chilometri ."),
    ("Fa 25 °C.", "fa venticinque gradi ."),
    ("Chiama il 333 1234567.", "chiama il tre tre tre uno due tre quattro cinque sei sette ."),
    ("+39 06 1234 5678", "più tre nove zero sei uno due tre quattro cinque sei sette otto"),
    ("La scheda ESP32 con USB.", "la scheda e esse pi tre due con u esse bi ."),
    ("La NATO e l'ONU.", "la nato e l'onu ."),
    ("Pagine 10-20, ecc.", "pagine dieci a venti , eccetera ."),
    ("Il Sig. Rossi e la Dott.ssa Bianchi.", "il signor rossi e la dottoressa bianchi ."),
    ("L’acqua c’è…", "l'acqua c'è ,"),
    ("Temperatura -5 gradi.", "temperatura meno cinque gradi ."),
    ("1.000.000 di euro", "un milione di euro"),
    ("Rock & roll", "rock e roll"),
])
def test_normalize(text, out):
    assert normalize_it(text) == out


def test_final_apostrophe_is_kept_as_a_letter():
    assert normalize_it("un po' d'acqua") == "un poʼ d'acqua"
