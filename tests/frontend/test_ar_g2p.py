"""Token set ar-en and the Arabic word reader (ar/g2p_ar.py): vowelled reading, vowel
restoration (lexicon, clitics, endings, patterns), stress."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.ar.g2p_ar import (
    PHONEMES,
    is_arabic_word,
    lexicon,
    pattern_vocalize,
    phonemes,
    read_vocalized,
    spelling_table,
    strip_marks,
    unreadable_ar,
    vocalize,
    word_tokens_ar,
)


def rd(word):
    return " ".join(read_vocalized(word))


def ph(word):
    return " ".join(p.rstrip("1") for p in phonemes(word))


def test_token_set_aren_extends_v2():
    assert ps.TOKENS_AREN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_AREN[107:]
    assert all(t.startswith("AR:") for t in block)
    assert len(block) == len(set(block)) == 42 and ps.VOCAB_SIZE_AREN == 149
    assert ps.TOKEN_SETS[ps.TOKEN_SET_AREN] is ps.TOKENS_AREN and ps.TOKEN_SET_AREN == "ar-en"
    assert ps.PAIR_MODES["ar"] == "ar-en"
    idx = ps.token_index("ar-en")
    assert idx["AR:?"] == 107 and idx["AR:a"] == 137 and idx["AR:a1"] == 143
    assert {t[3:] for t in block} == set(PHONEMES)


@pytest.mark.parametrize("word, expected", [
    # short and long vowels, sukun, shadda
    ("كَتَبَ", "k a t a b"), ("كِتَابٌ", "k i t aa b"), ("مُدَرِّسٌ", "m u d a r r i s"),
    ("بَيْت", "b a y t"), ("يَوْم", "y a w m"), ("سُور", "s uu r"), ("دِين", "d ii n"),
    # article: moon and sun letters, after proclitics, لل
    ("الْقَمَر", "a l q a m a r"), ("الشَّمْس", "a sh sh a m s"), ("الشَمْس", "a sh sh a m s"),
    ("وَالْقَمَر", "w a l q a m a r"), ("بِالشَّمْس", "b i sh sh a m s"),
    ("لِلْكِتَاب", "l i l k i t aa b"), ("الِاتِّحَاد", "a l i t t i H aa d"),
    # hamza forms, madda, alif maqsura, ta marbuta, dagger alif
    ("أَكَلَ", "? a k a l"), ("إِسْلَام", "? i s l aa m"), ("سُؤَال", "s u ? aa l"),
    ("سَائِل", "s aa ? i l"), ("شَيْء", "sh a y ?"), ("آخِر", "? aa x i r"),
    ("عَلَى", "3 a l aa"), ("مَدْرَسَةٌ", "m a d r a s a"), ("هٰذَا", "h aa dh aa"),
    # tanwin in pausal form: -un/-in dropped, -an written with alif is aa
    ("شُكْرًا", "sh u k r aa"), ("كِتَابٍ", "k i t aa b"),
    # hamzat al-wasl at the start, nisba in pause
    ("اِسْتِخْدَام", "i s t i x d aa m"), ("عَرَبِيّ", "3 a r a b ii"),
    # two-letter words keep their final vowel
    ("هُوَ", "h u w a"), ("مَعَ", "m a 3 a"),
])
def test_read_vocalized(word, expected):
    assert rd(word) == expected


def test_strip_marks_and_script():
    assert strip_marks("الْكِتَابُ") == "الكتاب"
    assert strip_marks("عـربي") == "عربي"
    assert is_arabic_word("كتاب،") and not is_arabic_word("٢٠٢٤") and not is_arabic_word("Wi-Fi")


@pytest.mark.parametrize("word, expected", [
    ("كتاب", "k i t aa b"), ("الكتاب", "a l k i t aa b"), ("والكتاب", "w a l k i t aa b"),
    ("بالكتاب", "b i l k i t aa b"), ("للكتاب", "l i l k i t aa b"),
    ("الشمس", "a sh sh a m s"), ("مدينة", "m a d ii n a"),
    ("حكومات", "H u k uu m aa t"),  # حكومة + ات
    ("الدولية", "a d d a w l i y y a"),  # دولة -> دولي + ية
    ("عربية", "3 a r a b i y y a"),
    ("كتابه", "k i t aa b i h"), ("عليها", "3 a l a y h aa"), ("منهم", "m i n h u m"),
    ("وكان", "w a k aa n"), ("أن", "? a n n a"), ("من", "m i n"), ("في", "f ii"),
    ("هذا", "h aa dh aa"), ("وهذا", "w a h aa dh aa"), ("الله", "a l l aa h"),
    ("لكن", "l aa k i n"), ("اكثر", "? a k t h a r".replace("t h", "th")),  # unseated hamza
    ("الوطنى", "a l w a T a n ii"),  # final ي written ى
])
def test_vocalize_unvowelled(word, expected):
    assert ph(word) == expected


@pytest.mark.parametrize("word, expected", [
    ("مكتوب", "m a k t uu b"),  # maf'uul
    ("كاتب", "k aa t i b"),  # faa'il
    ("استقبال", "i s t i q b aa l"),  # istif'aal
    ("انتقال", "i n t i q aa l"),  # infi'aal
    ("اجتماع", "i j t i m aa 3"),  # ifti'aal
    ("تدريب", "t a d r ii b"),  # taf'iil
    ("مدارس", "m u d aa r i s"),  # mufaa'il (مدارس itself is listed as madaaris)
    ("فيسبوك", "f ii s b uu k"), ("دارفور", "d aa r f uu r"),  # default: closed syllables
    ("رسميا", "r a s m i y y aa"),  # nisba adverb -iyyan
])
def test_patterns_and_default(word, expected):
    assert rd(pattern_vocalize(word)) == expected  # the rules alone (no lexicon)


def test_stress():
    assert phonemes("كتاب") == ("k", "i", "t", "aa1", "b")  # final superheavy
    assert phonemes("مدرسة") == ("m", "a1", "d", "r", "a", "s", "a")  # antepenult
    assert phonemes("كبير") == ("k", "a", "b", "ii1", "r")
    assert phonemes("من") == ("m", "i", "n")  # one syllable: unstressed
    assert sum(p.endswith("1") for p in phonemes("الاستقلال")) == 1


def test_lexicon_tables_are_wellformed():
    lex = lexicon()
    assert len(lex) > 1900
    for key, value in lex.items():
        assert strip_marks(value) == key, key
        assert read_vocalized(value), key
    for key, value in spelling_table().items():
        assert vocalize(key) == value


def test_tokens_and_unreadable():
    toks = word_tokens_ar("كتاب")
    assert toks and all(t in ps.token_index("ar-en") for t in toks)
    assert unreadable_ar("مرحبا Москва") and not unreadable_ar("مرحبا François، Wi-Fi ١٢")
