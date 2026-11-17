"""VLEX: the English lexicon + letter-to-sound blob for the device front-end."""

import random
import string

from vtts.frontend.en.cmudict import load_cmudict
from vtts.frontend.en.lts import LtsModel, load_lts, prune_table
from vtts.frontend.en.vlex import build_vlex, read_vlex
from vtts.frontend.phoneme_set import token_to_id_v2


def _ids(toks):
    return [token_to_id_v2(t) for t in toks]


def test_prune_is_lossless_on_sample():
    full = load_lts()
    pruned = LtsModel(prune_table(full.table))
    assert len(pruned.table) < len(full.table) // 5
    words = list(load_cmudict())[::50]
    rnd = random.Random(0)
    words += ["".join(rnd.choice(string.ascii_lowercase) for _ in range(rnd.randint(1, 10))) for _ in range(3000)]
    assert all(full.labels(w) == pruned.labels(w) for w in words)


def test_roundtrip_lexicon_and_lts():
    lex = load_cmudict()
    blob = build_vlex()
    v = read_vlex(blob)
    rnd = random.Random(0)
    for w in rnd.sample(sorted(lex), 3000):
        assert v.lookup(w) == _ids(lex[w]), w
    for w in ("zzqx", "vttsish", "blorptastic"):
        assert w not in lex and v.lookup(w) is None
        assert v.predict(w) == _ids(load_lts().predict(w)), w


def test_blob_size_budget():
    assert len(build_vlex()) <= 1_900_000  # lexicon ~1.5 MB + pruned letter-to-sound ~0.35 MB
