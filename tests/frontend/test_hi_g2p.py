"""Token set hi-en and Hindi Devanagari-to-phoneme rules (hi/g2p_hi.py)."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.hi.g2p_hi import (
    PHONEMES,
    is_devanagari_word,
    phonemes,
    rule_phonemes,
    unreadable_hi,
    word_tokens_hi,
)
from vtts.frontend.lexicons import load_table


def ph(word):
    return " ".join(phonemes(word))


def test_token_set_hien_extends_v2():
    assert ps.TOKENS_HIEN[:107] == ps.TOKENS_V2
    block = ps.TOKENS_HIEN[107:]
    assert all(t.startswith("HI:") for t in block)
    assert len(block) == len(set(block)) == 50 and ps.VOCAB_SIZE_HIEN == 157
    assert ps.TOKEN_SETS[ps.TOKEN_SET_HIEN] is ps.TOKENS_HIEN and ps.TOKEN_SET_HIEN == "hi-en"
    assert ps.PAIR_MODES["hi"] == "hi-en"
    idx = ps.token_index("hi-en")
    assert idx["HI:a"] == 107 and idx["HI:~"] == 117 and idx["HI:k"] == 118
    assert idx["EN:AA"] == 65 and idx["<eos>"] == 2
    assert {t[3:] for t in block} == set(PHONEMES)


@pytest.mark.parametrize("word, expected", [
    # independent vowels and matras
    ("अ", "a"), ("आम", "aa m"), ("इधर", "i dh a r"), ("ईख", "ii kh"), ("उधर", "u dh a r"),
    ("ऊन", "uu n"), ("एक", "e k"), ("ऐसा", "ai s aa"), ("ओर", "o r"), ("औरत", "au r a t"),
    ("किताब", "k i t aa b"), ("गीत", "g ii t"), ("सुन", "s u n"), ("फूल", "ph uu l"),
    ("देश", "d e sh"), ("पैसा", "p ai s aa"), ("मोर", "m o r"), ("कौन", "k au n"),
    ("कई", "k a ii"), ("गए", "g a e"),
    # loanword vowels ऑ ॅ, ऋ / ृ, ॐ
    ("ऑफ़िस", "au f i s"), ("डॉक्टर", "D au k T a r"), ("बैंक", "b ai ~ k"), ("कृपा", "k r i p aa"),
    ("ऋषि", "r i sh i"), ("ॐ", "o m"),
    # aspirated and retroflex consonants
    ("घर", "gh a r"), ("छत", "ch a t"), ("झील", "jh ii l"), ("ठीक", "Th ii k"), ("ढोल", "Dh o l"),
    ("बाण", "b aa N"), ("थाली", "th aa l ii"), ("धन", "dh a n"), ("फल", "ph a l"),
    ("भाषा", "bh aa sh aa"), ("टमाटर", "T a m aa T a r"),
    # nukta consonants (precomposed and decomposed forms read the same)
    ("क़लम", "q a l a m"), ("ख़ुश", "x u sh"), ("ग़लत", "G a l a t"), ("ज़रूर", "z a r uu r"),
    ("फ़ोन", "f o n"), ("पेड़", "p e R"), ("पढ़ाई", "p a Rh aa ii"),
    ("ड़ा", "R aa"), ("ड़ा", "R aa"),
    # conjuncts with virama
    ("क्या", "k y aa"), ("प्यार", "p y aa r"), ("स्कूल", "s k uu l"), ("नमस्ते", "n a m a s t e"),
    ("पक्का", "p a k k aa"), ("क्षमा", "k sh a m aa"), ("ज्ञान", "g y aa n"),
    ("त्रिशूल", "t r i sh uu l"), ("श्री", "sh r ii"), ("कृष्ण", "k r i sh N"),
    ("हिन्दी", "h i n d ii"),
    # anusvara: homorganic nasal after a short vowel before a stop, else nasalization
    ("हिंदी", "h i n d ii"), ("ठंडा", "Th a N D aa"), ("अंग्रेज़ी", "a ng g r e z ii"),
    ("पंजाब", "p a ny j aa b"), ("संबंध", "s a m b a n dh"), ("मुंबई", "m u m b a ii"),
    ("संसार", "s a ~ s aa r"), ("दांत", "d aa ~ t"), ("में", "m e ~"), ("नहीं", "n a h ii ~"),
    ("हैं", "h ai ~"),
    # chandrabindu
    ("हूँ", "h uu ~"), ("आँख", "aa ~ kh"), ("माँ", "m aa ~"), ("हँसना", "h a ~ s n aa"),
    # visarga
    ("दुःख", "d u h kh"), ("अतः", "a t a h"),
])
def test_letters_matras_conjuncts(word, expected):
    assert ph(word) == expected


@pytest.mark.parametrize("word, expected", [
    # medial schwa deletion: V C _ C V, right to left
    ("कमला", "k a m l aa"), ("समझना", "s a m a jh n aa"), ("अपना", "a p n aa"),
    ("लड़का", "l a R k aa"), ("करना", "k a r n aa"), ("बदलना", "b a d a l n aa"),
    ("उलझन", "u l jh a n"), ("जनता", "j a n t aa"), ("सरकार", "s a r k aa r"),
    ("दशमलव", "d a sh a m l a v"), ("लगभग", "l a g bh a g"), ("मंगलवार", "m a ng g a l v aa r"),
    ("पचहत्तर", "p a c h a t t a r"), ("अड़तालीस", "a R t aa l ii s"),
    # word-final schwa deleted; kept in one-letter words and after a cluster ending in y / r
    ("कमल", "k a m a l"), ("भारत", "bh aa r a t"), ("समय", "s a m a y"), ("न", "n a"),
    ("मित्र", "m i t r a"), ("सत्य", "s a t y a"), ("धर्म", "dh a r m"),
    # a schwa before a cluster stays
    ("मस्तक", "m a s t a k"),
])
def test_schwa_deletion(word, expected):
    assert ph(word) == expected


def test_overrides_table():
    table = load_table("hi", "overrides")
    assert len(table) >= 20
    for word, reading in table.items():
        assert is_devanagari_word(word), word
        assert set(reading.split()) <= set(PHONEMES), (word, reading)
        assert ph(word) == reading
        assert " ".join(rule_phonemes(word)) != reading, f"{word}: the rule already reads it"
    assert ph("उदाहरण") == "u d aa h a r a N"  # the rule would give u d aa h r a N
    assert ph("असफलता") == "a s a ph a l t aa"  # prefix a- + saphal
    assert ph("राष्ट्रपति") == "r aa sh T r a p a t i"  # compound raashTra + pati


def test_every_phoneme_is_a_token_and_tokens_are_prefixed():
    inventory = set(PHONEMES)
    text = ("नमस्ते आप कैसे हैं मैं ठीक हूँ आज मौसम बहुत अच्छा है क़िस्मत ख़बर ग़ज़ल फ़िल्म "
            "पढ़ना बड़ा ज्ञान कृषि दुःख ऑफ़िस संघ पञ्च कण्ठ")
    for w in text.split():
        assert set(phonemes(w)) <= inventory, w
        assert word_tokens_hi(w) == [f"HI:{p}" for p in phonemes(w)]


def test_unreadable():
    assert unreadable_hi("नमस्ते Москва") == list("Москва")
    assert unreadable_hi("नमस्ते, café और Wi-Fi।") == []
    assert unreadable_hi("নমস্কার") != []  # Bengali letters
    assert not is_devanagari_word("abc") and is_devanagari_word("हिंदी")
