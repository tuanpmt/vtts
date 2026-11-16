import pytest

from vtts.frontend.en.normalize_en import normalize_en


@pytest.mark.parametrize("text,expected", [
    ("It costs $5.50.", "it costs five dollars fifty cents ."),
    ("Meet at 3:30 pm on 11/16/2026", "meet at three thirty p m on november sixteenth twenty twenty six"),
    ("the 21st floor", "the twenty first floor"),
    ("1,250 people", "one thousand two hundred fifty people"),
    ("Dr. Smith", "doctor smith"),
    ("USB-C", "u s b c"),
    ("4K video", "four k video"),
    ("25°C", "twenty five degrees celsius"),
    ("50%", "fifty percent"),
    ("in 2005", "in two thousand five"),
    ("in 1999", "in nineteen ninety nine"),
    ("3.14", "three point one four"),
    ("-7", "minus seven"),
    ("10 km", "ten kilometers"),
    ("Hello, world!", "hello , world !"),
    ("iPhone 15 costs $799", "i phone fifteen costs seven hundred ninety nine dollars"),
    ("on Tuesday, November 18, between 2 and 4 p.m.", "on tuesday , november eighteenth , between two and four p m"),
    ("We have 3, 4 or 5.", "we have three , four or five ."),
    ("Apple's AirPods", "apple's air pods"),
])
def test_normalize_en(text, expected):
    assert normalize_en(text) == expected
