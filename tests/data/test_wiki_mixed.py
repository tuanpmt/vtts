import re

import pytest

from vtts.data.mixed import ID_PREFIX, TEMPLATE_DIR, load_templates, mixed_rows
from vtts.data.wiki_corpus import LATIN_LETTERS

LANGS = ("es", "id", "pt", "th", "hi")
PLAIN = {
    **{lang: re.compile(rf"^[{letters} ,.?!¿¡\-]+$") for lang, letters in LATIN_LETTERS.items()},
    "th": re.compile(r"^[ก-ฮะ-ฺเ-๎ ]+$"),
    "hi": re.compile(r"^[ऀ-ॣॱ-ॿ ,.?!]+$"),
}
AVAILABLE = [lang for lang in LANGS if (TEMPLATE_DIR / f"templates_{lang}.txt").exists()]


@pytest.mark.parametrize("lang", AVAILABLE)
def test_templates_one_slot_plain_text(lang):
    temps = load_templates(lang)
    assert 60 <= len(temps) <= 100 and len(set(temps)) == len(temps)
    for t in temps:
        assert t.count("{T}") == 1, t
        assert PLAIN[lang].match(t.replace("{T}", "x" if lang in LATIN_LETTERS else "")), t
        assert "  " not in t and t == t.strip(), t
        if lang != "th":
            assert t[-1] in ".?!", t
        if lang == "es":
            assert ("¿" in t) == ("?" in t), t


def test_prefixes_unique():
    prefixes = set(ID_PREFIX.values())
    assert len(prefixes) == len(ID_PREFIX)
    assert not prefixes & {"vi", "en", "mx", *ID_PREFIX}


@pytest.mark.parametrize("lang", AVAILABLE)
def test_rows(lang):
    rows, total = mixed_rows(lang, hours=0.1, seed=0)
    assert rows[0]["id"] == f"{ID_PREFIX[lang]}000000" and all(r["lang"] == lang for r in rows)
    assert len({r["id"] for r in rows}) == len(rows) and 360 <= total < 400
