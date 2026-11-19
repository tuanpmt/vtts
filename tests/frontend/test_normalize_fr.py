import pytest

from vtts.frontend.fr.normalize_fr import cardinal, feminine, normalize_fr, ordinal


@pytest.mark.parametrize("n, words", [
    (0, "zéro"), (1, "un"), (16, "seize"), (17, "dix-sept"), (21, "vingt et un"),
    (22, "vingt-deux"), (70, "soixante-dix"), (71, "soixante et onze"), (72, "soixante-douze"),
    (79, "soixante-dix-neuf"), (80, "quatre-vingts"), (81, "quatre-vingt-un"),
    (90, "quatre-vingt-dix"), (91, "quatre-vingt-onze"), (99, "quatre-vingt-dix-neuf"),
    (100, "cent"), (101, "cent un"), (200, "deux cents"), (201, "deux cent un"),
    (280, "deux cent quatre-vingts"), (1000, "mille"), (1001, "mille un"), (2000, "deux mille"),
    (1789, "mille sept cent quatre-vingt-neuf"), (2026, "deux mille vingt-six"),
    (80_000, "quatre-vingt mille"), (200_000, "deux cent mille"), (1_000_000, "un million"),
    (2_500_000, "deux millions cinq cent mille"), (80_000_000, "quatre-vingts millions"),
    (10 ** 9, "un milliard"), (-7, "moins sept"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


def test_feminine_and_ordinal():
    assert feminine("vingt et un") == "vingt et une" and feminine("quatre-vingt-un") == "quatre-vingt-une"
    assert ordinal(1) == "premier" and ordinal(1, fem=True) == "première"
    assert ordinal(2) == "deuxième" and ordinal(5) == "cinquième" and ordinal(9) == "neuvième"
    assert ordinal(21) == "vingt et unième" and ordinal(80) == "quatre-vingtième"
    assert ordinal(100) == "centième" and ordinal(1000) == "millième" and ordinal(11) == "onzième"


@pytest.mark.parametrize("text, out", [
    ("Bonjour, ça va?", "bonjour , ça va ?"),
    # numbers (with liaison: vingt t'et un n'ans)
    ("J'ai 21 ans.", "j'ai vingt t'et un n'ans ."),
    ("Il y a 1 250 personnes.", "il y a mille deux cent cinquante personnes ."),
    ("3,14 et 2.5", "trois virgule quatorze et deux point cinq"),
    ("-5 degrés", "moins cinq degrés"),
    ("de 10-20 personnes", "de dix à vingt personnes"),
    ("2 000 000 de personnes", "deux millions de personnes"),
    ("1 heure, 1 voiture, 21 pages", "une heure , une voiture , vingt t'et une pages"),
    # dates and times
    ("Le 14/07/1789.", "le quatorze juillet mille sept cent quatre vingt neuf ."),
    ("le 1/5/2024", "le premier mai deux mille vingt t'quatre"),
    ("2026-11-19", "di z'neuf novembre deux mille vingt t'six"),
    ("à 14 h 30", "à quatorze heures trente"),
    ("à 14h30", "à quatorze heures trente"),
    ("à 8 h", "à huit heures"),
    ("à 1 h", "à une heure"),
    ("à 21:15", "à vingt t'et une heures quinze"),
    # money, percent, units
    ("Ça coûte 12,50 €.", "ça coûte douze euros cinquante ."),
    ("1 €", "un n'euro"),
    ("0,50 €", "cinquante centimes"),
    ("1 000 000 €", "un million d'euros"),
    ("$5 ou 20 £", "cinq dollars ou vingt livres"),
    ("1,5 million €", "un virgule cinq million d'euros"),
    ("15,5 % du total", "quinze virgule cinq pour cent du total"),
    ("Il court 5 km et 1 km.", "il court cinq kilomètres et un kilomètre ."),
    ("Il fait 25 °C.", "il fait vingt t'cinq degrés ."),
    ("8 Go", "hui gigaoctets"),
    # ordinals, Roman numerals, phone numbers
    ("le 1er et la 1re, le 2e et la 2nde", "le premier et la première , le deuxième et la seconde"),
    ("le XIXe siècle et Louis XIV", "le di z'neuvième siècle et louis quatorze"),
    ("Appelez le 06 12 34 56 78.",
     "appelez le zéro si douze trente quatre cinquante si soixante di z'huit ."),
    ("+33 6 12 34 56 78", "plus trente trois si douze trente quatre cinquante si soixante di z'huit"),
    # codes, acronyms, abbreviations, symbols
    ("La carte ESP32-P4", "la carte eu èss pé trois deux pé quatre"),
    ("la SNCF et l'ONU", "la èss èn cé èf et l'onu"),
    ("M. Dupont et Mme Martin, etc.", "monsieur dupont et madame martin , et cetera ."),
    ("Le Dr Moreau habite au n° 5.", "le docteur moreau habite au numéro cinq ."),
    ("Paul & Marie", "paul et marie"),
    ("Bon… allons-y", "bon , allons z'y"),
    ("« Bonjour » (dit-elle)", "bonjour dit t'elle"),
    ("a-t-il dit", "a t'il dit"),
    # liaison, elision, h aspiré, denasalization, number finals
    ("Les amis sont arrivés.", "les z'amis sont t'arrivés ."),
    ("un ami, mon ami, bon ami, ancien élève", "un n'ami , mon n'ami , bonne ami , ancienne élève"),
    ("les héros et les hommes", "les héros et les z'hommes"),
    ("six ans, six mois, six.", "si z'ans , si mois , six ."),
    ("dix-huit, dix-neuf, dix-sept", "di z'huit , di z'neuf , dix sept"),
    ("vingt-deux, quatre-vingt-deux, vingt ans", "vingt t'deux , quatre vingt deux , vingt t'ans"),
    ("neuf ans, neuf heures, neuf mois", "neuf v'ans , neuf v'heures , neuf mois"),
    ("ils sont tous là, ils sont tous.", "ils sont tous là , ils sont tousse ."),
    ("à l'est de la ville", "à l'èst de la ville"),
    ("avec nous au cinéma, nous avons", "avec nous au cinéma , nous z'avons"),
    ("Aujourd’hui, quelqu'un est là.", "aujourd'hui , quelqu'un est là ."),
])
def test_normalize_fr(text, out):
    assert normalize_fr(text) == out


def test_no_digits_left():
    for text in ["1", "12345678901234567890", "3,5 %", "1er", "10:00", "99 km", "0,99 €", "14 h",
                 "XXIe", "2e", "1 000 000"]:
        assert not any(ch.isdigit() for ch in normalize_fr(text)), text
