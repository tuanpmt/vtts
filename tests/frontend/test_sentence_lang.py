"""Sentence language of the Latin-script pair modes and the vi mode (latin.sentence_is_english):
whole English sentences are read in English, sentences of the language with English terms keep
their word-by-word tags."""

import json
from pathlib import Path

import pytest

from vtts.frontend import lang
from vtts.frontend.lang import split_sentences_raw, tag_words
from vtts.frontend.latin import LATIN_PAIRS, sentence_is_english
from vtts.frontend.lexicons import load_words
from vtts.frontend.text import text_to_tokens

SETS = Path(__file__).parents[2] / "eval" / "sets"
ENGLISH = [
    "I have turned on the fan at medium speed.",
    "I am a text-to-speech voice and I can read the time for you.",
    "Set a timer for 25 minutes and remind me to check the oven.",
    "The temperature outside is 28 degrees.",
    "Do you want me to lock the back door?",
]


def _texts(name: str) -> list[str]:
    return [json.loads(line)["text"] for line in (SETS / name).read_text(encoding="utf-8").splitlines()
            if line.strip()]


@pytest.mark.parametrize("mode", ["es", "id", "pt"])
@pytest.mark.parametrize("text", ENGLISH)
def test_english_sentence_reads_as_english(mode, text):
    assert {t for _, t in tag_words(text, mode)} == {"en"}
    # the same tokens as the English mode of the vi-en pair (English words and numbers)
    assert text_to_tokens(text, mode) == text_to_tokens(text, "en")


@pytest.mark.parametrize(("mode", "text", "english"), [
    ("pt", "Abra o Netflix no iPhone e toque em Play.", {"Netflix", "iPhone", "Play."}),
    ("pt", "Ative o dark mode na tela do celular.", {"dark", "mode"}),
    ("es", "Abre Netflix en el iPhone y pon el modo dark mode.", {"Netflix", "iPhone", "dark", "mode."}),
    ("es", "Quiero ver un show en Netflix esta noche.", {"show", "Netflix"}),
    ("id", "Buka Netflix di iPhone lalu tekan Play.", {"Netflix", "iPhone", "Play."}),
    ("id", "Tolong nyalakan Bluetooth di laptop saya.", {"Bluetooth", "laptop"}),
])
def test_main_sentence_with_brand_keeps_word_tags(mode, text, english):
    tags = tag_words(text, mode)
    assert {c for c, t in tags if t == "en"} == english
    assert all(t == mode for c, t in tags if c not in english)


def test_own_letters_stay_in_the_language():
    tags = dict(tag_words("Tomorrow morning we will meet José at the airport and then go to the hotel.", "pt"))
    assert tags["José"] == "pt" and {t for c, t in tags.items() if c != "José"} == {"en"}
    # two words of the language against six English ones: word by word
    tags = dict(tag_words("We met José in São Paulo last year.", "pt"))
    assert tags["José"] == "pt" and tags["São"] == "pt" and tags["year."] == "en"


def test_english_term_alone_or_one_run_is_not_a_sentence():
    # no strong English word (Low Power Mode) / the English words form one run (check in)
    assert {t for c, t in tag_words("Eski telefonum Low Power Mode desteklemiyor.", "tr")
            if c in ("Eski", "telefonum", "desteklemiyor.")} == {"tr"}
    assert tag_words("Voitko sammuttaa check in hetkeksi?", "fi")[1] == ("sammuttaa", "fi")


@pytest.mark.parametrize("mode", sorted(LATIN_PAIRS))
def test_eval_sets(mode, monkeypatch):
    """The words of ood_en are read in English but for a few (a sentence of names and numbers), and
    no sentence of the language's own eval sets is decided English."""
    words = bad = 0
    for text in _texts("ood_en.jsonl"):
        for s in split_sentences_raw(text, mode):
            for _, t in tag_words(s, mode):
                if t != "neutral":
                    words += 1
                    bad += t != "en"
    assert bad <= 0.025 * words
    monkeypatch.setattr(lang, "sentence_is_english", lambda *a: False)  # the word-by-word tags
    for name in (f"ood_{mode}.jsonl", f"mixed_{mode}.jsonl"):
        for text in _texts(name):
            for s in split_sentences_raw(text, mode):
                assert not sentence_is_english(tag_words(s, mode), mode, lang._core), s


def test_vi_mode():
    assert {t for _, t in tag_words("Do you want me to lock the back door?", "vi")} == {"en"}
    for s in ("Toi muon mua cai may tinh moi.", "Con meo an ca trong bep.", "Mở Spotify và play playlist nhé."):
        assert any(t == "vi" for _, t in tag_words(s, "vi")), s
    # unaccented Vietnamese: English function words that are also syllables (to, an, may) count for neither
    assert {t for _, t in tag_words("Anh di to may an com", "vi")} == {"vi"}


def test_word_lists():
    english = load_words("latin", "function_en") | load_words("latin", "common_en")
    assert not load_words("latin", "function_en") & load_words("latin", "common_en")
    assert {"the", "you", "and", "i", "a"} <= english
    for mode in LATIN_PAIRS:
        words = load_words(mode, "function")
        assert len(words) >= 50 and all(w.isascii() for w in words), mode
