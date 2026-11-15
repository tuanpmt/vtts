"""Small, extendable lookup tables for text normalization (Northern readings)."""

LETTER_NAMES: dict[str, str] = {
    "a": "a", "b": "bê", "c": "xê", "d": "dê", "đ": "đê", "e": "e", "f": "ép",
    "g": "giê", "h": "hát", "i": "i", "j": "gi", "k": "ca", "l": "e lờ", "m": "em mờ",
    "n": "en nờ", "o": "o", "p": "pê", "q": "quy", "r": "e rờ", "s": "ét xì", "t": "tê",
    "u": "u", "v": "vê", "w": "vê kép", "x": "ích xì", "y": "i dài", "z": "dét",
    "ă": "á", "â": "ớ", "ê": "ê", "ô": "ô", "ơ": "ơ", "ư": "ư",
}

LOANWORDS: dict[str, str] = {
    "wifi": "oai phai",
    "email": "i meo",
    "ok": "ô kê",
    "okay": "ô kê",
    "internet": "in tơ nét",
    "video": "vi đê ô",
    "online": "on lai",
    "offline": "óp lai",
    "app": "áp",
    "smartphone": "xmát phôn",
    "covid": "cô vít",
    "hashtag": "hát tác",
    "ôtô": "ô tô",
    "tivi": "ti vi",
    "taxi": "tắc xi",
    "mini": "mi ni",
    "oxy": "ô xi",
}

# Applied case-sensitively, longest key first, only at word boundaries.
ABBREVIATIONS: dict[str, str] = {
    "TP.HCM": "thành phố hồ chí minh",
    "TPHCM": "thành phố hồ chí minh",
    "TP.": "thành phố",
    "Q.": "quận",
    "P.": "phường",
    "HN": "hà nội",
    "VN": "việt nam",
    "v.v.": "vân vân",
}

UNITS: dict[str, str] = {
    "km": "ki lô mét",
    "kg": "ki lô gam",
    "cm": "xen ti mét",
    "mm": "mi li mét",
    "ml": "mi li lít",
    "m": "mét",
    "g": "gam",
    "l": "lít",
    "°C": "độ xê",
    "°": "độ",
}

CURRENCIES: dict[str, str] = {
    "đ": "đồng", "đồng": "đồng", "vnđ": "đồng", "vnd": "đồng", "usd": "đô la",
}

SYMBOLS: dict[str, str] = {"@": "a còng", "+": "cộng", "=": "bằng", "&": "và"}
