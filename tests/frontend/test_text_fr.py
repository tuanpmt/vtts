"""text_to_ids(text, "fr"): French + English, token set fr-en."""

import pytest

from vtts.frontend.lang import tag_words, word_lang
from vtts.frontend.phoneme_set import TOKENS_FREN, VOCAB_SIZE_V2, token_index
from vtts.frontend.text import text_to_ids, text_to_tokens


def flat(text, lang="fr"):
    return [t for ch in text_to_tokens(text, lang) for t in ch]


def ph(text):
    return " ".join("_" if t == " " else t.removeprefix("FR:") for t in flat(text))


def test_tagging_french_and_english_words():
    assert tag_words("Ouvre GitHub et cherche le projet.", "fr") == [
        ("Ouvre", "fr"), ("GitHub", "en"), ("et", "fr"), ("cherche", "fr"), ("le", "fr"),
        ("projet.", "fr")]
    assert tag_words("J'ouvre l'iPhone.", "fr") == [("J'ouvre", "fr"), ("l'", "fr"),
                                                    ("iPhone.", "en")]
    assert tag_words("ESP32-P4 avec USB", "fr") == [
        ("ESP32-P4", "neutral"), ("avec", "fr"), ("USB", "fr")]
    assert tag_words("Le XIXe siècle", "fr")[1] == ("XIXe", "neutral")


@pytest.mark.parametrize("word, lang", [
    ("école", "fr"), ("ça", "fr"), ("Noël", "fr"), ("on", "fr"), ("comment", "fr"), ("six", "fr"),
    ("maison", "fr"), ("bonjour", "fr"), ("Paris", "fr"), ("Jean-Pierre", "fr"), ("a-t-il", "fr"),
    ("vingt-deux", "fr"), ("aujourd'hui", "fr"), ("l'ami", "fr"),
    ("update", "en"), ("online", "en"), ("weekend", "en"), ("the", "en"), ("laptop", "en"),
    ("YouTube", "en"), ("Spotify", "en"), ("Wi-Fi", "en"), ("smartwatch", "en"),
])
def test_word_lang(word, lang):
    got = tag_words(word, "fr")
    assert len(got) == 1 and got[0][1] == lang


def test_french_sentence_with_liaison_and_elision():
    assert ph("Les amis sont là.") == "l e _ z a m i _ s on _ l a ."
    assert ph("L'école.") == "l e k O l ."
    assert "EN:" not in " ".join(flat("Les enfants jouent dans le jardin de leur grand-mère."))


def test_mixed_fr_en():
    toks = flat("Je fais la mise à jour du software.")
    assert "EN:AO" in toks and "FR:zh" in toks and toks[-1] == "."
    assert flat("Le laptop est lent.").count(" ") == 3
    assert flat("l'iPhone")[0] == "FR:l"


def test_numbers_and_codes_in_french():
    assert flat("J'ai 21 ans.") == flat("J'ai vingt et un ans.")
    assert flat("à 14 h 30") == flat("à quatorze heures trente")
    assert flat("ESP32") == flat("eu èss pé trois deux")


def test_ids_use_fren_set_and_english_ids_match_v2():
    ids = text_to_ids("Ouvre YouTube, s'il te plaît.", "fr")
    flat_ids = [i for ch in ids for i in ch]
    idx = token_index("fr-en")
    assert ids[0][0] == idx["<bos>"] and ids[0][-1] == idx["<eos>"]
    assert any(i >= VOCAB_SIZE_V2 for i in flat_ids) and max(flat_ids) < len(TOKENS_FREN)
    assert text_to_ids("Please check the light.", "en") == text_to_ids("Please check the light.", "fr")


def test_other_modes_unchanged_by_french():
    for mode in ("vi", "en", "auto", "es", "pt"):
        ids = [i for ch in text_to_ids("Ça, l'école, garçon", mode) for i in ch]
        assert max(ids) < 150
    assert word_lang("garçon", "es") == "neutral"  # ç is not Spanish: read in es
    assert word_lang("garçon", "vi") == "vi"


def test_long_french_text_is_chunked():
    one = "le chien de mon voisin court dans le parc tous les matins du dimanche"
    text = " ".join([one] * 12) + "."
    chunks = text_to_tokens(text, "fr")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)
