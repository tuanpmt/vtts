"""Burmese front-end (my/): Zawgyi, normalization, syllables, tones, text_to_ids(text, "my")."""

import pytest

from vtts.frontend import phoneme_set as ps
from vtts.frontend.lang import split_sentences_raw, tag_words, word_lang
from vtts.frontend.my.g2p_my import run_phones, syllable_tokens, syllables, unreadable_my
from vtts.frontend.my.normalize_my import cardinal, is_burmese_word, normalize_my
from vtts.frontend.my.zawgyi import canonical_order, is_zawgyi, to_unicode, zawgyi_to_unicode
from vtts.frontend.text import text_to_ids, text_to_tokens


def read(text):
    return " . ".join(" ".join(p) for p in run_phones(text))


def flat(text):
    return [t for ch in text_to_tokens(text, "my") for t in ch]


def test_token_set_myen():
    assert ps.TOKENS_MYEN[:107] == ps.TOKENS_V2
    assert len(set(ps.TOKENS_MYEN)) == len(ps.TOKENS_MYEN) == ps.VOCAB_SIZE_MYEN == 160
    assert ps.PAIR_MODES["my"] == ps.TOKEN_SET_MYEN == "my-en"
    idx = ps.token_index("my-en")
    assert idx["MY:I:k"] == 107 and idx["MY:T4"] == 159


@pytest.mark.parametrize("zawgyi, unicode", [
    ("ေျပာပါတယ္", "ပြောပါတယ်"),
    ("ျမန္မာႏုိင္ငံေစ်းကြက္အတြင္းသုိ႔", "မြန်မာနိုင်ငံဈေးကွက်အတွင်းသို့"),
    ("အဂၤါေန႔က", "အင်္ဂါနေ့က"),
    ("ႏိုင္ငံျခားေရး၀န္ႀကီး", "နိုင်ငံခြားရေးဝန်ကြီး"),
    ("၎တို႔၏", "၎င်းတို့၏"),
    ("ကမာၻလွည့္ခရီးသည္", "ကမ္ဘာလှည့်ခရီးသည်"),
])
def test_zawgyi(zawgyi, unicode):
    assert is_zawgyi(zawgyi) and not is_zawgyi(unicode)
    assert zawgyi_to_unicode(zawgyi) == unicode == to_unicode(zawgyi) == to_unicode(unicode)


def test_canonical_order_keeps_special_spellings():
    assert canonical_order("ကျွန်ုပ်") == "ကျွန်ုပ်"     # marks after ် stay after it
    assert canonical_order("ယောက်ျား") == "ယောက်ျား"
    assert canonical_order("ဖွ့ံ") == "ဖွံ့"             # ံ before ့
    assert canonical_order("ခဲဲ့") == "ခဲ့"               # a repeated mark is dropped


@pytest.mark.parametrize("n, words", [
    (0, "သုည"), (1, "တစ်"), (10, "တစ်ဆယ်"), (21, "နှစ်ဆယ့်တစ်"), (100, "တစ်ရာ"),
    (110, "တစ်ရာ့တစ်ဆယ်"), (2026, "နှစ်ထောင့်နှစ်ဆယ့်ခြောက်"), (15000, "တစ်သောင်းငါးထောင်"),
    (300000, "သုံးသိန်း"), (1_000_000, "တစ်သန်း"), (25_000_000, "နှစ်ဆယ့်ငါးသန်း"), (-5, "အနုတ်ငါး"),
])
def test_cardinal(n, words):
    assert cardinal(n) == words


@pytest.mark.parametrize("text, out", [
    ("အသက် ၂၅ နှစ်။", "အသက်နှစ်ဆယ့်ငါးနှစ် ."),
    ("၁၉၅၄ဝဝဝ ယောက်", "တစ်သန်းကိုးသိန်းငါးသောင်းလေးထောင်ယောက်"),   # ဝ written for zero
    ("၅ဝန်ကြီး", "ငါးဝန်ကြီး"),                                        # ဝန် is not a zero
    ("19/11/2026", "နှစ်ထောင့်နှစ်ဆယ့်ခြောက်ခုနှစ် နိုဝင်ဘာလ တစ်ဆယ့်ကိုးရက်"),
    ("14:30", "တစ်ဆယ့်လေးနာရီသုံးဆယ်မိနစ်"),
    ("$5 နဲ့ 5000 Ks", "ငါးဒေါ်လာနဲ့ငါးထောင်ကျပ်"),
    ("50%", "ငါးဆယ်ရာခိုင်နှုန်း"),
    ("3.14", "သုံးဒသမ တစ်လေး"),
    ("10-20", "တစ်ဆယ်မှနှစ်ဆယ်"),
    ("ဟုတ်ကဲ့၊ ရပါတယ်", "ဟုတ်ကဲ့ , ရပါတယ်"),
    ("ဖွင့် ESP32", "ဖွင့် e s p သုံးနှစ်"),
    ("ေျပာပါတယ္", "ပြောပါတယ်"),                                        # Zawgyi
])
def test_normalize(text, out):
    assert normalize_my(text) == out


@pytest.mark.parametrize("word, reading", [
    ("မြန်မာ", "m G:y a N T1 . m a T1"),
    ("ကျွန်တော်", "k G:y U N T1 . t O T1"),        # ွန် = ʊN, ော် low
    ("မင်္ဂလာပါ", "m I N T1 . g @ . l a T1 . p a T1"),  # kinzi, reduced vowel inside a run
    ("ကမ္ဘာ", "k a N T1 . b a T1"),                  # stack
    ("ကလေး", "k @ . l e T2"),
    ("ပထမ", "p @ . th @ . m a T3"),                  # a̰ at the end of a run
    ("သူက", "T u T1 . k a T3"),                      # particle after a full syllable
    ("ကိုယ်", "k o T1"), ("ကြောင်း", "k G:y au N T2"), ("တိုက်", "t ai ? T4"),
    ("ရှိ", "S i T3"), ("နှင့်", "hn I N T3"), ("ပြည်", "p G:y i T1"), ("လည်း", "l E T2"),
    ("ဝန်", "w U N T1"), ("ကျွန်ုပ်", "k G:y U N T1 . n ou ? T4"),
    ("၏", "? i T3"), ("၎င်း", "l @ . g au N T2"),
])
def test_readings(word, reading):
    assert read(word) == reading


def test_syllables_and_tokens():
    assert [s.text for s in syllables("ကျောင်းသား")] == ["ကျောင်း", "သား"]
    assert syllable_tokens(["k", "G:y", "au", "N", "T2"]) == ["MY:I:k", "MY:M:y", "MY:V:au", "MY:F:N",
                                                              "MY:T2"]
    assert syllable_tokens(["?", "@"]) == ["MY:I:?", "MY:V:@"]


def test_text_to_ids_my():
    assert tag_words("ဖွင့်Wi-Fiပေးပါ", "my") == [("ဖွင့်", "my"), ("Wi-Fi", "en"), ("ပေးပါ", "my")]
    assert word_lang("ေျပာ", "my") == "my" and word_lang("hello", "my") == "en"
    assert word_lang("မြန်မာ", "km") == "neutral" and word_lang("မြန်မာ", "vi") == "vi"
    assert split_sentences_raw("ဟုတ်ကဲ့။ရပါတယ်။") == ["ဟုတ်ကဲ့။", "ရပါတယ်။"]
    toks = flat("Wi-Fi ကို ဖွင့်ပေးပါ။")
    assert "EN:W" in toks and toks[-1] == "." and "MY:I:ph" in toks
    assert flat("ေျပာပါတယ္") == flat("ပြောပါတယ်")
    ids = [i for ch in text_to_ids("YouTube ဖွင့်ပေးပါ", "my") for i in ch]
    assert max(ids) < len(ps.TOKENS_MYEN) and any(i >= ps.VOCAB_SIZE_V2 for i in ids)
    assert text_to_ids("Turn on the Wi-Fi.", "my") == text_to_ids("Turn on the Wi-Fi.", "en")
    chunks = text_to_tokens("မြန်မာနိုင်ငံသည် အရှေ့တောင်အာရှတွင် တည်ရှိသည်" * 8, "my")
    assert len(chunks) > 1 and all(len(c) + 2 <= 320 for c in chunks)


def test_unreadable_and_words():
    assert unreadable_my("မင်္ဂလာပါ Москва") and not unreadable_my("မင်္ဂလာပါ Café ၅")
    assert is_burmese_word("၎င်း") and not is_burmese_word("၁၂")
