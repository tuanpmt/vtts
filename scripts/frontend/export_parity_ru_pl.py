"""Parity fixtures of the Russian and Polish device front-ends (mode \\t text \\t ids, like
export_text_parity.py): runtime/test/text_parity_ru.tsv, text_parity_pl.tsv.

  uv run python scripts/frontend/export_parity_ru_pl.py --lang ru \\
      --sentences data/ru/sentences.jsonl data/ru/probe_src.jsonl --limit 3000 --out runtime/test/text_parity_ru.tsv
  uv run python scripts/frontend/export_parity_ru_pl.py --lang pl \\
      --sentences data/pl/sentences.jsonl data/pl/probe_src.jsonl --limit 3000 --out runtime/test/text_parity_pl.tsv

Cases: edge cases, both eval sets, template x term sentences, Wikipedia sentences (the given files
when present: the corpus and raw sentences with digits and symbols), sentences generated from the
lexicon words, every lexicon / exception entry (ru: overrides, stress words and stress endings;
pl: overrides, antepenult stems, native words), numbers / dates / times / money / units and random
strings dense in the characters the normalizer's patterns react to. --random N writes N extra
random strings instead (a larger run that is not committed). Texts the Python front-end raises on
are left out.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).parents[2]

RU_EDGE = [
    "Привет, мир!", "Ёлка, ёж и Ёлка.", "Ёлка йод молоко́", "В доме к другу с сестрой.",
    "в", "к", "с", "в.", "и т. д. и т. п. т. е. т.е.", "Это т. е. пример. Новое! и всё.", "г. Москва, ул. Ленина, д. 5",
    "В 2026 году, в 1990-х годах, 90-е годы, 1-й, 3-го, на 3-м этаже.", "15.03.2026 и 2026-03-15 и 31/12/99 г.",
    "5 мая, с 1 мая по 5 июня, к 3 марта", "XX век, в XX веке, XIX—XX вв., в. и вв.", "Пётр I, Екатерина II, Людовик XIV",
    "Встреча в 14:30, 9:05:07, 0:00.", "+7 (495) 123-45-67, 8 800 555 35 35, 123-45-67", "1 000 000 руб., 10,50 ₽, $5, 20 €",
    "3 млн рублей, 5 тыс. человек, 1,5 млрд долл.", "75%, -5 °C, 2,5 кг, 60 км/ч, 128 ГБ, 5 GB, 10 USD", "от 10 до 20, 10-20",
    "5-этажный, 100-летие, 2-х, 5-ти", "СССР, НАТО, МГУ, ПК, США", "ESP32, Wi-Fi, iPhone 15 Pro", "3,14159 и 1.500 и 1,500",
    "99999999999999999999 и 00012", "1 2 3", "21 книга, 2 книги, 1 окно, 32 стола", "до 32°.", "Київ і Львів", "ѐ ѝ ӣ",
    "что, чтобы, ничто, конечно, скучно, сегодня, сегодняшний, его, нового, много", "здравствуйте, чувство, солнце, счастье",
    "", " ", "...", "—", "!!!", "а. б. в.", "Он пришёл... Она ушла!", "Ты где? я тут.",
]
PL_EDGE = [
    "Cześć, jak się masz?", "W domu z tobą, w Polsce, z domu.", "w", "z", "Np. tak, itd. i itp., tzn. nie.",
    "ul. Długa 5, al. Jana Pawła II, pl. Zbawiciela", "Spotkanie 15.12.2026 o 14:30, do 7:00, od 9:05.",
    "w 2026 roku, w 1990 r., 1990 r. i rok 2000", "w XIX wieku, XXI wiek, XX w.", "1250 zł, 23,99 zł, $5, 20 €, 50 gr",
    "3 mln zł, 5 tys. osób, 2 mld, 75%", "do 30 °C, -5 °C, 1,2 kg, 100 Mb/s, 128 GB", "10-20 osób, od 10 do 20",
    "+48 123 456 789, 600 123 456", "ESP32 i USB, PKP, NATO, ZUS", "3,14159 i 2,25 i 1.500", "1 2 3", "1 książka, 1 okno, 2 koty",
    "chrząszcz brzmi w trzcinie", "Matematyka, muzyka, muzyce, języka, byliśmy, zrobilibyśmy", "Europa, autor, nauka, muzeum",
    "historii, linii, kiedy, gitara, piasek", "Kraków, żółw, jabłko, także, wódka", "uniwersytet, rzeczpospolita",
    "99999999999999999999 i 00012", "", " ", "...", "—", "Ząb. źle! ŻÓŁW?", "İstanbul, Škoda, François",
]


def _ids(text: str, lang: str) -> str | None:
    from vtts.frontend.text import text_to_ids

    try:
        return ";".join(" ".join(map(str, c)) for c in text_to_ids(text, lang))
    except Exception:  # noqa: BLE001 - texts the Python front-end cannot read are left out
        return None


def _rows(paths: list[Path]) -> list[str]:
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows


def _eval_sets(lang: str) -> list[str]:
    out = []
    for kind in ("ood", "mixed"):
        p = ROOT / "eval" / "sets" / f"{kind}_{lang}.jsonl"
        out += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out


def _mixed(lang: str, rnd, n: int) -> list[str]:
    here = ROOT / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / f"templates_{lang}.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    return rnd.sample(mixed, min(len(mixed), n))


def _lines_of(words: list[str], per: int) -> list[str]:
    return [" ".join(words[i:i + per]) for i in range(0, len(words), per)]


def _generated(words: list[str], rnd, n: int, marks: str) -> list[str]:
    out = []
    for _ in range(n):
        k = rnd.randint(3, 14)
        ws = [rnd.choice(words) for _ in range(k)]
        if rnd.random() < 0.5:
            ws[0] = ws[0][:1].upper() + ws[0][1:]
        out.append(" ".join(ws) + rnd.choice(marks))
    return out


def _numbers(lang: str, rnd, n: int) -> list[str]:
    if lang == "ru":
        temps = ["{} книга", "{} книги", "{} окно", "{} стола", "{} руб.", "{},{} ₽", "${}", "{} €", "{}%", "{},{}%",
                 "{} км", "{} кг", "{} ГБ", "{} GB", "до {} °C", "от {} до {}", "{}-{}", "{}-й", "{}-го", "{}-м",
                 "{}-х годах", "{}-е годы", "{}-летие", "в {} году", "{} г.", "в {} г.", "{} мая", "с {} мая",
                 "{}:{}", "{}.{}.{}", "{} млн", "{},{} млрд руб.", "{} тыс.", "около {} человек", "-{}", "{}.{}",
                 "{} {} {}", "{} {}"]
    else:
        temps = ["{} książka", "{} okno", "{} zł", "{},{} zł", "${}", "{} €", "{}%", "{},{}%", "{} km", "{} kg",
                 "{} GB", "do {} °C", "od {} do {}", "{}-{}", "w {} roku", "{} r.", "w {} r.", "{} maja", "o {}:{}",
                 "{}:{}", "{}.{}.{}", "{} mln", "{},{} mld zł", "{} tys.", "około {} osób", "-{}", "{}.{}", "{} {} {}",
                 "w {} wieku"]
    out = []
    for _ in range(n):
        t = rnd.choice(temps)
        vals = [rnd.choice([rnd.randint(0, 9), rnd.randint(0, 99), rnd.randint(0, 2100), rnd.randint(0, 10 ** 7),
                            rnd.randint(0, 10 ** 13), rnd.randint(0, 10 ** 19)]) for _ in range(t.count("{}"))]
        out.append(t.format(*vals))
    return out


def _fuzz(lang: str, rnd, n: int) -> list[str]:
    common = list("0123456789") * 4 + list(":/.,-–—%'+&@=×#№§° ") * 2 + [
        "…", "...", "“", "”", "«", "»", "(", ")", "ESP", "A", "B", "C", "I", "V", "X", "L", "Z", "x", "ab", "Ok", "é",
        "İ", " ", "  ", " ", " ", "+7", "8", "_", "$", "€", "£", "¥", "km", "GB", "USD", "°C", "℃", "\t"]
    if lang == "ru":
        atoms = common + ["в", "к", "с", "во", "до", "от", "около", "г.", "гг.", "г", "год", "года", "году", "век",
                          "в.", "вв.", "веке", "т.", "е.", "т. е.", "ул.", "руб.", "р.", "₽", "млн", "тыс.", "км", "кг",
                          "ГБ", "-й", "-го", "-х", "-е", "-ти", "летие", "мая", "марта", "СССР", "ПК", "Пётр", "книга",
                          "ы", "а", "о", "ё", "ь", "ъ", "й", "ё", "й", "́", "Ѐ", "ґ"]
    else:
        atoms = common + ["w", "z", "o", "do", "od", "około", "r.", "roku", "rok", "wiek", "wieku", "w.", "np.",
                          "itd.", "ul.", "zł", "gr", "mln", "tys.", "km", "kg", "GB", "Mb/s", "maja", "PKP", "NATO",
                          "ą", "ę", "ó", "ł", "ż", "ź", "ć", "ń", "ś", "rz", "cz", "sz", "dz", "ci", "książka"]
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def _lexicon_lines(lang: str) -> list[str]:
    from vtts.frontend.lexicons import load_table, load_words

    if lang == "ru":
        words = sorted(load_table("ru", "overrides")) + sorted(load_table("ru", "stress"))
        sufs = sorted(k[1:] for k in load_table("ru", "stress_suffixes") if len(k) > 1)
        return _lines_of(words, 12) + _lines_of(sufs, 16)
    stems = sorted(load_words("pl", "antepenult"))
    forms = [s + e for s in stems for e in ("a", "i", "ę", "ą")] + [s[:-1] + "ce" for s in stems]
    words = sorted(load_table("pl", "overrides")) + forms + sorted(load_words("pl", "native"))
    return _lines_of(words, 10)


def lines(lang: str, paths: list[Path], limit: int | None, fuzz: int, extra_random: int = 0) -> list[str]:
    rnd = random.Random(0 if not extra_random else 12345)
    if extra_random:
        texts = _fuzz(lang, rnd, extra_random // 2) + _numbers(lang, rnd, extra_random // 4)
        rows = _rows(paths)
        texts += _generated([w for r in rows for w in r.split()] or ["a"], rnd, extra_random // 4, ".?!,")
    else:
        texts = list(RU_EDGE if lang == "ru" else PL_EDGE) + _eval_sets(lang) + _mixed(lang, rnd, 1500)
        rows = _rows(paths)
        if limit and len(rows) > limit:
            rows = rnd.sample(rows, limit)
        texts += rows
        vocab = sorted({w.strip(".,?!;:()«»\"") for r in rows for w in r.split()} - {""})
        texts += _generated(vocab or ["a"], rnd, 1500, ".?!,;:")
        texts += _lexicon_lines(lang)
        texts += _numbers(lang, rnd, 1500)
        texts += _fuzz(lang, rnd, fuzz)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        ids = _ids(text, lang)
        if ids is not None:
            out.append(f"{lang}\t{text}\t{ids}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=("ru", "pl"), required=True)
    ap.add_argument("--sentences", type=Path, nargs="*", default=[])
    ap.add_argument("--limit", type=int, default=3000)
    ap.add_argument("--fuzz", type=int, default=2000)
    ap.add_argument("--random", type=int, default=0, help="only N extra random cases (an uncommitted run)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = lines(a.lang, a.sentences, a.limit, a.fuzz, a.random)
    a.out.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} cases to {a.out}")


if __name__ == "__main__":
    main()
