from vtts.frontend.en.cmudict import arpabet_to_tokens, load_cmudict


def test_arpabet_to_tokens_moves_stress_after_vowel():
    assert arpabet_to_tokens(["HH", "AH0", "L", "OW1"]) == ["EN:HH", "EN:AH", "S0", "EN:L", "EN:OW", "S1"]


def test_lexicon_loads_first_pronunciation():
    lex = load_cmudict()
    assert len(lex) > 120_000
    assert lex["bluetooth"] == ["EN:B", "EN:L", "EN:UW", "S1", "EN:T", "EN:UW", "S2", "EN:TH"]
    assert "hello(2)" not in lex and all(k == k.lower() for k in list(lex)[:1000])
