"""Token set ru-en and the Russian rules (ru/g2p_ru.py): stress, spelling, reduction, voicing."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lexicons import load_table
from vtts.frontend.ru.g2p_ru import (
    _stress_words,
    _suffixes,
    phonemes,
    stress_source,
    stressed,
    unreadable_ru,
    word_tokens_ru,
)


def test_token_set_ruen_extends_v2():
    assert ps.TOKENS_RUEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_RUEN[107:]
    assert all(t.startswith("RU:") for t in block)
    assert len(block) == len(set(block)) == 47 and ps.VOCAB_SIZE_RUEN == 154
    assert ps.TOKEN_SETS[ps.TOKEN_SET_RUEN] is ps.TOKENS_RUEN and ps.PAIR_MODES["ru"] == "ru-en"
    idx = ps.token_index("ru-en")
    assert idx["RU:a"] == 107 and idx["RU:a1"] == 112 and idx["RU:p"] == 118 and idx["RU:p'"] == 133
    assert idx["EN:AA"] == 65


def test_every_phoneme_is_a_token():
    inventory = {t[3:] for t in ps.TOKENS_RUEN[107:]}
    text = ("молоко ещё хорошо съезд объявление семья жена шёл цирк чай щука ёлка юбка яблоко "
            "этаж мыло пятьдесят здравствуйте счастье солнце чувство детский учиться хлеб друг "
            "мягкий вокзал сделать гиря хижина кефир эхо")
    seen = set()
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w
        seen |= set(phonemes(w))
    assert len(seen) >= 40


@pytest.mark.parametrize("word, ph", [
    # vowel reduction: a in the syllable before the stress and at the start, @ elsewhere
    ("молоко", "m @ l a k o1"), ("хорошо", "x @ r a sh o1"), ("окно", "a k n o1"),
    ("голова", "g @ l a v a1"),
    # ikanye after soft consonants; final unstressed я after a soft consonant is @
    ("язык", "j i z y1 k"), ("весна", "v' i s n a1"), ("время", "v r' e1 m' @"),
    ("часы", "ch i s y1"), ("пятно", "p' i t n o1"),
    # ж ш ц hard: и -> ы, unstressed е -> ы
    ("жена", "zh y n a1"), ("шина", "sh y1 n @"), ("цирк", "ts y1 r k"),
    # ё is always stressed, also when written е (stress table)
    ("ещё", "j i shch o1"), ("еще", "j i shch o1"), ("её", "j i j o1"),
    # j: start of a word, after a vowel, after ь and ъ
    ("яблоко", "j a1 b l @ k @"), ("семья", "s' i m' j a1"), ("объём", "a b j o1 m"),
    ("этаж", "i t a1 sh"),
    # spelling rules
    ("его", "j i v o1"), ("нового", "n o1 v @ v @"), ("сегодня", "s' i v o1 d n' @"),
    ("что", "sh t o1"), ("конечно", "k a n' e1 sh n @"), ("чувство", "ch u1 s t v @"),
    ("солнце", "s o1 n ts y"), ("счастье", "shch a1 s t' j i"), ("учиться", "u ch i1 ts @"),
    ("детский", "d' e1 ts k' i j"), ("мягкий", "m' a1 x k' i j"),
    ("здравствуйте", "z d r a1 s t v u j t' i"),
    # voicing assimilation and final devoicing; в does not voice what comes before it
    ("сделать", "z' d' e1 l @ t'"), ("вокзал", "v a g z a1 l"), ("сказка", "s k a1 s k @"),
    ("дуб", "d u1 p"), ("хлеб", "x l' e1 p"), ("друг", "d r u1 k"), ("свет", "s v' e1 t"),
    ("вкус", "f k u1 s"),
    # softness before a soft dental with a vowel after it; not at the end of a word
    ("кости", "k o1 s' t' i"), ("есть", "j e1 s t'"),
    # clitics joined by the normalizer, hyphenated words
    ("в-доме", "v d o1 m' i"), ("к-другу", "g d r u1 g u"), ("кто-то", "k t o1 t a"),
    # hand-written overrides (homographs, source errors)
    ("после", "p o1 s l' i"), ("дела", "d' i l a1"),
])
def test_word_phonemes(word, ph):
    assert " ".join(phonemes(word)) == ph


def test_stress_sources():
    assert stress_source("ещё") == "marked" and stressed("ещё") == "ещ+ё"
    assert stress_source("после") == "overrides"
    assert stress_source("еще") == "stress" and stressed("еще") == "ещ+ё"  # ё restored
    assert stress_source("на") == "none" and stressed("на") == "на"
    assert stress_source("дом") == "one"
    assert stress_source("книгами") == "suffix" and stressed("книгами") == "кн+игами"
    assert stressed("молок+о") == "молок+о"  # an explicit mark wins


def test_tables_are_consistent():
    words = _stress_words()
    assert len(words) > 10000 and all(v.count("+") == 1 for v in words.values())
    assert all(k == v.replace("+", "").replace("ё", "е") for k, v in words.items())
    suffixes, longest = _suffixes()
    assert "" in suffixes and longest <= 7 and len(suffixes) > 10000
    overrides = load_table("ru", "overrides")
    for k, v in overrides.items():  # each override differs from what the tables would give
        assert k == v.replace("+", "").replace("ё", "е") and v.count("+") == 1, k
        assert words.get(k) != v, k


def test_word_tokens_spell_vowelless_words():
    spelled = [t for n in ("ка", "пэ", "эс", "эс") for t in word_tokens_ru(n)]
    assert word_tokens_ru("кпсс") == spelled
    assert word_tokens_ru("в") == ["RU:f"]  # a lone preposition is not spelled
    assert all(t.startswith("RU:") for t in word_tokens_ru("Привет"))


def test_other_cyrillic_letters_are_folded():
    assert phonemes("Київ") == phonemes("кийив")
    assert unreadable_ru("Привет, Київ, Café") == []
    assert unreadable_ru("Привет नमस्ते")
