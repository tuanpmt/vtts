from vtts.frontend.en.cmudict import load_cmudict
from vtts.frontend.en.g2p_en import g2p_word_en, letter_tokens


def ph(tokens):
    return " ".join(t[3:] if t.startswith("EN:") else t for t in tokens)


def test_lexicon_word():
    assert g2p_word_en("Hello") == load_cmudict()["hello"]


def test_possessive_and_plural():
    assert g2p_word_en("Apple's") == load_cmudict()["apple"] + ["EN:Z"]
    assert ph(g2p_word_en("bluetooths")).endswith("TH S")


def test_acronym_is_spelled():
    assert g2p_word_en("USB") == letter_tokens("u") + letter_tokens("s") + letter_tokens("b")
    assert ph(letter_tokens("w")) == "D AH S1 B AH S0 L Y UW S0"


def test_camel_case_and_compound():
    assert ph(g2p_word_en("AirPods")).startswith("EH S1 R P AA S2 D Z")
    chat = load_cmudict()["chat"]
    assert g2p_word_en("ChatGPT")[: len(chat)] == chat
    assert ph(g2p_word_en("smartwatches")) == "S M AA S1 R T W AA S2 CH AH S0 Z"
    assert ph(g2p_word_en("bluetoothed")).endswith("TH T")


def test_hyphenated_and_unknown():
    assert ph(g2p_word_en("Wi-Fi")) == "W AY S1 F AY S2"
    lex = load_cmudict()
    demoted = ["S2" if t == "S1" else t for t in lex["orange"]]
    assert g2p_word_en("purple-orange") == lex["purple"] + demoted
    out = g2p_word_en("zzyzx")
    assert out and out.count("S1") == 1


def test_one_primary_stress_in_compounds():
    assert g2p_word_en("AirPods").count("S1") == 1
