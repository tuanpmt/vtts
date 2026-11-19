"""Parity cases of the Dutch, Swedish and Norwegian device front-ends (modes nl, sv, no), used by
export_text_parity.py --nx nl|sv|no:

  uv run python scripts/frontend/export_text_parity.py --nx nl --sentences data/nl/sentences.jsonl \
      --limit 3000 --out runtime/test/text_parity_nl.tsv

Edge cases, both eval sets, template x term sentences, the strings of the language's unit tests,
corpus sentences (or generated ones), every exception, word-list, abbreviation, unit and number-morph
entry, random words of the language's letters, number / date / time / money / unit cases and random
strings dense in the characters the scanner reacts to.
"""

from __future__ import annotations

import ast
import importlib
import json
import random
from pathlib import Path

from vtts.frontend.text import text_to_ids

ROOT = Path(__file__).resolve().parents[2]

EDGE = {
    "nl": ["Hallo, hoe gaat het?", "Op 3-5-2026 om 14:30 kostte het € 5,50.", "Dr. Jansen komt o.a. morgen. Dan gaan we.",
           "Het werk van J. S. Bach. Mooi!", "Fruit enz. De rest.", "'s Avonds en auto's, zo'n 5km.", "'t Is 'n mooie dag.",
           "De 2e, 3de, 8ste en 21ste keer.", "Om 9.30 uur en 9.30 en 14.05uur.", "Bel 06-12345678 of +31 20 123 4567.",
           "Het kost 5,- of ƒ 2,50... echt — ja!", "0,05 en 12,345 en 007 en 1.250.000 en 3.14 en 1.2.3", "1999 en 2026 en 1100",
           "ESP32-P4 met 4G, USB en NAVO.", "België, ruïne, één, café, idee, geïnstalleerd.", "Jan & Piet + 3 = 5 @ # × §",
           "10-20 km, -5 °C, 25℃, 1 km, 5 min, 2‰ en 75%.", "t/m v. Chr. n.Chr. bijv. d.w.z.", "", "...", "a", "'", "-",
           "aangevallen ongeveer ingesteld", "Amsterdam Rotterdam Nederland politie informatie functie"],
    "sv": ["Hej, hur mår du?", "Den 3 maj 2026 kl. 14.30 kostade det 12,50 kr.", "Han kom bl.a. i går. Sedan gick vi.",
           "Frukt osv. Resten.", "Det kostar 50:- eller 99 kr.", "Den 2:a och 21:a gången, 1:e plats.", "Kl. 9.05 och klockan 9:05.",
           "Ring 08-123 45 67 eller +46 70 123 45 67.", "Det är 1 250 000 och 3,14 och 1 000.", "1999 och 2026.",
           "ESP32-P4 med 4G och USB, NATO.", "Göteborg, Malmö, Åsa, idé.", "T.ex. detta, bl.a. det.", "", "...", "a",
           "kyrka göra skicka sjuk stjärna tjugo regn älg berg Norge bord kort barn fors första",
           "station musik studera politiker förstå betala frihet kärlek tjugotvå tvåtusentjugosex"],
    "no": ["Hei, hvordan går det?", "Den 17. mai 2026 kl. 14.30 kostet det kr 12,50.", "Den 17. mai feirer vi. Det er gøy.",
           "Han kom bl.a. i går. Så gikk vi.", "Det var i 1999. Så kom 2000.", "Det koster 50,- eller 99 kr.",
           "Han kom på 3. plass, 3. Mai.", "Ring 22 12 34 56 eller +47 912 34 567.", "1 250 000 og 3,14 og 1905 og 105.",
           "ESP32-P4 med 4G og USB, NATO.", "Tromsø, Ærlig, Å, æ ø å.", "F.eks. dette, bl.a. det.", "", "...", "a",
           "kjøre kirke skjære sjø gi hva hvem god tid land kald gård holde viktig huset biler",
           "stasjon musikk studere forstå betale norsk barn kort fjord være nei øy frihet tjueen"],
}


def _tests(lang: str) -> list[str]:
    root = ROOT / "tests" / "frontend"
    out = []
    for name in (f"test_normalize_{lang}.py", f"test_text_{lang}.py", f"test_{lang}_g2p.py"):
        p = root / name
        if p.exists():
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and 0 < len(node.value) < 400:
                    out.append(node.value)
    return out


def _vocab(lang: str) -> list[str]:
    from vtts.frontend.lexicons import load_words

    g = importlib.import_module(f"vtts.frontend.{lang}.g2p_{lang}")
    nm = importlib.import_module(f"vtts.frontend.{lang}.normalize_{lang}")
    words = list(g.override_table()) + sorted(load_words(lang, "native")) + sorted(load_words(lang, "english"))
    words += list(nm.ABBREVIATIONS) + list(nm.UNITS) + list(nm.CURRENCY) + list(nm.MONTHS[1:])
    words += list(g.NUMBER_MORPHS)
    if lang == "nl":
        words += list(g.NOT_PREFIX) + sorted(g.CH_S) + sorted(g.FUNCTION_WORDS)
    else:
        words += list(g.RULES.not_prefix) + sorted(g.RULES.function_words)
    return words


def _letters(lang: str) -> str:
    g = importlib.import_module(f"vtts.frontend.{lang}.g2p_{lang}")
    return "".join(sorted(g.LETTERS))


def _pseudo(lang: str, rnd, n: int) -> list[str]:
    letters = _letters(lang)
    vow = "aeiouy" + {"nl": "éëï", "sv": "åäö", "no": "æøå"}[lang]
    out = []
    for _ in range(n):
        w = []
        for _ in range(rnd.randint(1, 4)):
            w.append(rnd.choice(letters) * rnd.choice([1, 1, 2]) + rnd.choice(vow) * rnd.choice([1, 1, 2]))
            if rnd.random() < 0.6:
                w.append(rnd.choice(letters))
        out.append("".join(w))
    return out


def _numbers(lang: str, rnd) -> list[str]:
    nm = importlib.import_module(f"vtts.frontend.{lang}.normalize_{lang}")
    units = list(nm.UNITS)
    curs = list(nm.CURRENCY)
    months = list(nm.MONTHS[1:])
    out = []
    for _ in range(2500):
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(1000, 2100), rnd.randint(0, 99999),
                        rnd.randint(0, 10 ** 9), rnd.randint(0, 10 ** 15), rnd.randint(0, 10 ** 22)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 99)
        fmt = rnd.choice(["{} hus", "{:,}", "{}.5%", "€ {}", "{}e", "{}de", "{}ste", "{}:a", "{}:e", "{}. mai",
                          "-{} " + rnd.choice(units), "{}" + rnd.choice(units), "{} " + rnd.choice(curs),
                          rnd.choice(curs) + " {}", "{},{:02d} " + rnd.choice(curs), "{}:-", "{},-", "{} " + rnd.choice(months),
                          "{}/{}/2026", "{}-{}-{}", "{}.{}.{}", "{}:{:02d}", "kl. {}.{:02d}", "{}.{:02d} uur",
                          "{}.{:03d}.{:03d}", "{} {:03d} {:03d}", "+{} {} {}", "0{} {} {}", "{}-{}", "{},{}", "{}.{}",
                          "{} ‰", "0{}", "{}G", "ESP{}", "{}x{}"])
        out.append(fmt.format(v, a, b).replace(",", rnd.choice([",", ".", " "])) if "{:," in fmt else fmt.format(v, a, b))
    for _ in range(500):
        out.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} og "
                   f"{rnd.randint(0, 33)}.{rnd.randint(0, 13)}.{rnd.randint(0, 99):02d} "
                   f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    return out


def _fuzz(lang: str, n: int, rnd) -> list[str]:
    nm = importlib.import_module(f"vtts.frontend.{lang}.normalize_{lang}")
    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=()§°‰ ") * 2 + list(nm.UNITS) + list(nm.CURRENCY)
             + list(nm.ABBREVIATIONS) + list(nm.MONTHS[1:]) + [":a", ":e", "e", "de", "ste", "uur", "kl", "kl.",
                                                                "klockan", "klokka", ",-", ":-", "…", "...", "¿", "¡",
                                                                "A", "B", "Z", "ESP", "x", "ab", "Ok", "Wi", "é", "ë",
                                                                "å", "ä", "ö", "æ", "ø", "İ", "²", "_", "'s", " ", "  ",
                                                                " ", " ", "“", "”", "«", "»", "−"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def nx_lines(lang: str, paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    rnd = random.Random(0)
    here = ROOT / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / f"templates_{lang}.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(EDGE[lang])
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        texts += [json.loads(x)["text"] for x in (ROOT / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _tests(lang)
    rows: list[str] = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows
    vocab = _vocab(lang)
    texts += [" ".join(vocab[i:i + 12]) + "." for i in range(0, len(vocab), 12)]
    texts += vocab
    pseudo = _pseudo(lang, rnd, 6000)
    texts += [" ".join(pseudo[i:i + 15]) + "." for i in range(0, len(pseudo), 15)]
    texts += _numbers(lang, rnd) + _fuzz(lang, fuzz, rnd)
    out, seen = [], set()
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85  "):
            continue
        seen.add(text)
        ids = text_to_ids(text, lang)
        out.append(f"{lang}\t{text}\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out
