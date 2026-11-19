"""German normalization (normalize_de) and sentence splitting."""

import pytest

from vtts.frontend.de.normalize_de import (
    cardinal,
    normalize_de,
    ordinal_stem,
    split_sentences_de,
    year,
)


@pytest.mark.parametrize("n, words", [
    (0, "null"), (1, "eins"), (7, "sieben"), (11, "elf"), (16, "sechzehn"), (17, "siebzehn"),
    (21, "einundzwanzig"), (30, "dreißig"), (99, "neunundneunzig"), (100, "hundert"),
    (101, "hunderteins"), (1000, "tausend"), (1234, "tausendzweihundertvierunddreißig"),
    (2026, "zweitausendsechsundzwanzig"), (200000, "zweihunderttausend"),
    (1_000_000, "eine Million"), (2_500_000, "zwei Millionen fünfhunderttausend"),
    (3_000_000_000, "drei Milliarden"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


def test_cardinal_before_a_noun_and_years():
    assert cardinal(1, final=False) == "ein" and cardinal(101, final=False) == "hundertein"
    assert year(1999) == "neunzehnhundertneunundneunzig" and year(1100) == "elfhundert"
    assert year(2026) == "zweitausendsechsundzwanzig"
    assert [ordinal_stem(n) for n in (1, 2, 3, 7, 8, 19, 20, 21, 100)] == [
        "erst", "zweit", "dritt", "siebt", "acht", "neunzehnt", "zwanzigst", "einundzwanzigst", "hundertst"]


@pytest.mark.parametrize("text, out", [
    ("Ich habe 21 Äpfel.", "ich habe einundzwanzig äpfel ."),
    ("Das kostet 5,50 €.", "das kostet fünf euro fünfzig ."),
    ("Nur 0,99 € und 1 € Pfand.", "nur neunundneunzig cent und ein euro pfand ."),
    ("Es sind -5 Grad.", "es sind minus fünf grad ."),
    ("Pi ist 3,14.", "pi ist drei komma eins vier ."),
    ("1.250 Leute", "tausendzweihundertfünfzig leute"),
    ("Er wurde 1999 geboren.", "er wurde neunzehnhundertneunundneunzig geboren ."),
    ("Am 3. Mai 2026", "am dritten mai zweitausendsechsundzwanzig"),
    ("3. Mai", "dritter mai"),
    ("Die 2. Klasse", "die zweite klasse"),
    ("im 5. Stock", "im fünften stock"),
    ("am 03.05.2026", "am dritten mai zweitausendsechsundzwanzig"),
    ("2026-05-03", "dritter mai zweitausendsechsundzwanzig"),
    ("um 14:30 Uhr", "um vierzehn uhr dreißig"),
    ("um 9.05 Uhr", "um neun uhr fünf"),
    ("um 7 Uhr", "um sieben uhr"),
    ("75 % mehr", "fünfundsiebzig prozent mehr"),
    ("3,5 %", "drei komma fünf prozent"),
    ("25 °C", "fünfundzwanzig grad"),
    ("100 km/h", "hundert kilometer pro stunde"),
    ("1 min", "eine minute"),
    ("3 h", "drei stunden"),
    ("8 GB", "acht gigabyte"),
    ("10-20", "zehn bis zwanzig"),
    ("Tel. 030 1234567", "telefon null drei null eins zwei drei vier fünf sechs sieben"),
    ("+49 30 1234567", "plus vier neun drei null eins zwei drei vier fünf sechs sieben"),
    ("z. B. Äpfel, usw.", "zum beispiel äpfel , und so weiter ."),
    ("Dr. Müller", "doktor müller"),
    ("ca. 5 kg", "circa fünf kilogramm"),
    ("1 Stunde und 1 Tag", "eine stunde und ein tag"),
    ("ESP32", "e ess pe drei zwei"),
    ("USB und NATO", "u ess be und nato"),
    ("Schicke eine E-Mail", "schicke eine ihmehl"),
    ("A & B", "a und b"),
])
def test_normalize(text, out):
    assert normalize_de(text) == out


def test_split_keeps_ordinals_and_abbreviations():
    assert split_sentences_de("Am 3. Mai kam er. Dann ging er.") == ["Am 3. Mai kam er.", "Dann ging er."]
    assert split_sentences_de("Das sind z. B. Äpfel. Gut!") == ["Das sind z. B. Äpfel.", "Gut!"]
    assert split_sentences_de("J. S. Bach war bei Dr. Müller.") == ["J. S. Bach war bei Dr. Müller."]
    assert split_sentences_de("Er war die Nummer 1. Danach kam ich.") == ["Er war die Nummer 1.", "Danach kam ich."]
