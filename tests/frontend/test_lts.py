import random

from vtts.frontend.en.cmudict import load_cmudict
from vtts.frontend.en.lts import LtsModel, align, em_align, train_lts


def _strip(tokens):
    return [t for t in tokens if not t.startswith("S")]


def _edits(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
    return d[len(b)]


def test_align_maps_each_letter():
    lex = load_cmudict()
    pairs = [(w, [t[3:] for t in lex[w] if t.startswith("EN:")]) for w in list(lex)[:20000] if w.isalpha()]
    table = em_align(pairs)
    assert [lab for _, lab in align("box", ["B", "AA", "K", "S"], table)] == ["B", "AA", "K S"]
    assert [lab for _, lab in align("knee", ["N", "IY"], table)][0] == "_"


def test_one_primary_stress_and_tokens():
    m = LtsModel({"": {}}, default="_")
    toks = m.finish(["EN:K", "EN:AE", "S2", "EN:T", "EN:AH", "S2"])
    assert toks.count("S1") == 1 and toks[2] == "S1"


def test_heldout_phoneme_error_rate():
    lex = load_cmudict()
    words = sorted(w for w in lex if w.isalpha())
    rng = random.Random(0)
    test = set(rng.sample(words, 2000))
    model = train_lts({w: lex[w] for w in words if w not in test})
    err = sum(_edits(_strip(model.predict(w)), _strip(lex[w])) for w in test)
    total = sum(len(_strip(lex[w])) for w in test)
    assert err / total <= 0.15
    assert model.predict("cat") == ["EN:K", "EN:AE", "S1", "EN:T"]
