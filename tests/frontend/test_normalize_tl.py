import pytest

from vtts.frontend.tl.normalize_tl import cardinal, linked, normalize_tl, ordinal, spanish


@pytest.mark.parametrize("n, words", [
    (0, "sero"), (1, "isa"), (10, "sampu"), (11, "labing isa"), (12, "labindalawa"),
    (14, "labing apat"), (19, "labinsiyam"), (20, "dalawampu"), (21, "dalawampu't isa"),
    (45, "apatnapu't lima"), (100, "isang daan"), (125, "isang daan at dalawampu't lima"),
    (400, "apat na raan"), (600, "anim na raan"), (1000, "isang libo"),
    (1250, "isang libo at dalawang daan at limampu"), (2026, "dalawang libo at dalawampu't anim"),
    (10_000, "sampung libo"), (21_000, "dalawampu't isang libo"), (1_000_000, "isang milyon"),
    (10 ** 9, "isang bilyon"), (-7, "minus pito"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("n, words", [(1, "uno"), (5, "singko"), (15, "kinse"), (20, "beynte"),
                                      (25, "beynte singko"), (35, "treynta'y singko"),
                                      (50, "singkuwenta"), (100, "siyen"),
                                      (150, "siyento singkuwenta"), (250, "dos siyentos singkuwenta"),
                                      (500, "kinyentos"), (999, "nobe siyentos nobenta'y nuwebe")])
def test_spanish(n, words):
    assert spanish(n) == words


def test_ordinal_and_linker():
    assert [ordinal(n) for n in (1, 2, 3, 4, 10, 21)] == [
        "una", "ikalawa", "ikatlo", "ikaapat", "ikasampu", "ikadalawampu't isa"]
    assert [linked(w) for w in ("isa", "apat", "milyon", "dalawampu't isa")] == [
        "isang", "apat na", "milyong", "dalawampu't isang"]


@pytest.mark.parametrize("text, out", [
    ("Kumusta ka?", "kumusta ka ?"),
    # numbers, with the linker before a noun
    ("May 3 aso ako.", "may tatlong aso ako ."),
    ("21 tao at 1,250 upuan", "dalawampu't isang tao at isang libo at dalawang daan at limampung upuan"),
    ("Noong 2026 ay", "noong dalawang libo at dalawampu't anim ay"),
    ("3.14", "tatlo punto isa apat"),
    ("-5 digri", "minus limang digri"),
    ("10-20 tao", "sampu hanggang dalawampu tao"),
    # dates (month first) and Spanish clock times
    ("11/19/2026", "ikalabinsiyam ng nobyembre , dalawang libo at dalawampu't anim"),
    ("Nobyembre 1, 2026", "una ng nobyembre , dalawang libo at dalawampu't anim"),
    ("19 Nob. 2026", "ikalabinsiyam ng nobyembre , dalawang libo at dalawampu't anim"),
    ("2026-06-12", "ikalabindalawa ng hunyo , dalawang libo at dalawampu't anim"),
    ("1:00", "ala una"), ("alas 3:30 ng hapon", "alas tres i medya ng hapon"),
    ("14:15", "alas dos i kinse ng hapon"), ("19:45", "alas siyete i kuwarenta'y singko ng gabi"),
    ("8:05 a.m.", "alas otso i singko ng umaga"), ("0:10", "alas dose i diyes ng hatinggabi"),
    # money: Spanish for whole pesos up to 999, native otherwise
    ("₱50 lang", "singkuwenta pesos lang"), ("PHP 250", "dos siyentos singkuwenta pesos"),
    ("₱1", "isang piso"), ("₱1,500", "isang libo at limang daang piso"),
    ("₱12.50", "labindalawang piso at limampung sentimo"), ("$20", "dalawampung dolyar"),
    # percent, units, ordinals, phone numbers
    ("15%", "labinlimang porsiyento"), ("5 km", "limang kilometro"), ("2 kg", "dalawang kilo"),
    ("34°C", "tatlumpu't apat na digri selsiyus"),
    ("ika-3 puwesto", "ikatlong puwesto"), ("Ika-1", "una"),
    ("0917-123-4567", "sero siyam isa pito isa dalawa tatlo apat lima anim pito"),
    # hyphen before a vowel: glottal stop; other hyphens split
    ("mag-aral tayo", "mag'aral tayo"), ("araw-araw", "araw araw"),
    # codes, acronyms, abbreviations, symbols
    ("DOH at NBI", "di o eyts at en bi ay"), ("ESP32-P4", "i es pi tatlo dalawa pi apat"),
    ("Gng. Santos, Brgy. San Roque atbp.", "ginang santos , barangay san roque at iba pa ."),
    ("Juan & Maria", "juan at maria"),
])
def test_normalize_tl(text, out):
    assert normalize_tl(text) == out


def test_no_digits_left():
    for text in ["1", "123456789012345678", "3.5%", "ika-2", "10:00", "99 km", "₱0.50", "1,234,567.89"]:
        assert not any(ch.isdigit() for ch in normalize_tl(text)), text
