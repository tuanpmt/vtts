import pytest

from vtts.frontend.es.normalize_es import cardinal, normalize_es, ordinal
from vtts.frontend.latin_norm import parse_number


@pytest.mark.parametrize("n, words", [
    (0, "cero"), (1, "uno"), (15, "quince"), (16, "dieciséis"), (21, "veintiuno"),
    (22, "veintidós"), (30, "treinta"), (31, "treinta y uno"), (99, "noventa y nueve"),
    (100, "cien"), (101, "ciento uno"), (115, "ciento quince"), (200, "doscientos"),
    (500, "quinientos"), (777, "setecientos setenta y siete"), (1000, "mil"), (1001, "mil uno"),
    (2026, "dos mil veintiséis"), (21000, "veintiún mil"), (100000, "cien mil"),
    (1_000_000, "un millón"), (2_500_000, "dos millones quinientos mil"),
    (1_000_000_000, "mil millones"), (21_000_000, "veintiún millones"),
    (10 ** 12, "un billón"), (-7, "menos siete"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, fem, words", [
    (1, False, "primero"), (2, True, "segunda"), (3, False, "tercero"), (10, False, "décimo"),
    (11, False, "undécimo"), (21, False, "vigésimo primero"), (100, False, "centésimo"),
    (23, True, "vigésima tercera"),
])
def test_ordinal(n, fem, words):
    assert ordinal(n, fem) == words


@pytest.mark.parametrize("s, parsed", [
    ("1.000", (1000, None, None)), ("1.000.000", (1000000, None, None)),
    ("1,000,000", (1000000, None, None)), ("1.234,5", (1234, "5", ",")),
    ("1,234.5", (1234, "5", ".")), ("3,5", (3, "5", ",")), ("3.14", (3, "14", ".")),
    ("0,05", (0, "05", ",")), ("2026", (2026, None, None)),
])
def test_parse_number(s, parsed):
    assert parse_number(s) == parsed


@pytest.mark.parametrize("text, out", [
    ("Hola, ¿qué tal?", "hola , qué tal ?"),
    ("¡Qué bien!", "qué bien !"),
    # numbers, "un" before a word
    ("Tengo 21 años y 1 perro.", "tengo veintiún años y un perro ."),
    ("Son 1.250 personas.", "son mil doscientos cincuenta personas ."),
    ("Página 1", "página uno"),
    ("3,14 y 2.5", "tres coma catorce y dos punto cinco"),
    ("0,05", "cero coma cero cinco"),
    ("-5 grados", "menos cinco grados"),
    ("de 10-20 personas", "de diez a veinte personas"),
    ("2.000.000 de personas", "dos millones de personas"),
    # dates and times
    ("El 5/3/2026.", "el cinco de marzo de dos mil veintiséis ."),
    ("2026-11-18", "dieciocho de noviembre de dos mil veintiséis"),
    ("a las 14:30 h.", "a las catorce y treinta ."),
    ("a las 7:00", "a las siete en punto"),
    ("a la 1:15", "a la una y quince"),
    ("a las 21:05", "a las veintiuna y cinco"),
    # money, percent, units
    ("Cuesta $1.250,50.", "cuesta mil doscientos cincuenta coma cincuenta dólares ."),
    ("20 € o 1 €", "veinte euros o un euro"),
    ("El 15,5% del total", "el quince coma cinco por ciento del total"),
    ("Corre 5 km y 1 km.", "corre cinco kilómetros y un kilómetro ."),
    ("Hace 25 °C", "hace veinticinco grados"),
    ("a 120 km/h", "a ciento veinte kilómetros por hora"),
    ("8 GB de RAM", "ocho gigabytes de ram"),
    # ordinals
    ("el 1.º y la 2.ª", "el primero y la segunda"),
    ("el 3.er piso", "el tercer piso"),
    # phone numbers digit by digit
    ("Llama al 600 123 456.", "llama al seis cero cero uno dos tres cuatro cinco seis ."),
    ("+34 600 123 456", "más tres cuatro seis cero cero uno dos tres cuatro cinco seis"),
    ("código 0034", "código cero cero tres cuatro"),
    # codes, acronyms, abbreviations, symbols
    ("La placa ESP32-P4", "la placa é ese pe tres dos pe cuatro"),
    ("el USB y la ONU", "el ú ese be y la onu"),
    ("COVID-19", "covid diecinueve"),
    ("Sr. Pérez y la Dra. Gómez", "señor pérez y la doctora gómez"),
    ("perros, gatos, etc.", "perros , gatos , etcétera ."),
    ("EE. UU.", "estados unidos ."),
    ("Juan & María", "juan y maría"),
    ("Escribe a info@correo", "escribe a info arroba correo"),
    ("Bueno… vale", "bueno , vale"),
    ("Él — dijo — vino", "él , dijo , vino"),
    ("«Hola» (dijo)", "hola dijo"),
])
def test_normalize_es(text, out):
    assert normalize_es(text) == out


def test_no_digits_left():
    for text in ["1", "12345678901234567890123456", "3,5%", "1º", "10:00", "99 km", "$0,99"]:
        assert not any(ch.isdigit() for ch in normalize_es(text)), text
