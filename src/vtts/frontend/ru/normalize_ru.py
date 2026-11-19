"""Russian text normalization for one Russian run.

Output follows the other modules' convention: lower-case words and the punctuation tokens
, . ? ! ; : separated by single spaces (ё kept). Latin parts go through the English normalizer.

Rules, in order: ё and й written with combining marks composed and the combining acute (a
stress mark) dropped, phone numbers (+7 (495) 123-45-67: digit by digit), abbreviations (т. е., и т. д.,
г., ул., руб., млн ...), quotes and brackets dropped, numbers grouped with spaces (1 000 000),
dates (15.03.2026, 2026-03-15: пятнадцатое марта две тысячи двадцать шестого года), a day before
a month name (5 мая -> пятое мая; after с/до/от/после/около: пятого), years before год/года/году/
г. (ordinal in that case), centuries and regnal numbers in Roman numerals (XX век, Пётр I), times
(14:30 -> четырнадцать тридцать), numbers with тыс./млн/млрд, money (100 ₽, $5, 10,50 руб. ->
десять рублей пятьдесят копеек), percentages, units after a number (5 км, 128 ГБ, 25 °C),
ordinals with a written ending (1-й, 2-я, 3-го, 1990-х), ranges (10-20 -> от десяти до двадцати),
pause marks, product codes (ESP32: Latin letters by their Russian names, digits one by one),
numbers (decimal comma: три целых пять десятых), symbols, acronyms (СССР -> эс эс эс эр; a few
read as words: НАТО, МИД), and the one-letter prepositions в к с joined to the next word with a
hyphen (в доме -> в-доме) so the voicing rules see them together.

Agreement: a number takes the gender of the noun after it only where it is cheap: 1 and 2 (21,
32 ...) before a noun ending in а/я (одна книга) or о/е (одно окно) and 2 before a noun ending in
ы/и (две книги); units and currencies have their gender and the noun form by the number (1
рубль, 2 рубля, 5 рублей). A whole number (with or without a unit) after до, от, около, более,
с ... is genitive (до тридцати двух градусов). Other cases are read nominative.
"""

from __future__ import annotations

import re
import unicodedata

from ..latin_norm import DROP, PAUSE, PRODUCT_CODE, parse_number
from .g2p_ru import compose

ONES = ("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
        "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
        "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
TENS = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят",
        "восемьдесят", "девяносто")
HUNDREDS = ("", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот",
            "восемьсот", "девятьсот")
ONES_GEN = ("ноля", "одного", "двух", "трёх", "четырёх", "пяти", "шести", "семи", "восьми",
            "девяти", "десяти", "одиннадцати", "двенадцати", "тринадцати", "четырнадцати",
            "пятнадцати", "шестнадцати", "семнадцати", "восемнадцати", "девятнадцати")
TENS_GEN = ("", "", "двадцати", "тридцати", "сорока", "пятидесяти", "шестидесяти", "семидесяти",
            "восьмидесяти", "девяноста")
HUNDREDS_GEN = ("", "ста", "двухсот", "трёхсот", "четырёхсот", "пятисот", "шестисот", "семисот",
                "восьмисот", "девятисот")
# (value, gender, one, few, many)
SCALES = ((10 ** 12, "m", "триллион", "триллиона", "триллионов"),
          (10 ** 9, "m", "миллиард", "миллиарда", "миллиардов"),
          (10 ** 6, "m", "миллион", "миллиона", "миллионов"),
          (1000, "f", "тысяча", "тысячи", "тысяч"))
DIGITS = ONES[:10]

# Ordinals: stem and declension class (h: -ый, s: stressed -ой, t: третий).
ORD_ONES = (("", ""), ("перв", "h"), ("втор", "s"), ("трет", "t"), ("четвёрт", "h"), ("пят", "h"),
            ("шест", "s"), ("седьм", "s"), ("восьм", "s"), ("девят", "h"), ("десят", "h"),
            ("одиннадцат", "h"), ("двенадцат", "h"), ("тринадцат", "h"), ("четырнадцат", "h"),
            ("пятнадцат", "h"), ("шестнадцат", "h"), ("семнадцат", "h"), ("восемнадцат", "h"),
            ("девятнадцат", "h"))
ORD_TENS = ("", "", "двадцат", "тридцат", "сороков", "пятидесят", "шестидесят", "семидесят",
            "восьмидесят", "девяност")
ORD_TENS_CLASS = ("", "", "h", "h", "s", "h", "h", "h", "h", "h")
ORD_HUNDREDS = ("", "сот", "двухсот", "трёхсот", "четырёхсот", "пятисот", "шестисот", "семисот",
                "восьмисот", "девятисот")
ORD_THOUSANDS = ("", "", "двух", "трёх", "четырёх", "пяти", "шести", "семи", "восьми", "девяти")
CASES = ("nom_m", "nom_f", "nom_n", "nom_pl", "gen_m", "dat_m", "prep_m", "ins_m", "acc_f",
         "obl_f", "gen_pl", "ins_pl")
ENDINGS = {
    "h": ("ый", "ая", "ое", "ые", "ого", "ому", "ом", "ым", "ую", "ой", "ых", "ыми"),
    "s": ("ой", "ая", "ое", "ые", "ого", "ому", "ом", "ым", "ую", "ой", "ых", "ыми"),
    "t": ("ий", "ья", "ье", "ьи", "ьего", "ьему", "ьем", "ьим", "ью", "ьей", "ьих", "ьими"),
}
# Written ordinal endings (1-й, 3-го ...) -> case.
SUFFIX_CASE = {"й": "nom_m", "ый": "nom_m", "ий": "nom_m", "я": "nom_f", "ая": "nom_f",
               "ья": "nom_f", "е": "nom_n", "ое": "nom_n", "ье": "nom_n", "ые": "nom_pl",
               "го": "gen_m", "ого": "gen_m", "его": "gen_m", "му": "dat_m", "ому": "dat_m",
               "ему": "dat_m", "м": "prep_m", "ом": "prep_m", "ем": "prep_m", "ым": "ins_m",
               "им": "ins_m", "ю": "acc_f", "ую": "acc_f", "ой": "obl_f", "ей": "obl_f",
               "х": "gen_pl", "ых": "gen_pl", "их": "gen_pl", "ми": "ins_pl", "ыми": "ins_pl"}

MONTHS = ("", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря")
YEAR_NOUN = {"год": "nom_m", "года": "gen_m", "году": "prep_m", "годом": "ins_m",
             "годах": "gen_pl", "годов": "gen_pl", "годы": "nom_pl", "годам": "gen_pl"}
CENTURY_NOUN = {"век": "nom_m", "века": "gen_m", "веке": "prep_m", "веку": "dat_m",
                "веком": "ins_m", "веков": "gen_pl", "веках": "gen_pl", "вв.": "gen_pl",
                "в.": "nom_m"}
GEN_PREPOSITIONS = frozenset(("с", "со", "до", "от", "после", "около", "начиная", "из", "без",
                              "для", "у", "кроме", "среди", "посреди", "вокруг", "против"))
# Words after which a plain count is genitive (до 30 градусов -> до тридцати градусов).
GEN_COUNT = frozenset(("до", "от", "около", "после", "без", "для", "из", "у", "кроме", "более",
                       "менее", "свыше", "больше", "меньше", "порядка", "с", "со"))

LETTER_NAMES = {"а": "а", "б": "бэ", "в": "вэ", "г": "гэ", "д": "дэ", "е": "е", "ё": "ё",
                "ж": "жэ", "з": "зэ", "и": "и", "й": "и краткое", "к": "ка", "л": "эль", "м": "эм",
                "н": "эн", "о": "о", "п": "пэ", "р": "эр", "с": "эс", "т": "тэ", "у": "у", "ф": "эф",
                "х": "ха", "ц": "цэ", "ч": "че", "ш": "ша", "щ": "ща", "ъ": "твёрдый знак",
                "ы": "ы", "ь": "мягкий знак", "э": "э", "ю": "ю", "я": "я"}
LATIN_LETTERS = {"a": "эй", "b": "би", "c": "си", "d": "ди", "e": "и", "f": "эф", "g": "джи",
                 "h": "эйч", "i": "ай", "j": "джей", "k": "кей", "l": "эл", "m": "эм", "n": "эн",
                 "o": "оу", "p": "пи", "q": "кью", "r": "ар", "s": "эс", "t": "ти", "u": "ю",
                 "v": "ви", "w": "дабл ю", "x": "экс", "y": "уай", "z": "зед"}
ACRONYM_WORDS = frozenset(("нато", "мид", "гост", "вуз", "вузы", "вузов", "загс", "гэс", "аэс",
                           "тэц", "мхат", "гум", "цум", "тасс", "оон", "юнеско", "ссср", "рсфср",
                           "спид", "омон", "нии", "мвд", "фсб", "мчс", "рф", "сша", "ес", "снг",
                           "ран", "мгу", "вдв", "ввп", "гибдд", "ржд", "цска", "рао", "зао",
                           "оао", "ооо", "пао", "кпсс", "вцик", "нэп", "вак", "ик"))
# Acronyms in the list above that are spelled (the rest are read as words).
SPELLED = frozenset(("ссср", "рсфср", "мвд", "фсб", "мчс", "рф", "сша", "ес", "снг", "мгу",
                     "вдв", "ввп", "гибдд", "ржд", "цска", "рао", "зао", "оао", "ооо", "пао",
                     "кпсс", "нии", "оон", "ик"))
ABBREVIATIONS = {
    "т. е.": "то есть", "т.е.": "то есть", "и т. д.": "и так далее", "и т.д.": "и так далее",
    "и т. п.": "и тому подобное", "и т.п.": "и тому подобное", "т. к.": "так как",
    "т.к.": "так как", "т. н.": "так называемый", "т.н.": "так называемый",
    "и др.": "и другие", "и пр.": "и прочие", "в т. ч.": "в том числе", "в т.ч.": "в том числе",
    "до н. э.": "до нашей эры", "до н.э.": "до нашей эры", "н. э.": "нашей эры",
    "н.э.": "нашей эры", "см.": "смотри", "напр.": "например", "ул.": "улица",
    "просп.": "проспект", "пл.": "площадь", "кв.": "квартира", "им.": "имени",
    "проф.": "профессор", "акад.": "академик", "доц.": "доцент", "стр.": "страница",
    "рис.": "рисунок", "табл.": "таблица", "ок.": "около", "прим.": "примечание",
    "англ.": "английский", "лат.": "латинский", "гг.": "годы", "г.": "город",
    "обл.": "область", "р-н": "район", "пос.": "посёлок", "дер.": "деревня",
}
# (gender, one, few, many)
UNITS = {
    "км/ч": ("m", "километр в час", "километра в час", "километров в час"),
    "km/h": ("m", "километр в час", "километра в час", "километров в час"),
    "км": ("m", "километр", "километра", "километров"), "km": ("m", "километр", "километра", "километров"),
    "м": ("m", "метр", "метра", "метров"), "m": ("m", "метр", "метра", "метров"),
    "см": ("m", "сантиметр", "сантиметра", "сантиметров"), "cm": ("m", "сантиметр", "сантиметра", "сантиметров"),
    "мм": ("m", "миллиметр", "миллиметра", "миллиметров"), "mm": ("m", "миллиметр", "миллиметра", "миллиметров"),
    "кг": ("m", "килограмм", "килограмма", "килограммов"), "kg": ("m", "килограмм", "килограмма", "килограммов"),
    "г": ("m", "грамм", "грамма", "граммов"), "g": ("m", "грамм", "грамма", "граммов"),
    "мг": ("m", "миллиграмм", "миллиграмма", "миллиграммов"), "mg": ("m", "миллиграмм", "миллиграмма", "миллиграммов"),
    "т": ("f", "тонна", "тонны", "тонн"),
    "л": ("m", "литр", "литра", "литров"), "l": ("m", "литр", "литра", "литров"), "L": ("m", "литр", "литра", "литров"),
    "мл": ("m", "миллилитр", "миллилитра", "миллилитров"), "ml": ("m", "миллилитр", "миллилитра", "миллилитров"),
    "га": ("m", "гектар", "гектара", "гектаров"),
    "ч": ("m", "час", "часа", "часов"), "h": ("m", "час", "часа", "часов"),
    "мин": ("f", "минута", "минуты", "минут"), "min": ("f", "минута", "минуты", "минут"),
    "сек": ("f", "секунда", "секунды", "секунд"), "s": ("f", "секунда", "секунды", "секунд"),
    "Мбит/с": ("m", "мегабит в секунду", "мегабита в секунду", "мегабит в секунду"),
    "Мбит": ("m", "мегабит", "мегабита", "мегабит"),
    "Mbps": ("m", "мегабит в секунду", "мегабита в секунду", "мегабит в секунду"),
    "КБ": ("m", "килобайт", "килобайта", "килобайт"), "KB": ("m", "килобайт", "килобайта", "килобайт"),
    "МБ": ("m", "мегабайт", "мегабайта", "мегабайт"), "MB": ("m", "мегабайт", "мегабайта", "мегабайт"),
    "ГБ": ("m", "гигабайт", "гигабайта", "гигабайт"), "GB": ("m", "гигабайт", "гигабайта", "гигабайт"),
    "ТБ": ("m", "терабайт", "терабайта", "терабайт"), "TB": ("m", "терабайт", "терабайта", "терабайт"),
    "кВт·ч": ("m", "киловатт-час", "киловатт-часа", "киловатт-часов"),
    "kWh": ("m", "киловатт-час", "киловатт-часа", "киловатт-часов"),
    "кВт": ("m", "киловатт", "киловатта", "киловатт"), "kW": ("m", "киловатт", "киловатта", "киловатт"),
    "Вт": ("m", "ватт", "ватта", "ватт"), "W": ("m", "ватт", "ватта", "ватт"),
    "В": ("m", "вольт", "вольта", "вольт"), "V": ("m", "вольт", "вольта", "вольт"),
    "мАч": ("m", "миллиампер-час", "миллиампер-часа", "миллиампер-часов"),
    "mAh": ("m", "миллиампер-час", "миллиампер-часа", "миллиампер-часов"),
    "ГГц": ("m", "гигагерц", "гигагерца", "гигагерц"), "GHz": ("m", "гигагерц", "гигагерца", "гигагерц"),
    "МГц": ("m", "мегагерц", "мегагерца", "мегагерц"), "MHz": ("m", "мегагерц", "мегагерца", "мегагерц"),
    "Гц": ("m", "герц", "герца", "герц"), "Hz": ("m", "герц", "герца", "герц"),
    "°C": ("m", "градус Цельсия", "градуса Цельсия", "градусов Цельсия"),
    "℃": ("m", "градус Цельсия", "градуса Цельсия", "градусов Цельсия"),
    "°": ("m", "градус", "градуса", "градусов"),
}
CURRENCY = {
    "₽": ("m", "рубль", "рубля", "рублей"), "руб.": ("m", "рубль", "рубля", "рублей"),
    "руб": ("m", "рубль", "рубля", "рублей"), "р.": ("m", "рубль", "рубля", "рублей"),
    "RUB": ("m", "рубль", "рубля", "рублей"),
    "$": ("m", "доллар", "доллара", "долларов"), "долл.": ("m", "доллар", "доллара", "долларов"),
    "USD": ("m", "доллар", "доллара", "долларов"),
    "€": ("n", "евро", "евро", "евро"), "EUR": ("n", "евро", "евро", "евро"),
    "£": ("m", "фунт", "фунта", "фунтов"), "¥": ("f", "иена", "иены", "иен"),
    "₴": ("f", "гривна", "гривны", "гривен"), "грн": ("f", "гривна", "гривны", "гривен"),
    "₸": ("m", "тенге", "тенге", "тенге"),
}
SUBUNIT = {"рубль": ("f", "копейка", "копейки", "копеек"), "доллар": ("m", "цент", "цента", "центов"),
           "евро": ("m", "цент", "цента", "центов")}
SCALE_ABBR = {"тыс.": 1000, "тыс": 1000, "млн": 10 ** 6, "млн.": 10 ** 6, "млрд": 10 ** 9,
              "млрд.": 10 ** 9, "трлн": 10 ** 12, "трлн.": 10 ** 12}
# Plain Latin words of the tables: lang.py tags them Russian in mode "ru" (5 km, 10 USD).
LATIN_WORDS = frozenset(k for k in (*UNITS, *CURRENCY) if len(k) > 1 and k.isascii() and k.isalpha())
SYMBOLS = {"&": " и ", "+": " плюс ", "=": " равно ", "@": " собака ", "×": " на ", "#": " номер ",
           "№": " номер ", "%": " процентов ", "/": " ", "§": " параграф "}
FRACTION = ("", "десятая", "сотая", "тысячная")
FRACTION_PL = ("", "десятых", "сотых", "тысячных")

_NUM = r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_A = r"(?<![\w.,])"
_Z = r"(?![\w])"
_CYR = "а-яёА-ЯЁ"
_UNIT_KEYS = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_CUR_KEYS = "|".join(re.escape(c) for c in sorted(CURRENCY, key=len, reverse=True))
_SCALE_KEYS = "|".join(re.escape(s) for s in sorted(SCALE_ABBR, key=len, reverse=True))
PHONE = re.compile(r"(?<![\d\w])(?:(?:\+\d{1,3}|8)[\s-]*\(?\d{3,4}\)?[\s-]*\d{2,3}[\s-]*\d{2}[\s-]*\d{2}"
                   r"|(?:\(?\d{3,4}\)?[\s-]*)?\d{2,3}-\d{2}-\d{2})(?![\d])")
DATE_DMY = re.compile(r"(?<![\d.])(\d{1,2})([./])(\d{1,2})\2(\d{4}|\d{2})(?![\d])(\s*(?:г\.|года?))?")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
DAY_MONTH = re.compile(r"(?<![\d,.])(\d{1,2})\s+(" + "|".join(MONTHS[1:]) + r")" + _Z)
YEAR = re.compile(r"(?<![\d,.])(\d{3,4})\s*(г\.|гг\.|" + "|".join(YEAR_NOUN) + r")(?![\w])")
ROMAN = r"[IVXLC]+"
CENTURY = re.compile(r"(?<![\w])(" + ROMAN + r")(?:\s*[-–]\s*(" + ROMAN + r"))?\s+(" +
                     "|".join(re.escape(k) for k in sorted(CENTURY_NOUN, key=len, reverse=True)) +
                     r")(?![\w])")
REGNAL = re.compile(r"(?<=[" + _CYR + r"])(\s+)(" + ROMAN + r")(?![\w])")
TIME = re.compile(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?![\d:])")
SCALED = re.compile(_A + r"(" + _NUM + r")\s*(" + _SCALE_KEYS + r")(?:\s*(" + _CUR_KEYS + r"))?(?![\w])")
MONEY_BEFORE = re.compile(r"(?<![\w])(" + _CUR_KEYS + r")\s?(" + _NUM + r")(?![\d])")
MONEY_AFTER = re.compile(_A + r"(" + _NUM + r")\s?(" + _CUR_KEYS + r")(?![\w])")
PERCENT = re.compile(_A + r"(-?)(" + _NUM + r")\s?%")
UNIT = re.compile(_A + r"(-?)(" + _NUM + r")\s?(" + _UNIT_KEYS + r")(?![\w])")
ORDINAL = re.compile(_A + r"(\d+)\s?-\s?(" + "|".join(sorted([*SUFFIX_CASE, "ти"], key=len, reverse=True)) +
                     r")(?![\w])(\s+\S+)?")
COMPOUND = re.compile(_A + r"(\d{1,4})-([" + _CYR + r"]{3,})")  # 5-этажный, 1000-летие
COMPOUND_PREFIX = {1: "одно", 100: "сто", 90: "девяносто", 40: "сорока", 1000: "тысяче"}
RANGE = re.compile(_A + r"(\d+)\s?[-–—]\s?(\d+)" + _Z)
NUMBER = re.compile(r"(?<![\w.,])(-?)(" + _NUM + r")(?![\d])(?=(\s+[" + _CYR + r"]+)?)")
ACRONYM = re.compile(r"(?<![\w])[А-ЯЁ]{2,6}(?![\w])")
LATIN = re.compile(r"[A-Za-zÀ-ɏ](?:[A-Za-zÀ-ɏ'-]*[A-Za-zÀ-ɏ])?")
WORD = re.compile(r"[а-яё]+|[^\W\d_]+(?:'[^\W\d_]+)*|[,.?!;:]")
MARKS = ",.?!;:"
CLITICS = frozenset(("в", "к", "с"))


def prev_word(m: re.Match) -> str | None:
    """The whitespace-separated chunk right before a match (in the pass's input), or None when no
    whitespace or nothing precedes it: до in "до 32 °C". It is looked at, not replaced."""
    s, k = m.string, m.start()
    j = k
    while j > 0 and s[j - 1].isspace():
        j -= 1
    if j == k or j == 0:
        return None
    i = j
    while i > 0 and not s[i - 1].isspace():
        i -= 1
    return s[i:j]


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """forms (one, few, many) for an integer count: 1 21 -> one, 2-4 22-24 -> few, else many."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def _below_1000(n: int, gender: str = "m") -> list[str]:
    h, r = divmod(n, 100)
    out = [HUNDREDS[h]] if h else []
    if r >= 20:
        t, r = divmod(r, 10)
        out.append(TENS[t])
    if r:
        word = ONES[r]
        if r == 1 and gender != "m":
            word = "одна" if gender == "f" else "одно"
        elif r == 2 and gender == "f":
            word = "две"
        out.append(word)
    return out


def cardinal(n: int, gender: str = "m") -> str:
    """Russian cardinal in the nominative; gender (m, f, n) of the counted noun: 1 -> один / одна /
    одно, 2 -> два / две; 2026 -> две тысячи двадцать шесть."""
    if n < 0:
        return "минус " + cardinal(-n, gender)
    if n == 0:
        return "ноль"
    if n >= 10 ** 15:
        return digits(str(n))
    out: list[str] = []
    for value, g, *forms in SCALES:
        q, n = divmod(n, value)
        if q:
            if not (q == 1 and value == 1000):  # тысяча, not одна тысяча
                out += _below_1000(q, g) if q < 1000 else cardinal(q, g).split()
            out.append(plural(q, tuple(forms)))
    out += _below_1000(n, gender)
    return " ".join(out)


def cardinal_gen(n: int) -> str:
    """Genitive cardinal (от десяти до двадцати, двух тысяч)."""
    if n >= 10 ** 15:
        return digits(str(n))
    if n == 0:
        return "ноля"
    out: list[str] = []
    for value, _g, one, _few, many in SCALES:
        q, n = divmod(n, value)
        if q:
            if q > 1:
                words = cardinal_gen(q)
                if value == 1000:
                    words = re.sub(r"одного$", "одной", words)
                out.append(words)
            out.append(("тысячи" if value == 1000 else one + "а") if q % 10 == 1 and q % 100 != 11
                       else many)
    h, r = divmod(n, 100)
    if h:
        out.append(HUNDREDS_GEN[h])
    if r >= 20:
        t, r = divmod(r, 10)
        out.append(TENS_GEN[t])
    if r:
        out.append(ONES_GEN[r])
    return " ".join(out)


def _ord_word(stem: str, cls: str, case: str) -> str:
    return stem + ENDINGS[cls][CASES.index(case)]


def ordinal(n: int, case: str = "nom_m") -> str:
    """Ordinal adjective: 1 -> первый, 21 (gen_m) -> двадцать первого, 2026 (gen_m) -> две тысячи
    двадцать шестого, 2000 -> двухтысячный, 300 -> трёхсотый."""
    if n <= 0 or n >= 10 ** 9:
        return cardinal(n)
    r100 = n % 100
    if r100:
        head = n - r100
        if r100 < 20:
            stem, cls = ORD_ONES[r100]
        elif r100 % 10 == 0:
            stem, cls = ORD_TENS[r100 // 10], ORD_TENS_CLASS[r100 // 10]
        else:
            head += r100 - r100 % 10
            stem, cls = ORD_ONES[r100 % 10]
        word = _ord_word(stem, cls, case)
    elif n % 1000:
        head = n - n % 1000
        word = _ord_word(ORD_HUNDREDS[(n % 1000) // 100], "h", case)
    elif n % 10 ** 6:
        q = (n % 10 ** 6) // 1000
        head = n - n % 10 ** 6
        prefix = ORD_THOUSANDS[q] if q < 10 else cardinal_gen(q).replace(" ", "")
        word = _ord_word(prefix + "тысячн", "h", case)
    else:
        q = n // 10 ** 6
        head = 0
        prefix = "" if q == 1 else (ORD_THOUSANDS[q] if q < 10 else cardinal_gen(q).replace(" ", ""))
        word = _ord_word(prefix + "миллионн", "h", case)
    return (cardinal(head) + " " + word) if head else word


def digits(s: str) -> str:
    return " ".join(DIGITS[int(c)] for c in s if c.isdigit())


def _clean_num(s: str) -> str:
    return re.sub(r"[ \u00a0\u202f]", "", s)


def number(s: str, gender: str = "m") -> str:
    """A written number: decimal comma or point (3,5 -> три целых пять десятых; more than three
    decimals digit by digit after запятая)."""
    s = _clean_num(s)
    neg = s.startswith("-")
    n, frac, _ = parse_number(s.lstrip("-"))
    if frac is None:
        out = cardinal(n, gender)
    elif len(frac) <= 3:
        whole = cardinal(n, "f") + " " + plural(n, ("целая", "целых", "целых"))
        k = int(frac)
        out = f"{whole} {cardinal(k, 'f')} " + (FRACTION[len(frac)] if plural(k, ("1", "", "")) == "1"
                                                 else FRACTION_PL[len(frac)])
    else:
        out = cardinal(n) + " запятая " + digits(frac)
    return ("минус " if neg else "") + out


def count(s: str, unit: tuple[str, str, str, str]) -> str:
    """A number and the unit noun in the form the number takes (1 рубль, 2 рубля, 2,5 рубля)."""
    gender, *forms = unit
    s = _clean_num(s)
    n, frac, _ = parse_number(s.lstrip("-"))
    noun = forms[1] if frac is not None else plural(n, tuple(forms))
    return f"{number(s, gender)} {noun}"


def _gender_of(noun: str | None) -> str:
    """Cheap guess of a following noun's gender for 1 and 2: а/я -> f, о/е -> n, else m."""
    if not noun:
        return "m"
    w = noun.strip().lower()
    if w.endswith(("а", "я")):
        return "f"
    if w.endswith(("о", "е", "ё")):
        return "n"
    return "m"


def _gen_count(prev: str | None, num: str) -> bool:
    """A whole number after до, от, около ... is read in the genitive."""
    return (prev or "").lower() in GEN_COUNT and parse_number(_clean_num(num))[1] is None


def _number(m: re.Match) -> str:
    sign, num, noun = m.groups()
    prev = prev_word(m)
    n_clean = _clean_num(num)
    n, frac, _ = parse_number(n_clean)
    if not sign and _gen_count(prev, num):
        return f" {cardinal_gen(n)} "
    gender = "m"
    if noun and frac is None:
        last = n % 10
        w = noun.strip().lower()
        if last == 1 and n % 100 != 11:
            gender = _gender_of(w)
        elif last == 2 and n % 100 != 12 and w.endswith(("ы", "и")):
            gender = "f"
    return f" {number(sign + num, gender)} "


def _date(d: int, m: int, y: str | None, case: str = "nom_n") -> str:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return ""
    day_case = {"nom_n": "nom_n", "gen_m": "gen_m", "dat_m": "dat_m"}.get(case, "nom_n")
    out = f"{ordinal(d, day_case)} {MONTHS[m]}"
    if y is not None:
        yy = int(y) + (2000 if len(y) == 2 else 0)
        out += f" {ordinal(yy, 'gen_m')} года"
    return f" {out} "


def _prep_case(prev: str | None) -> str:
    p = (prev or "").lower()
    if p in GEN_PREPOSITIONS:
        return "gen_m"
    if p in ("к", "ко"):
        return "dat_m"
    return "nom_n"


def _day_month(m: re.Match) -> str:
    d, month = m.groups()
    prev = prev_word(m)
    if not 1 <= int(d) <= 31:
        return m.group(0)
    case = _prep_case(prev)
    return f" {ordinal(int(d), case)} {month} "


def _year(m: re.Match) -> str:
    y, noun = m.groups()
    prev = prev_word(m)
    if noun in ("г.", "гг."):
        plural_noun = noun == "гг."
        if (prev or "").lower() in ("в", "во"):
            case, noun = ("gen_pl", "годах") if plural_noun else ("prep_m", "году")
        elif plural_noun:
            case, noun = "nom_pl", "годы"
        else:
            case, noun = "gen_m", "года"
    else:
        case = YEAR_NOUN[noun]
    end = " ." if m.group(2).endswith(".") and not m.string[m.end():].strip() else ""
    return f" {ordinal(int(y), case)} {noun}{end} "


ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = ROMAN_VALUES[a]
        total += -v if b != " " and ROMAN_VALUES[b] > v else v
    return total


def _century(m: re.Match) -> str:
    a, b, noun = m.groups()
    case = CENTURY_NOUN[noun]
    word = {"в.": "век", "вв.": "веков"}.get(noun, noun)
    if b:
        case = "nom_m" if case == "gen_pl" and noun == "вв." else case
        return f" {ordinal(roman(a), case)} {ordinal(roman(b), case)} {word} "
    return f" {ordinal(roman(a), case)} {word} "


def _regnal(m: re.Match) -> str:
    """Пётр I -> Пётр первый, Екатерина II -> Екатерина вторая (the name before decides)."""
    space, r = m.groups()
    start = m.string.rfind(" ", 0, m.start()) + 1
    name = m.string[start:m.start()]
    if r in ("C", "L") or not name[:1].isupper():
        return m.group(0)
    case = "nom_f" if name.endswith(("а", "я")) else "nom_m"
    return f"{space}{ordinal(roman(r), case)}"


def _time(m: re.Match) -> str:
    h, mi, sec = int(m.group(1)), int(m.group(2)), m.group(3)
    out = cardinal(h) + " " + ("ноль ноль" if mi == 0 else cardinal(mi) if mi >= 10
                               else "ноль " + cardinal(mi))
    if sec and int(sec):
        out += f" и {cardinal(int(sec), 'f')} {plural(int(sec), ('секунда', 'секунды', 'секунд'))}"
    return f" {out} "


def _scaled(m: re.Match) -> str:
    num, scale_key, cur = m.groups()
    value = SCALE_ABBR[scale_key]
    forms = next((g, one, few, many) for v, g, one, few, many in SCALES if v == value)
    out = count(num, forms)
    if cur:
        out += " " + CURRENCY[cur][3]
    return f" {out} "


def _money(num: str, cur: str) -> str:
    unit = CURRENCY[cur]
    s = _clean_num(num)
    n, frac, _ = parse_number(s)
    if frac is not None and len(frac) == 2 and unit[1] in SUBUNIT:
        out = count(str(n), unit)
        if int(frac):
            out += " " + count(str(int(frac)), SUBUNIT[unit[1]])
        return f" {out} "
    return f" {count(num, unit)} "


def _unit(m: re.Match) -> str:
    sign, num, unit = m.groups()
    prev = prev_word(m)
    if not sign and _gen_count(prev, num):
        n = parse_number(_clean_num(num))[0]
        forms = UNITS[unit]
        return f" {cardinal_gen(n)} {forms[2] if plural(n, ('1', '', '')) == '1' else forms[3]} "
    return f" {'минус ' if sign else ''}{count(num, UNITS[unit])} "


def _ordinal(m: re.Match) -> str:
    n, suffix, nxt = int(m.group(1)), m.group(2), m.group(3) or ""
    if suffix in ("х", "ти") and n < 10:  # 2-х, 5-ти: двух, пяти
        return f" {cardinal_gen(n)}{nxt}"
    case = SUFFIX_CASE[suffix]
    if suffix == "е" and (n >= 1000 or nxt.strip().strip(",.?!;:").lower() == "годы"):
        case = "nom_pl"
    return f" {ordinal(n, case)}{nxt}"


def _compound(m: re.Match) -> str:
    """5-этажный -> пятиэтажный, 100-летие -> столетие, 50-летний -> пятидесятилетний."""
    n = int(m.group(1))
    prefix = COMPOUND_PREFIX.get(n) or cardinal_gen(n).replace(" ", "")
    return f" {prefix}{m.group(2)}"


def _spell_code(code: str) -> str:
    out = []
    for c in code:
        if c.isdigit():
            out.append(DIGITS[int(c)])
        elif c.lower() in LATIN_LETTERS:
            out.append(LATIN_LETTERS[c.lower()])
        elif c.lower() in LETTER_NAMES:
            out.append(LETTER_NAMES[c.lower()])
    return " ".join(out)


def _acronym(m: re.Match) -> str:
    w = m.group(0)
    low = w.lower()
    if low in ACRONYM_WORDS and low not in SPELLED:
        return low
    return " " + " ".join(LETTER_NAMES[c] for c in low) + " "


def _latin(m: re.Match) -> str:
    from ..en.normalize_en import normalize_en

    folded = "".join(c for c in unicodedata.normalize("NFKD", m.group(0)) if c.isascii())
    return f" {normalize_en(folded)} "


def _abbreviations(t: str) -> str:
    for key in sorted(ABBREVIATIONS, key=len, reverse=True):
        end = key.endswith(".")

        def sub(m: re.Match, key=key, end=end) -> str:
            last = end and not m.string[m.end():].strip()
            return f" {ABBREVIATIONS[key]} {'.' if last else ''}"

        t = re.sub(r"(?<![\w])" + re.escape(key) + ("" if end else r"(?![\w])"), sub, t)
    return t


def _join_clitics(words: list[str]) -> list[str]:
    """в к с before a Cyrillic word are joined to it with a hyphen (в-доме)."""
    out: list[str] = []
    k = 0
    while k < len(words):
        w = words[k]
        if (w in CLITICS and k + 1 < len(words) and words[k + 1] not in MARKS
                and any("а" <= c <= "я" or c == "ё" for c in words[k + 1])):
            out.append(f"{w}-{words[k + 1]}")
            k += 2
            continue
        out.append(w)
        k += 1
    return out


def normalize_ru(text: str) -> str:
    t = compose(text)
    t = PHONE.sub(lambda m: f" {'плюс ' if m.group(0).startswith('+') else ''}{digits(m.group(0))} ", t)
    t = DATE_ISO.sub(lambda m: _date(int(m.group(3)), int(m.group(2)), m.group(1)) or m.group(0), t)
    t = DATE_DMY.sub(lambda m: _date(int(m.group(1)), int(m.group(3)), m.group(4)) or m.group(0), t)
    t = YEAR.sub(_year, t)
    t = CENTURY.sub(_century, t)
    t = _abbreviations(t)
    t = t.translate({ord(c): " " for c in DROP})
    t = DAY_MONTH.sub(_day_month, t)
    t = REGNAL.sub(_regnal, t)
    t = TIME.sub(_time, t)
    t = SCALED.sub(_scaled, t)
    t = MONEY_BEFORE.sub(lambda m: _money(m.group(2), m.group(1)), t)
    t = MONEY_AFTER.sub(lambda m: _money(m.group(1), m.group(2))
                        + (" ." if m.group(2).endswith(".") and not t[m.end():].strip() else ""), t)
    t = PERCENT.sub(lambda m: f" {'минус ' if m.group(1) else ''}"
                    f"{count(m.group(2), ('m', 'процент', 'процента', 'процентов'))} ", t)
    t = UNIT.sub(_unit, t)
    t = ORDINAL.sub(_ordinal, t)
    t = COMPOUND.sub(_compound, t)
    t = RANGE.sub(lambda m: f" от {cardinal_gen(int(m.group(1)))} до {cardinal_gen(int(m.group(2)))} ", t)
    t = PAUSE.sub(" , ", t)
    t = PRODUCT_CODE.sub(lambda m: f" {_spell_code(m.group(0))} ", t)
    t = NUMBER.sub(_number, t)
    t = ACRONYM.sub(_acronym, t)
    t = LATIN.sub(_latin, t)
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = t.replace("-", " ").replace("–", " ").replace("—", " , ")
    out: list[str] = []
    for w in WORD.findall(t.lower()):
        if w in MARKS and out and out[-1] in MARKS:
            continue
        out.append(w)
    return " ".join(_join_clitics(out))
