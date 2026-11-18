import pytest

from vtts.frontend.pt.normalize_pt import cardinal, feminine, normalize_pt, ordinal


@pytest.mark.parametrize("n, words", [
    (0, "zero"), (1, "um"), (14, "quatorze"), (16, "dezesseis"), (21, "vinte e um"),
    (100, "cem"), (101, "cento e um"), (120, "cento e vinte"), (200, "duzentos"),
    (555, "quinhentos e cinquenta e cinco"), (1000, "mil"), (1001, "mil e um"),
    (1100, "mil e cem"), (1200, "mil e duzentos"), (1234, "mil duzentos e trinta e quatro"),
    (2026, "dois mil e vinte e seis"), (10_000, "dez mil"), (1_000_000, "um milhão"),
    (2_500_000, "dois milhões e quinhentos mil"), (10 ** 9, "um bilhão"),
    (3 * 10 ** 12, "três trilhões"), (-7, "menos sete"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


def test_feminine_and_ordinal():
    assert feminine("vinte e um") == "vinte e uma" and feminine("dois") == "duas"
    assert feminine("duzentos") == "duzentas"
    assert ordinal(1) == "primeiro" and ordinal(2, fem=True) == "segunda"
    assert ordinal(21) == "vigésimo primeiro" and ordinal(100) == "centésimo"


@pytest.mark.parametrize("text, out", [
    ("Olá, tudo bem?", "olá , tudo bem ?"),
    # numbers
    ("Tenho 21 anos.", "tenho vinte e um anos ."),
    ("São 1.250 pessoas.", "são mil duzentos e cinquenta pessoas ."),
    ("3,14 e 2.5", "três vírgula quatorze e dois ponto cinco"),
    ("-5 graus", "menos cinco graus"),
    ("de 10-20 pessoas", "de dez a vinte pessoas"),
    ("2.000.000 de pessoas", "dois milhões de pessoas"),
    # dates and times
    ("Em 5/3/2026.", "em cinco de março de dois mil e vinte e seis ."),
    ("1/5/2024", "primeiro de maio de dois mil e vinte e quatro"),
    ("2026-11-18", "dezoito de novembro de dois mil e vinte e seis"),
    ("às 14h30", "às quatorze e trinta"),
    ("às 7h", "às sete horas"),
    ("à 1:00", "à uma hora"),
    ("às 21:15", "às vinte e uma e quinze"),
    # money, percent, units
    ("Custa R$ 1.250,50.", "custa mil duzentos e cinquenta reais e cinquenta centavos ."),
    ("R$ 1,00", "um real"),
    ("R$ 0,01", "zero reais e um centavo"),
    ("US$ 5 ou 20 €", "cinco dólares ou vinte euros"),
    ("R$ 1,5 milhão", "um vírgula cinco milhão de reais"),
    ("15,5% do total", "quinze vírgula cinco por cento do total"),
    ("Corre 5 km e 1 km.", "corre cinco quilômetros e um quilômetro ."),
    ("Faz 25 °C", "faz vinte e cinco graus"),
    ("8 GB", "oito gigabaites"),
    # ordinals, phone numbers
    ("o 1º lugar e a 2ª vez", "o primeiro lugar e a segunda vez"),
    ("Ligue para (11) 98765-4321.", "ligue para um um nove oito sete seis cinco quatro três dois um ."),
    ("+55 11 98765 4321", "mais cinco cinco um um nove oito sete seis cinco quatro três dois um"),
    # codes, acronyms, abbreviations, symbols
    ("A placa ESP32-P4", "a placa é ésse pê três dois pê quatro"),
    ("o USB e a ONU", "o ú ésse bê e a onu"),
    ("o ENEM e o CPF", "o enem e o cê pê éfe"),
    ("Sr. Silva e a Dra. Souza", "senhor silva e a doutora souza"),
    ("frutas, legumes, etc.", "frutas , legumes , etcétera ."),
    ("vc vem? pq não?", "você vem ? porque não ?"),
    ("Ana & João", "ana e joão"),
    ("Bom… vamos", "bom , vamos"),
    ("“Oi” (disse ela)", "oi disse ela"),
])
def test_normalize_pt(text, out):
    assert normalize_pt(text) == out


def test_no_digits_left():
    for text in ["1", "12345678901234567890", "3,5%", "1º", "10:00", "99 km", "R$0,99", "14h"]:
        assert not any(ch.isdigit() for ch in normalize_pt(text)), text
