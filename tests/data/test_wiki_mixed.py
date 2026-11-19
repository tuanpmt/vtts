import re

import pytest

from vtts.data.mixed import ID_PREFIX, TEMPLATE_DIR, load_templates, mixed_rows
from vtts.data.wiki_corpus import APOSTROPHE, LATIN_LETTERS

LANGS = ("es", "id", "pt", "th", "hi", "fr", "de", "it", "tr", "ru", "pl", "ar", "fi", "el", "ms", "tl", "sw", "nl", "sv", "no", "da", "lo")
JOINS = {lang: "'" for lang in APOSTROPHE}  # it: l'app, dell'ufficio
PLAIN = {
    **{lang: re.compile(rf"^[{letters} ,.?!¿¡\-{JOINS.get(lang, '')}]+$")
       for lang, letters in LATIN_LETTERS.items()},
    "th": re.compile(r"^[ก-ฮะ-ฺเ-๎ ]+$"),
    "hi": re.compile(r"^[ऀ-ॣॱ-ॿ ,.?!]+$"),
    "ru": re.compile(r"^[а-яА-ЯёЁ ,.?!\-]+$"),
    "ar": re.compile(r"^[\u0621-\u063a\u0640-\u064a ،.؟!]+$"),
    "lo": re.compile(r"^[\u0e81-\u0ecd\u0edc-\u0edf ]+$"),
}
PLAIN["el"] = re.compile(rf"^[{LATIN_LETTERS['el']} ,.;!\-]+$")
PLAIN["fr"] = re.compile(rf"^[{LATIN_LETTERS['fr']} ,.?!'\-]+$")  # elision: l'école
AVAILABLE = [lang for lang in LANGS if (TEMPLATE_DIR / f"templates_{lang}.txt").exists()]


@pytest.mark.parametrize("lang", AVAILABLE)
def test_templates_one_slot_plain_text(lang):
    temps = load_templates(lang)
    assert 60 <= len(temps) <= 100 and len(set(temps)) == len(temps)
    for t in temps:
        assert t.count("{T}") == 1, t
        assert PLAIN[lang].match(t.replace("{T}", "x" if lang in LATIN_LETTERS and lang != "el" else "")), t
        assert "  " not in t and t == t.strip(), t
        if lang not in ("th", "lo"):
            assert t[-1] in (".;!" if lang == "el" else ".?!؟"), t
        if lang == "es":
            assert ("¿" in t) == ("?" in t), t


def test_prefixes_unique():
    prefixes = set(ID_PREFIX.values())
    assert len(prefixes) == len(ID_PREFIX)
    from vtts.data.wiki_corpus import ID_PREFIX as SENTENCE_PREFIX

    assert not prefixes & {"vi", "en", "mx", *(SENTENCE_PREFIX.get(k, k) for k in ID_PREFIX)}


@pytest.mark.parametrize("lang", AVAILABLE)
def test_rows(lang):
    rows, total = mixed_rows(lang, hours=0.1, seed=0)
    assert rows[0]["id"] == f"{ID_PREFIX[lang]}000000" and all(r["lang"] == lang for r in rows)
    assert len({r["id"] for r in rows}) == len(rows) and 360 <= total < 400
