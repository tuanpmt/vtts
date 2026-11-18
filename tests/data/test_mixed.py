import re

import pytest

from vtts.data.mixed import load_templates, load_terms, mixed_rows

LANGS = ("zh", "ko", "ja")


@pytest.mark.parametrize("lang", LANGS)
def test_templates_have_one_slot(lang):
    temps = load_templates(lang)
    assert len(temps) == 40 and len(set(temps)) == 40
    assert all(t.count("{T}") == 1 for t in temps)


def test_korean_no_variable_particle_after_term():
    # 을/를, 이/가, 은/는, 와/과, (으)로 depend on the last sound of the term; only invariant
    # particles (에, 에서, 의, 도, 만, 보다, 부터, 하고 ...) or a space may follow {T}.
    bad = re.compile(r"\{T\}(을|를|이|가|은|는|와|과|으로|로)")
    assert not [t for t in load_templates("ko") if bad.search(t)]


@pytest.mark.parametrize("lang", LANGS)
def test_every_sentence_reads_in_the_pair_token_set(lang):
    from vtts.frontend.ja.g2p_ja import unreadable_ja
    from vtts.frontend.ko.g2p_ko import unreadable_ko
    from vtts.frontend.phoneme_set import PUNCTUATION
    from vtts.frontend.text import text_to_ids, text_to_tokens
    from vtts.frontend.zh.g2p_zh import unknown_han

    unreadable = {"zh": unknown_han, "ko": unreadable_ko, "ja": unreadable_ja}[lang]
    for tp in load_templates(lang):
        for tm in load_terms():
            s = tp.replace("{T}", tm)
            chunks = text_to_tokens(s, lang)
            assert chunks and all(any(t not in PUNCTUATION for t in c) for c in chunks), s
            assert not unreadable(s), s
            text_to_ids(s, lang)  # every token has an id in the pair set


@pytest.mark.parametrize("lang,prefix", [("zh", "zm"), ("ko", "km"), ("ja", "jm")])
def test_rows_ids_lang_and_budget(lang, prefix):
    rows, total = mixed_rows(lang, hours=0.1, seed=0)
    assert rows and all(r["lang"] == lang for r in rows)
    assert rows[0]["id"] == f"{prefix}000000" and len({r["id"] for r in rows}) == len(rows)
    assert 360 <= total < 360 + 30
    assert mixed_rows(lang, hours=0.1, seed=0)[0] == rows  # deterministic


def test_zh_rows_match_former_build_zh_mixed():
    import random

    from vtts.data.zh_corpus import han_count

    terms, temps = load_terms(), load_templates("zh")
    combos = [(tp.replace("{T}", tm), tm) for tp in temps for tm in terms]
    random.Random(0).shuffle(combos)
    old, total = [], 0.0
    for s, tm in combos:
        if total >= 0.2 * 3600:
            break
        old.append({"id": f"zm{len(old):06d}", "text": s, "lang": "zh"})
        total += han_count(s) / 4.5 + len(tm.split()) / 2.6
    assert mixed_rows("zh", hours=0.2, seed=0)[0] == old
