"""Polish normalization (pl/normalize_pl.py)."""

import pytest

from vtts.frontend.pl.normalize_pl import cardinal, cardinal_gen, normalize_pl, ordinal, plural


@pytest.mark.parametrize("n, gender, words", [
    (0, "m", "zero"), (1, "m", "jeden"), (1, "f", "jedna"), (1, "n", "jedno"), (2, "f", "dwie"),
    (12, "f", "dwanaście"), (22, "f", "dwadzieścia dwie"), (21, "f", "dwadzieścia jeden"),
    (100, "m", "sto"), (1000, "m", "tysiąc"), (2000, "m", "dwa tysiące"),
    (5000, "m", "pięć tysięcy"), (22000, "m", "dwadzieścia dwa tysiące"),
    (2026, "m", "dwa tysiące dwadzieścia sześć"), (1_000_000, "m", "milion"),
    (2_500_000, "m", "dwa miliony pięćset tysięcy"), (-5, "m", "minus pięć"),
])
def test_cardinal(n, gender, words):
    assert cardinal(n, gender) == words


@pytest.mark.parametrize("n, case, words", [
    (1, "nom_m", "pierwszy"), (2, "nom_f", "druga"), (2, "gen_m", "drugiego"), (3, "nom_f", "trzecia"),
    (3, "gen_m", "trzeciego"), (22, "loc_m", "dwudziestym drugim"), (100, "nom_m", "setny"),
    (300, "nom_m", "trzechsetny"), (2000, "nom_m", "dwutysięczny"),
    (2026, "gen_m", "dwa tysiące dwudziestego szóstego"),
    (1990, "nom_m", "tysiąc dziewięćset dziewięćdziesiąty"), (14, "gen_f", "czternastej"),
])
def test_ordinal(n, case, words):
    assert ordinal(n, case) == words


def test_plural_and_genitive():
    forms = ("złoty", "złote", "złotych")
    assert [plural(n, forms) for n in (1, 2, 5, 11, 12, 21, 22, 25, 112)] == [
        "złoty", "złote", "złotych", "złotych", "złotych", "złotych", "złote", "złotych", "złotych"]
    assert cardinal_gen(32) == "trzydziestu dwóch" and cardinal_gen(2500) == "dwóch tysięcy pięciuset"


@pytest.mark.parametrize("text, out", [
    ("Cześć, jak się masz?", "cześć , jak się masz ?"),
    ("Mam 21 lat.", "mam dwadzieścia jeden lat ."),
    ("1 książka, 1 okno", "jedna książka , jedno okno"),
    ("Jest 15:45.", "jest piętnasta czterdzieści pięć ."),
    ("o 14:30", "o czternastej trzydzieści"),
    ("15.12.2026", "piętnasty grudnia dwa tysiące dwudziestego szóstego roku"),
    ("5 maja", "piąty maja"),
    ("w 1990 r.", "w-tysiąc dziewięćset dziewięćdziesiątym roku ."),
    ("w 2026 roku", "w-dwa tysiące dwudziestym szóstym roku"),
    ("w XIX wieku", "w-dziewiętnastym wieku"),
    ("XXI wiek", "dwudziesty pierwszy wiek"),
    ("1250 zł", "tysiąc dwieście pięćdziesiąt złotych"),
    ("23,99 zł", "dwadzieścia trzy złote dziewięćdziesiąt dziewięć groszy"),
    ("$5", "pięć dolarów"),
    ("3 mln zł", "trzy miliony złotych"),
    ("5 tys. osób", "pięć tysięcy osób"),
    ("75%", "siedemdziesiąt pięć procent"),
    ("1,2 kg", "jeden i dwie dziesiąte kilograma"),
    ("2,25", "dwa i dwadzieścia pięć setnych"),
    ("3,14159", "trzy przecinek jeden cztery jeden pięć dziewięć"),
    ("do 30 °C", "do trzydziestu stopni celsjusza"),
    ("10-20 osób", "od dziesięciu do dwudziestu osób"),
    ("-5 °C", "minus pięć stopni celsjusza"),
    ("+48 123 456 789", "plus cztery osiem jeden dwa trzy cztery pięć sześć siedem osiem dziewięć"),
    ("ESP32 i USB", "e es pe trzy dwa i u es be"),
    ("PKP, NATO, ZUS", "pe ka pe , nato , zus"),
    ("Np. tak, itd.", "na przykład tak , i tak dalej ."),
    ("ul. Długa", "ulica długa"),
    ("W domu z tobą", "w-domu z-tobą"),
    ("To — przykład", "to , przykład"),
    ("1 2 3", "jeden dwa trzy"),
])
def test_normalize(text, out):
    assert normalize_pl(text) == out
