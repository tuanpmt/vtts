import json
import re
from collections import Counter
from pathlib import Path

import pytest

SETS = Path(__file__).resolve().parents[2] / "eval" / "sets"
GROUPS = {"device", "numbers", "names", "questions", "long"}
LATIN_LANGS = ["es"]


def _rows(name):
    return [json.loads(x) for x in (SETS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if x]


def _english_words(text, lang):
    from vtts.frontend.lang import split_sentences_raw, tag_words

    return [w for s in split_sentences_raw(text) for w, t in tag_words(s, lang) if t == "en"]


@pytest.mark.parametrize("lang", ["zh", "ko", "ja", *LATIN_LANGS])
@pytest.mark.parametrize("kind", ["ood", "mixed"])
def test_pair_set_shape_and_front_end(kind, lang):
    from vtts.data.train_list import unreadable
    from vtts.eval.cer import prep_for_cer
    from vtts.frontend.text import text_to_ids

    rows = _rows(f"{kind}_{lang}")
    assert len(rows) == 50 and len({r["id"] for r in rows}) == 50
    assert Counter(r["group"] for r in rows) == {g: 10 for g in GROUPS}
    assert {r["lang"] for r in rows} == {lang}
    latin = re.compile(r"[A-Za-z]")
    for r in rows:
        assert text_to_ids(r["text"], lang), r["text"]
        assert not unreadable(r["text"], lang), r["text"]
        assert prep_for_cer(r["text"], lang)
        if lang in LATIN_LANGS:  # the same letters: English words are those the tagger reads in English
            assert bool(_english_words(r["text"], lang)) == (kind == "mixed"), r["text"]
        else:
            assert bool(latin.search(r["text"])) == (kind == "mixed"), r["text"]
