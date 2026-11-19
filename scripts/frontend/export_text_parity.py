"""Write the C front-end parity fixture: sentences the device front-end supports + expected ids.

Usage: uv run python scripts/frontend/export_text_parity.py --sentences FILE... --out runtime/test/text_parity.tsv
       uv run python scripts/frontend/export_text_parity.py --v2 --sentences data/bilingual/sentences.jsonl \
           eval/sets/*.jsonl --out runtime/test/text_parity_v2.tsv
       uv run python scripts/frontend/export_text_parity.py --zh --sentences data/zh/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_zh.tsv
--v2 writes "mode<TAB>text<TAB>ids" lines (phoneme set v2) for vi, en and auto mode; --zh writes the
same format for mode zh (token set zh-en). Without data/zh/sentences.jsonl, --zh generates Chinese
sentences from the reading tables.
       uv run python scripts/frontend/export_text_parity.py --ko --sentences data/ko/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_ko.tsv
--ko does the same for mode ko (token set ko-en); without data/ko/sentences.jsonl it generates Korean
sentences from the eval sets, the templates, the exception table and random syllables.
       uv run python scripts/frontend/export_text_parity.py --hi --sentences data/hi/sentences.jsonl \
           data/hi/probe_src.jsonl --limit 3000 --out runtime/test/text_parity_hi.tsv
--hi does the same for mode hi (token set hi-en): the Wikipedia sentences when present, plus sentences
built by the corpus rules from their words, the templates, the exception table and random aksharas.
       uv run python scripts/frontend/export_text_parity.py --ja --sentences data/ja/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_ja.tsv --nfkc-out runtime/test/ja_nfkc.tsv
--ja does the same for mode ja (token set ja-en); without data/ja/sentences.jsonl it generates Japanese
sentences from the reading tables (words, context keys after kanji and katakana, kanji, kana runs).
--nfkc-out also writes the NFKC fixture of the C reader (every code point NFKC changes and random
sequences with combining marks, half-width kana and Hangul jamo).
       uv run python scripts/frontend/export_text_parity.py --lt es --sentences data/es/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_es.tsv
--lt es|id|pt|it|tr does the same for mode es, id, pt, it or tr (token set es-en, id-en, pt-en, it-en,
tr-en); without a corpus it generates sentences from the eval sets, the templates, the word lists, the
exception table and random words of the language's letters.
       uv run python scripts/frontend/export_text_parity.py --th --out runtime/test/text_parity_th.tsv
       uv run python scripts/frontend/export_text_parity.py --sw --sentences data/sw/sentences.jsonl \
           data/sw/mixed.jsonl --limit 3000 --out runtime/test/text_parity_sw.tsv
--sw does the same for mode sw (token set sw-en): edge cases, the eval sets, the templates, the tests'
strings, corpus sentences, the word lists, number/date/time/money/unit cases and random strings.
--th does the same for mode th (token set th-en): edge cases, the Thai eval sets and unit-test strings,
generated sentences and regex-dense random strings.
       uv run python scripts/frontend/export_text_parity.py --tl --sentences data/tl/sentences.jsonl \
           data/tl/mixed.jsonl --limit 3000 --out runtime/test/text_parity_tl.tsv
--tl does the same for mode tl (token set tl-en): edge cases, the eval sets, the templates, the stress
table words with affixes and clitics, random Tagalog words, numbers and regex-dense random strings.
       uv run python scripts/frontend/export_text_parity.py --fe fi --sentences data/fi/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_fi.tsv
--fe fi|el does the same for mode fi or el (token set fi-en, el-en): edge cases, both eval sets,
template x term sentences, the tests' strings, corpus or generated sentences, every exception and
word-list entry, number/date/time/money/unit cases and regex-dense random strings.
       uv run python scripts/frontend/export_text_parity.py --de --sentences data/de/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_de.tsv
--de does the same for mode de (token set de-en): edge cases, the German eval sets and unit-test strings,
template sentences, corpus sentences, every stem and exception word, pseudo words, numbers and
regex-dense random strings (de_lines).
       uv run python scripts/frontend/export_text_parity.py --ar --sentences data/ar/sentences.jsonl \
           --limit 2000 --out runtime/test/text_parity_ar.tsv
--ar does the same for mode ar (token set ar-en): edge cases, the Arabic eval sets and unit-test strings,
the Wikipedia sentences when present and sentences built from their words, template x term sentences,
every table word with clitics and endings, random (vowelled) words, numbers, dates, times, money and
units, and regex-dense random strings.
       uv run python scripts/frontend/export_text_parity.py --nx nl --sentences data/nl/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_nl.tsv
--nx nl|sv|no does the same for mode nl, sv or no (token set nl-en, sv-en, no-en; see
export_text_parity_nx.py).
"""

import argparse
import re
from pathlib import Path

from vtts.frontend.text import text_to_ids

# not implemented on the device front-end (documented in runtime/README.md)
UNSUPPORTED = re.compile(
    r"@|https?://|www\.|\$|\d{4}-\d{2}-\d{2}|(?<!\d)0\d{2,3}[. ]?\d{3}[. ]?\d{3,4}"
    r"|\d\s?(?:đ|đồng|vnđ|vnd|usd|km|kg|cm|mm|ml|m|g|l|°)(?![^\W\d_])", re.IGNORECASE)


def supported(text: str) -> bool:
    return not UNSUPPORTED.search(text)


V2_EDGE = [
    "Đã kết nối Bluetooth với AirPods, pin còn 80%.", "Mở Spotify và play playlist Chill Vibes nhé.",
    "Chip ESP32-P4 chạy nhanh hơn ESP32-S3.", "Your package arrives on Tuesday, November 18, at 2:30 p.m.",
    "Cuộc họp trên Google Meet lúc 9 giờ, nhớ file PowerPoint nhé.", "It costs $5.50 and weighs 2 kg.",
    "Bật wifi rồi mở app YouTube.", "OK, xong rồi!", "Smartphone và smarthome.", "USB, NASA và iPhone 15.",
    "Gọi cho anh Nam lúc 7:30 sáng mai.", "Meeting with Lan at 3pm tomorrow.", "Tốc độ 150 Mbps, ping 20 ms.",
    "Hello. Xin chào! How are you? Bạn khỏe không;", "TP.HCM và HN.", "e-mail, x-ray, well-known.",
    "Don't stop. It's 5 o'clock.", "...", "", "a", "Đ", "100%", "ChatGPT, McDonald's và IoT.",
    "Câu rất dài " + "một hai ba bốn năm sáu bảy tám chín mười " * 6 + "hết.",
    "A very long English sentence " + "with many words that keep going on and on " * 6 + "until the end.",
]


def v2_lines(paths: list[Path], limit: int | None) -> list[str]:
    import json
    import random

    rows = []
    for p in paths:
        for x in p.read_text(encoding="utf-8").splitlines():
            if x.strip():
                rows.append(json.loads(x))
    rnd = random.Random(0)
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    cases = [("vi", t) for t in V2_EDGE] + [("en", t) for t in V2_EDGE] + [("auto", t) for t in V2_EDGE]
    for r in rows:
        mode = "en" if r.get("lang") == "en" else "vi"
        cases.append((mode, r["text"]))
        if rnd.random() < 0.3:
            cases.append(("auto", r["text"]))
    out = []
    for mode, text in cases:
        text = text.replace("\t", " ").replace("\n", " ")
        if mode != "en" and not supported(text):  # Vietnamese device normalizer subset, as for v1
            continue
        out.append(f"{mode}\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, mode)))
    return out


ZH_EDGE = [
    "你好，世界！", "第一、第二；第三：完。", "他说：“好的”（真的）", "共123个", "圆周率3.14", "0.5倍", "增长15%",
    "增长１５％", "2026年", "11月18日", "2026-11-18", "9:30开会", "9:05", "18:00", "气温-5度", "电话13812345678",
    "人口1,250,000", "3~5天", "价格¥99", "25℃", "ESP32-P4芯片", "5G网络", "好……吧", "打开Wi-Fi设置。",
    "请发 email 给我", "打开 Wi-Fi，然后重启。", "，你好", "打开 smart home 模式", "ESP32-P4有2个核",
    "Turn on the Wi-Fi.", "银行行长说，这个行业很重要。", "我们今天去公园散步然后回家吃饭" * 30 + "。",
    "会议在2026年11月18日上午9:30开始，预计持续2个小时。", "这台电脑的价格是$1,299.99，比去年便宜了15.5%。",
    "今天北京的气温是-3℃到5℃，明天会降到-8°C。", "他的电话号码是13900001111，邮箱是me@example.com。",
    "温度为30°c，湿度为85 %。", "比分是3-2，时间是12:30:45。", "现在是00:00:00，也就是午夜。", "第24:00和25:00和1:5。",
    "2024/1/1和2024.12.31和2024-13-45和12024-1-1。", "1998年 和 2008 年 和 12345年。", "我有€50和£20和¥ 1,000。",
    "数字1.2.3和1,23和1,234,5678和0.0和00.5和.5。", "负数-1.5和-1,000和a-1和1-2-3。", "C++和R&D和Q&A。",
    "Python3和USB3.0和RTX3060和i7和A1B2C3D4。", "iPhone 15 Pro Max的价格是7999元。", "我喜欢看NBA和听K-pop。",
    "他是CEO，也是一名AI工程师。", "打开ChatGPT然后问它一个问题。", "我们用Zoom开会，用Slack聊天。",
    "这个APP叫TikTok，在中国叫抖音。", "WiFi密码是abc123。", "下载PDF文件到Downloads文件夹。",
    "一二三四五六七八九十", "不要不要不要！", "今天天气很好；明天会下雨？后天呢！", "嗯……这个——怎么说呢。",
    "《红楼梦》是一部「经典」小说『作品』【推荐】〔注〕〈好〉。", "价格：￥１２８．５０元", "１２：３０开会",
    "ｈｅｌｌｏ　ｗｏｒｌｄ", "他说：“Hello, world!”然后走了。", "这是第100,000,000,000,000,000,000个。",
    "12345678901234567890123", "100000000和120000000和100005000和10010和1010和110和105和15和10和0",
    "1万和3.5亿", "A股和B站", "OK", "ok好的", "Hi，你好！", "...", "", "。", "a", "中", "𠀀字", "かな和한국어",
    "Việt Nam和中国", "café和naïve", "don't和it's和o'clock", "e-mail和x-ray", "3:30pm和9 a.m.",
    "9:30, 10:45 和 11:00。", "2 + 3 = 5", "100%和50 % 和-20%", "$5 million", "第1名和第2名", "1/2和3/4",
    "Hello. 你好！How are you? 我很好；谢谢。", "  前后有空格  ", "多个\t制表符", "全角　空格",
    "长" + "很" * 400 + "。", "数字" + "1234567890" * 20 + "。", "Very long English " + "words " * 80 + "end.",
]


def _zh_generated(n: int, rnd) -> list[str]:
    """Sentences built from the reading tables (no Chinese corpus in the repository): phrases,
    single characters, digits, Latin words and punctuation."""
    from vtts.frontend.zh.g2p_zh import char_table, phrase_table

    phrases, chars = sorted(phrase_table()), sorted(char_table())
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1"]
    numbers = ["3", "15", "100", "2026年", "3.5", "1,000", "50%", "9:30", "¥20", "-7", "2024-05-01", "3~5",
               "12345678", "25℃", "第2"]
    marks = ["，", "。", "！", "？", "；", "：", "、", ",", ".", " ", "……", "“", "”"]
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 12)):
            r = rnd.random()
            if r < 0.45:
                parts.append(rnd.choice(phrases))
            elif r < 0.8:
                parts.append("".join(rnd.choice(chars) for _ in range(rnd.randint(1, 4))))
            elif r < 0.87:
                parts.append(rnd.choice(numbers))
            elif r < 0.92:
                parts.append(rnd.choice(latin))
            else:
                parts.append(rnd.choice(marks))
        out.append("".join(parts) + rnd.choice(["。", "！", "？", "", "."]))
    return out


def _zh_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalize_zh regex passes react to."""
    atoms = (list("0123456789") * 4 + list(":/.,-~%'+&@ ") * 2
             + ["年", "月", "日", "点", "中", "国", "°", "°C", "°c", "℃", "¥", "$", "€", "£", "￥", "％", "：",
                "，", "。", "！", "？", "；", "…", "—", "“", "”", "（", "）", "　", "１", "Ａ", "ESP", "A", "B",
                "Z", "x", "ab", "Ok", "Wi", "é", " ", "  "])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def zh_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode "zh" cases: edge cases, the mixed-style sentences (templates_zh x terms_en), Chinese
    sentences (data/zh/sentences.jsonl when given and present, else generated from the reading
    tables), number/date/time cases and regex-dense random strings."""
    import json
    import random

    rnd = random.Random(0)
    here = Path(__file__).parents[2] / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_zh.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(ZH_EDGE) + rnd.sample(mixed, min(len(mixed), 2000))
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows if rows else _zh_generated(limit or 3000, rnd)
    nums = []
    for _ in range(1500):
        k = rnd.randint(0, 9)
        v = rnd.choice([rnd.randint(0, 99), rnd.randint(0, 99999), rnd.randint(0, 10**12), rnd.randint(0, 10**20)])
        nums.append(["共{}个", "{:,}元", "增长{}.5%", "¥{}", "第{}名", "-{}度", "{}年", "{}~{}天", "{}:{}", "{}-{}-{}"][k]
                    .format(v, rnd.randint(0, 60), rnd.randint(0, 40)))
    for _ in range(300):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)}"
                    f"和{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _zh_regex_fuzz(fuzz, rnd)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        out.append(f"zh\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, "zh")))
    return out


KO_EDGE = [
    "안녕하세요, 세계!", "첫째, 둘째; 셋째: 끝.", "그는 “좋아요”(정말)라고 했다.", "사과 3개", "학생 2명", "스무 살, 20살",
    "4마리와 3시간", "1번째와 2번째", "350원", "1,250달러", "10번", "2026년 11월 18일", "6월과 10월", "2026-06-10",
    "2026. 6. 10.", "2026.10.3", "9:30", "18:00", "12:30:45", "0:05", "3.14", "15%", "-5도", "010-1234-5678", "02-123-4567",
    "0123", "₩5,000", "$20", "€3.5", "¥100", "£7", "25℃", "30°C", "5km", "3kg", "500ml", "2L", "16GB", "1.5m", "3~5개",
    "10-20명", "3 ~ 5 개", "ESP32-P4", "5G", "Wi-Fi를 켜고", "iPhone 15 Pro", "e-mail과 x-ray", "R&D와 Q&A", "C++",
    "A+", "me@example.com", "국물 좋아", "학교 국밥 앉다 읽고 넓다", "같이 굳이 닫히다", "좋다 닿소 놓는 좋아",
    "축하 입학 앉히다", "한국어 앉아 값을", "부엌 닭 읽고", "종로 담력 국물 십만 독립", "신라 칼날 희망 가져",
    "물고기를 김밥 솜이불 의견란 갈등", "밟다 밟고 넓죽 삶과 닭고기", "ㅋㅋㅋ 정말요?", "漢字와 한글", "かな와 한국어",
    "Việt Nam과 한국", "café와 naïve", "don't와 it's", "안녕。 잘 가！ 뭐？ 네；끝", "음…… 그게——뭐랄까.",
    "《책》「인용」『제목』【추천】〔주〕〈좋아〉", "ｈｅｌｌｏ　ｗｏｒｌｄ", "１２：３０에 만나요", "가격：￦１２８",
    "Hello. 안녕! How are you? 잘 지내요; 감사합니다.", "  앞뒤 공백  ", "여러\t탭", "...", "", "。", "a", "가",
    "아주 " + "길고 " * 200 + "끝.", "가" * 400 + "다.", "숫자 " + "1234567890" * 20 + "개.",
    "Very long English " + "words " * 80 + "end.", "1,234,5km와 1,2345원", "1.2.3과 1,23과 1,234,5678",
    "00시 00분", "24:00과 25:00과 1:5", "2024-13-45와 2024-1-1과 12024-1-1", "1월 2월 3월 4월 5월 6월 7월 8월 9월 10월 11월 12월",
    "06월 010월 6월에", "1번째 11번째 1번 1개 0개 100개 99개 20개 21개", "3~5시간 1~2번째 100~200개 3-5살",
    "-3.5% 와 - 5%", "2,000,000,000,000,000,000,000원", "100000000000000000000000",
    "100000000과 120000000과 100005000과 10010과 1010과 110과 105과 15와 10과 0",
    "만 원 1만 원 10000원 11000원", "3.5억", "A1B2C3", "USB3.0과 RTX3060", "GPT-4o와 Llama3", "OK 좋아요",
    "Hi, 안녕하세요!", "스마트 홈 smart home 모드", "9시 30분에 일어나요.", "1시간 30분", "2시 반",
]


def _ko_vocab() -> list[str]:
    """Korean words (어절) from the eval sets, the code-switching templates and the exception table."""
    import json

    root = Path(__file__).parents[2]
    words: set[str] = set()
    for name in ("ood_ko.jsonl", "mixed_ko.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                words.update(json.loads(x)["text"].split())
    for t in (root / "scripts" / "data" / "bilingual" / "templates_ko.txt").read_text(encoding="utf-8").splitlines():
        words.update(t.replace("{T}", " ").split())
    from vtts.frontend.ko.g2p_ko import override_table

    for k in override_table():
        words.update({k, k + "를", k + "이", k + "과", k + "에서"})
    return sorted(w for w in words if any("가" <= c <= "힣" for c in w))


def _ko_generated(n: int, rnd) -> list[str]:
    """Sentences from the vocabulary, random Hangul syllables, numbers with counters, Latin words and
    punctuation (no Korean corpus in the repository)."""
    from vtts.frontend.ko.normalize_ko import JOINED, NATIVE_COUNTERS, SINO_COUNTERS

    vocab = _ko_vocab()
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1", "smart"]
    counters = list(NATIVE_COUNTERS + SINO_COUNTERS + JOINED) + ["", "이", "를", "에서", "은"]
    particles = ["", "", "은", "는", "이", "가", "을", "를", "에", "에서", "으로", "와", "과", "도", "만", "의"]
    marks = [",", ".", "!", "?", ";", ":", "…", "·", "“", "”", "(", ")"]
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 12)):
            r = rnd.random()
            if r < 0.5:
                parts.append(rnd.choice(vocab))
            elif r < 0.7:
                parts.append("".join(chr(0xAC00 + rnd.randrange(11172)) for _ in range(rnd.randint(1, 4)))
                             + rnd.choice(particles))
            elif r < 0.85:
                v = rnd.choice([rnd.randint(0, 30), rnd.randint(0, 100), rnd.randint(0, 99999), rnd.randint(0, 10**9)])
                sep = rnd.choice(["", "", " "])
                parts.append(f"{v}{sep}{rnd.choice(counters)}")
            elif r < 0.92:
                parts.append(rnd.choice(latin) + rnd.choice(particles))
            else:
                parts.append(rnd.choice(marks))
        out.append(" ".join(parts) + rnd.choice([".", "!", "?", "", "。"]))
    return out


def _ko_pairs(rnd) -> list[str]:
    """Every (coda, next onset, next vowel) of two adjacent syllables, 20 two-syllable words per line,
    and random three-syllable words: covers every branch of the pronunciation rules."""
    words = []
    for coda in range(28):
        for onset in range(19):
            for vowel in range(21):
                first = 0xAC00 + (rnd.randrange(19) * 21 + rnd.randrange(21)) * 28 + coda
                words.append(chr(first) + chr(0xAC00 + (onset * 21 + vowel) * 28 + rnd.randrange(28)))
    rnd.shuffle(words)
    words += ["".join(chr(0xAC00 + rnd.randrange(11172)) for _ in range(3)) for _ in range(4000)]
    return [" ".join(words[i:i + 20]) + "." for i in range(0, len(words), 20)]


def _ko_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalize_ko regex passes react to."""
    atoms = (list("0123456789") * 4 + list(":/.,-~%'+&@ ") * 2
             + ["년", "월", "일", "시", "분", "개", "명", "번째", "살", "개월", "가", "한", "°", "°C", "°c", "℃", "₩", "$",
                "€", "¥", "£", "￦", "％", "：", "，", "。", "！", "？", "；", "…", "—", "·", "ㆍ", "“", "”", "（", "）",
                "　", "１", "Ａ", "ESP", "A", "B", "Z", "x", "ab", "Ok", "Wi", "km", "kg", "m", "g", "l", "L", "GB", "MB",
                "ml", "é", "ㅋ", " ", "  "])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def ko_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode "ko" cases: edge cases, the Korean eval sets, the mixed-style sentences (templates_ko x
    terms_en), Korean sentences (data/ko/sentences.jsonl when given and present, else generated),
    every pair of adjacent syllables, number/date/time cases and regex-dense random strings."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_ko.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(KO_EDGE)
    for name in ("ood_ko.jsonl", "mixed_ko.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows if rows else _ko_generated(limit or 3000, rnd)
    texts += _ko_pairs(rnd)
    from vtts.frontend.ko.normalize_ko import NATIVE_COUNTERS, SINO_COUNTERS

    counters = list(NATIVE_COUNTERS + SINO_COUNTERS)
    nums = []
    for _ in range(2000):
        k = rnd.randint(0, 11)
        v = rnd.choice([rnd.randint(0, 99), rnd.randint(0, 99999), rnd.randint(0, 10**12), rnd.randint(0, 10**22)])
        c = rnd.choice(counters)
        nums.append(["{}" + c, "{} " + c + "을", "{:,}원", "{}.5%", "₩{}", "제{}회", "-{}도", "{}년 {}월 {}일", "{}~{}" + c,
                     "{}:{}", "{}-{}-{}", "0{}"][k].format(v, rnd.randint(0, 60), rnd.randint(0, 40)))
    for _ in range(400):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)}과 "
                    f"{rnd.randint(1900, 2100)}. {rnd.randint(0, 13)}. {rnd.randint(0, 33)}. "
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _ko_regex_fuzz(fuzz, rnd)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        out.append(f"ko\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, "ko")))
    return out


HI_EDGE = [
    "नमस्ते, आप कैसे हैं?", "मैं घर जा रहा हूँ। तुम कहाँ हो॥ ठीक है", "मैं घर जा रहा हूँ।तुम कहाँ हो?", "मेरी उम्र 21 साल है।",
    "मेरी उम्र २१ साल है।", "7:30 पर मिलते हैं", "7:00 बजे", "10:15 बजे आना", "23:59:59", "24:00 और 25:00 और 1:5", "0:05",
    "15/08/1947 को आज़ादी मिली।", "15.08.1947", "15-08-47", "2026-11-19", "2026-13-45 और 12026-1-1", "32/13/2020",
    "सन 1947 में", "सन् 1857 का विद्रोह", "ईस्वी 2026", "हसन 1947", "₹500", "₹ 1,25,000", "₹1.50", "₹1.05", "₹1.5",
    "₹1", "₹01", "₹0.00", "Rs 99", "Rs. 250", "Rs.5", "रु. 250", "रु 40", "INR 1000", "US$ 20", "$20", "$5.50", "€3.5", "£7",
    "₹5 हज़ार", "₹2 लाख", "₹3 करोड़", "₹ 7.5 करोड़", "$5 million", "50%", "50 %", "-20%", "12.5%", "5 km", "128GB", "30°C",
    "30℃", "45°", "100 km/h", "5kWh", "2.5 kg", "500 ml", "1 L", "3 mAh", "2GHz", "5 m", "5 मीटर", "10वीं", "1वाँ", "2वीं",
    "3वें", "4वीं", "6वाँ", "5वां", "21वीं सदी", "10 वें", "1ला", "1st", "10-20", "10 - 20", "10–20", "5-10 लोग", "1-2-3",
    "9876543210", "+91 98765 43210", "+91-98765-43210", "011-2345-6789", "12345", "12 34 56", "1234567890123",
    "ESP32", "ESP32-P4", "5G", "A1B2C3", "USB3.0", "RTX3060", "GPT-4o", "1,25,000", "125,000", "1,00,00,000",
    "10000000000", "999999999999999", "1000000000000000", "12345678901234567890", "0", "00", "007", "3.14", "0.5", ".5",
    "-5", "-3.5", "x-5", "5.", "1.2.3", "1,2345", "1,23,4567", "डॉ. शर्मा", "प्रो. वर्मा", "5 कि.मी.", "2 कि.ग्रा.",
    "नं. 5", "पृ. 10", "लि.", "स्व. नेहरू", "R&D", "C++", "2 + 3 = 5", "3 × 4", "a@b.com", "राम-श्याम", "और... फिर",
    "वह — जो", "हाँ…", "“उद्धरण” (कोष्ठक) [वर्ग] {घुँघराले} <कोण>", "¿क्या? ¡हाँ!", "*जोर* _रेखा_ ~लहर~ |पाइप|",
    "मुझे YouTube पर वीडियो देखना है।", "मैंने laptop पर software update कर दिया।", "Wi-Fi को चालू करो।",
    "मेरा फ़ोन 5G है", "YouTube खोलो, please.", "Turn on the Wi-Fi.", "Hello. नमस्ते! How are you? मैं ठीक हूँ; धन्यवाद।",
    "km", "GB", "Rs", "km/h", "मेरा iPhone 15 Pro है", "don't और it's और o'clock", "e-mail और x-ray", "café और naïve",
    "Ǆ ß Æ Œ ĳ ſ", "Ω ω Ж ж", "中文 और 한국어", "Việt Nam", "x²", "½", "ज़रूरी", "ज़रूरी", "फ़िल्म", "फ़िल्म", "ड़", "ड़",
    "ऩ", "ऩ", "क़िला", "ख़ुशी", "ग़लत", "य़", "ऱ", "ऴ", "हिंदी", "ठंडा", "दांत", "संसार", "में", "कमला", "समझना", "सत्य",
    "मित्र", "न", "ज्ञान", "क्षमा", "श्री", "ऋषि", "कृष्ण", "दुःख", "दुःख", "ॐ", "ऑफ़िस", "कॉफ़ी", "ऍ", "ॲ", "क्", "क्‍ष",
    "क्‌ष", "क़्", "क़्", "ज़्ञ", "अंधेरा", "पंख", "चंचल", "घंटा", "अंत", "कंबल", "संयम", "सिंह", "कांड", "हँसना", "आँख",
    "उन्होंने", "इंग्लैंड", "दुःख-सुख", "प्रातः", "अतः", "उदाहरण", "उदाहरणों", "असफल", "असफलता", "राष्ट्रपति", "करोड़पति",
    "अ", "आ", "ा", "ि", "्", "़", "ं", "ँ", "ः", "ऽ", "॰", "।", "॥", "०१२३४५६७८९", "१०:३०", "₹१,२५,०००", "२०२६-११-१९",
    "...", "", "।", "a", "क", "  आगे पीछे खाली  ", "कई\tटैब", "बहुत " * 120 + "लंबा।", "क" * 200 + "।",
    "संख्या " + "1234567890" * 20 + "।", "Very long English " + "words " * 80 + "end.",
    "हम हर रविवार को पार्क में घूमने जाते हैं और वहाँ बच्चों के साथ खेलते हैं " * 6 + "।",
]


def _hi_vocab(paths: list[Path]) -> list[str]:
    """Hindi words of the given sentence files, the templates, the tests' sentences and the exception
    table (with case suffixes)."""
    import json

    root = Path(__file__).parents[2]
    words: set[str] = set()
    for p in paths:
        if p.exists():
            for x in p.read_text(encoding="utf-8").splitlines():
                if x.strip():
                    words.update(json.loads(x)["text"].split())
    for t in (root / "scripts" / "data" / "bilingual" / "templates_hi.txt").read_text(encoding="utf-8").splitlines():
        words.update(t.replace("{T}", " ").split())
    for name in ("test_hi_g2p.py", "test_normalize_hi.py", "test_text_hi.py"):
        words.update(re.findall(r"[\u0900-\u0963\u0971-\u097f]+", (root / "tests" / "frontend" / name).read_text(encoding="utf-8")))
    from vtts.frontend.hi.g2p_hi import override_table

    for k in override_table():
        words.update({k, k + "ों", k + "ें", k + "ी", k + "ा"})
    return sorted(w.strip(".,?!") for w in words if any("\u0900" <= c <= "\u097f" for c in w) and w.strip(".,?!"))


_HI_CONS = "कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ"
_HI_MATRAS = ["", "", "", "ा", "ि", "ी", "ु", "ू", "े", "ै", "ो", "ौ", "ृ", "ॅ", "ॉ", "्"]
_HI_SIGNS = ["", "", "", "", "", "ं", "ँ", "ः", "़"]
_HI_VOWELS = "अआइईउऊएऐओऔऋऑ"


def _hi_akshara(rnd) -> str:
    r = rnd.random()
    if r < 0.08:
        return rnd.choice(_HI_VOWELS) + rnd.choice(_HI_SIGNS)
    c = rnd.choice(_HI_CONS)
    if rnd.random() < 0.08:
        c += "़"
    if rnd.random() < 0.15:  # conjunct
        c += "्" + rnd.choice(_HI_CONS)
    return c + rnd.choice(_HI_MATRAS) + rnd.choice(_HI_SIGNS)


def _hi_words(rnd) -> list[str]:
    """Random words of 1-6 aksharas, 20 per line: every branch of the schwa-deletion, nasal and
    nukta rules."""
    words = ["".join(_hi_akshara(rnd) for _ in range(rnd.randint(1, 6))) for _ in range(12000)]
    return [" ".join(words[i:i + 20]) + "." for i in range(0, len(words), 20)]


def _hi_generated(vocab: list[str], n: int, rnd) -> list[str]:
    """Sentences by the Wikipedia corpus rules (vtts.data.wiki_corpus: Devanagari words, intra-word
    hyphens, , . ? !, 5-30 words, ending with . ? !), plus some with numbers and Latin words."""
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "laptop",
             "software", "update", "YouTube", "km", "GB", "Rs"]
    out = []
    for k in range(n):
        words = []
        for _ in range(rnd.randint(5, 30)):
            w = rnd.choice(vocab)
            if rnd.random() < 0.04:
                w += "-" + rnd.choice(vocab)
            if rnd.random() < 0.08:
                w += ","
            words.append(w)
        if k % 3 == 0:  # mixed: numbers and Latin words
            for _ in range(rnd.randint(1, 3)):
                pos = rnd.randrange(len(words) + 1)
                v = rnd.choice([str(rnd.randint(0, 100)), str(rnd.randint(0, 10 ** 7)), rnd.choice(latin),
                                f"{rnd.randint(1, 28)}/{rnd.randint(1, 12)}/{rnd.randint(1900, 2100)}",
                                f"{rnd.randint(0, 23)}:{rnd.randint(0, 59):02d}", f"₹{rnd.randint(1, 99999)}",
                                f"{rnd.randint(1, 99)}%", "सन " + str(rnd.randint(1000, 2100))])
                words.insert(pos, v)
        out.append(" ".join(words) + rnd.choice([".", "?", "!", "।", "।", "॥"]))
    return out


def _indian(v: int) -> str:
    """Indian digit grouping: 1,25,000."""
    head, tail = str(v)[:-3], str(v)[-3:]
    groups = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(groups + [tail])


def _hi_numbers(rnd) -> list[str]:
    def dev(t: str) -> str:
        return t.translate(str.maketrans("0123456789", "०१२३४५६७८९"))

    out = []
    for _ in range(2500):
        k = rnd.randint(0, 17)
        v = rnd.choice([rnd.randint(0, 99), rnd.randint(0, 99999), rnd.randint(0, 10 ** 9), rnd.randint(0, 10 ** 13),
                        rnd.randint(0, 10 ** 20)])
        a, b = rnd.randint(0, 40), rnd.randint(0, 70)
        indian = _indian(v)
        t = ["कुल {} लोग", "{:,} रुपये", "₹{}", "₹" + indian, "{}.5%", "{} km", "{}GB", "{}वीं बार", "{}-{} दिन",
             "{}:{} बजे", "{}/{}/{}", "सन {}", "-{} डिग्री", "{}.{}", "फ़ोन 98{}", "+91 {}", "Rs {}", "{} से {}"][k]
        text = t.format(v, a, b) if "{" in t else t
        out.append(dev(text) if rnd.random() < 0.25 else text)
    for _ in range(500):
        out.append(f"{rnd.randint(1, 35)}/{rnd.randint(0, 13)}/{rnd.choice([rnd.randint(0, 99), rnd.randint(1000, 2999)])} और "
                   f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} को "
                   f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    return out


def _hi_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalize_hi regex passes react to."""
    atoms = (list("0123456789") * 4 + list(":/.,-–%'+&@=×° ") * 2
             + ["०", "५", "९", "।", "॥", "॰", "बजे", "सन", "सन्", "ईस्वी", "हज़ार", "लाख", "करोड़", "वाँ", "वीं", "वें", "वे",
                "₹", "Rs", "Rs.", "रु.", "रु", "INR", "US$", "$", "€", "£", "km", "km/h", "m", "g", "GB", "kWh", "°C", "℃",
                "डॉ.", "कि.मी.", "नं.", "…", "—", "...", "“", "”", "(", ")", "ESP", "A", "B", "Z", "x", "ab", "Ok", "é",
                "क", "ा", "ं", " ", "  ", "\u00a0", "+91", "_"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def hi_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode "hi" cases: edge cases, Hindi sentences (the given files when present) and sentences built
    by the corpus rules from their words, the mixed-style sentences (templates_hi x terms_en), random
    words (schwa deletion, nasals, nukta), number/date/time/money cases and regex-dense random strings."""
    import json
    import random

    rnd = random.Random(0)
    here = Path(__file__).parents[2] / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_hi.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(HI_EDGE)
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _hi_generated(_hi_vocab(paths), 2000, rnd)
    texts += _hi_words(rnd)
    texts += _hi_numbers(rnd)
    texts += _hi_regex_fuzz(fuzz, rnd)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        out.append(f"hi\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, "hi")))
    return out


JA_EDGE = [
    "こんにちは、世界！", "第一、第二；第三：完。", "彼は「いいよ」（本当に）と言った。", "りんごを3個ください。",
    "学生が2人います。", "1人、2人、3人、4人、7人、10人", "鉛筆が1本、2本、3本、6本、8本、10本、100本、1000本",
    "犬が1匹、3匹、6匹", "コーヒーを1杯、3杯", "3分の1と5分の2", "1分、3分、4分、6分、10分、30分",
    "1階、3階、8階", "1軒と3軒", "1冊、8冊、10冊", "20歳と20才と6歳", "1か月と3ヶ月と6カ月と8ケ月", "5カ国と1ヶ国",
    "1,250円", "4年と14年", "4時と7時と9時、4時間", "4月7月9月と11月1日と1日と14日と20日と24日", "2日間と10日間と24日間",
    "1つ、2つ、9つ、10個、11", "13秒", "3度", "1番目と1番", "2枚", "3台", "5名", "2倍", "3号", "1位", "3割",
    "2026年11月18日", "2026-11-18", "2026/1/1と2026.12.31と2024-13-45と12024-1-1", "9:30", "18:00", "12:30:45",
    "0:05", "24:00と25:00と1:5", "3.14", "15%", "-5度", "マイナス5", "03-1234-5678", "090-1234-5678", "0123", "00",
    "¥5,000", "$20", "€3.5", "£7", "25℃", "30°C", "5km", "3kg", "500ml", "2L", "16GB", "1.5m", "100km/h", "3〜5個",
    "10-20人", "3 ~ 5 個", "1万", "3万5000", "1.5万", "3億2000万", "1兆", "12345万", "1万2345", "1万23456", "0万",
    "1.00001万", "0.000000001万", "123456789012345678万", "1億1.5万", "3万⁠12345", "1.1万", "٣万", "１．５万",
    "$9,3926", "¥1,26٣9", "$1,234567", "€1,234.5678,9","ESP32-P4", "5G", "Wi-Fiを設定",
    "iPhone 15 Pro", "e-mailとx-ray", "R&DとQ&A", "C++", "A+", "me@example.com", "2+3=5", "4×5と6÷2", "rock-'n'-roll-",
    "東京へ行きます。", "日本人とアメリカ人", "今日は一日中雨でした。", "戦後に", "人々と時々と山々", "々から始まる",
    "川と小川", "コンピューターとスーパー", "ヴァイオリンとティーとウィキ", "きゃきゅきょ", "ゃゅょっん", "ーあー", "ゝゞヽヾ",
    "いすゞ", "ｱｲｳｴｵ ｶﾞｷﾞ ﾊﾟﾋﾟ", "ｺﾝﾋﾟｭｰﾀｰ", "がと゛", "①②③", "㍻と㍼", "㌔㍍", "Ⅷ", "ﬁle", "１２：３０に会いましょう",
    "ｈｅｌｌｏ　ｗｏｒｌｄ", "価格：￥１２８", "漢字とかな", "한국어とかな", "中文和日本語", "Việt Namと日本", "caféとnaïve",
    "don'tとit's", "こんにちは。 さようなら！ 何？ はい；終わり", "うーん……それは——どうかな。", "《本》「引用」『題名』【おすすめ】〔注〕〈良い〉",
    "Hello. こんにちは！How are you? 元気です；ありがとう。", "  前後に空白  ", "複数の\tタブ", "...", "", "。", "a", "あ", "ア", "亜",
    "とても" + "長い" * 200 + "文。", "あ" * 400 + "。", "ア" * 300 + "。", "数字" + "1234567890" * 20 + "個。",
    "Very long English " + "words " * 80 + "end.", "1,234,5kmと1,2345円", "1.2.3と1,23と1,234,5678", "٣個と٣٤円",
    "1,000,000,000,000,000,000円", "100000000000000000000000", "123456789012345678本", "12345678901234567本",
    "1万円と10000円と11000円", "A1B2C3", "USB3.0とRTX3060", "GPT-4oとLlama3", "OKです", "Hi、こんにちは！",
    "スマートホーム smart home モード", "9時30分に起きます。", "1時間30分", "2時半", "〆切は月末です。", "ヶ月",
    "日本語のテキストを音声に変換します。", "今日、明日、明後日", "お茶とご飯", "一人と二人", "大人と子供",
]


def _ja_generated(n: int, rnd) -> list[str]:
    """Sentences built from the reading tables (no Japanese corpus in the repository): table words,
    context keys after a kanji or katakana word, single kanji, kana runs, numbers with counters,
    Latin words and punctuation."""
    from vtts.frontend.ja.g2p_ja import tables
    from vtts.frontend.ja.normalize_ja import COUNTERS

    t = tables()
    words, kanji = sorted(t.words), sorted(t.kanji)
    after_k, after_kt = sorted(t.after["kanji"]), sorted(t.after["katakana"])
    hira = [chr(c) for c in range(0x3041, 0x3097)]
    kata = [chr(c) for c in range(0x30A1, 0x30FB)] + ["ー"]
    katakana_words = ["コンピューター", "アメリカ", "テレビ", "スマホ", "メール", "パソコン", "ニュース", "カメラ"]
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1", "smart"]
    counters = list(COUNTERS) + ["", "", "人", "円"]
    particles = ["", "", "は", "が", "を", "に", "で", "と", "の", "も", "へ", "から", "まで", "です", "ます"]
    marks = ["、", "。", "！", "？", "；", "：", ",", ".", " ", "…", "「", "」", "・", "ー"]
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 12)):
            r = rnd.random()
            if r < 0.35:
                parts.append(rnd.choice(words) + rnd.choice(particles))
            elif r < 0.45:
                parts.append(rnd.choice(kanji) + rnd.choice(after_k))
            elif r < 0.52:
                parts.append(rnd.choice(katakana_words) + rnd.choice(after_kt))
            elif r < 0.62:
                parts.append("".join(rnd.choice(kanji) for _ in range(rnd.randint(1, 4))) + rnd.choice(["", "々"]))
            elif r < 0.72:
                pool = rnd.choice([hira, kata])
                parts.append("".join(rnd.choice(pool) for _ in range(rnd.randint(1, 14))))
            elif r < 0.85:
                v = rnd.choice([rnd.randint(0, 30), rnd.randint(0, 100), rnd.randint(0, 99999), rnd.randint(0, 10**9)])
                parts.append(f"{v}{rnd.choice(['', '', ' '])}{rnd.choice(counters)}")
            elif r < 0.92:
                parts.append(rnd.choice(latin) + rnd.choice(particles))
            else:
                parts.append(rnd.choice(marks))
        out.append("".join(parts) + rnd.choice(["。", "！", "？", "", "."]))
    return out


def _ja_context(rnd) -> list[str]:
    """Every context-table key after a kanji (and after 々) or after a katakana word, and every word
    key after a kanji, a katakana and a hiragana, 12 per line: covers the choice between the context
    and the main table."""
    from vtts.frontend.ja.g2p_ja import tables

    t = tables()
    kanji = sorted(t.kanji)
    kata = ["アメリカ", "コーヒー", "テレビ", "パン", "ゲーム", "ニュース"]
    items = [rnd.choice(kanji) + k for k in t.after["kanji"]]
    items += [rnd.choice(kanji) + "々" + k for k in rnd.sample(sorted(t.after["kanji"]), 500)]
    items += [rnd.choice(kata) + k for k in t.after["katakana"]]
    sample = rnd.sample(sorted(t.words), 6000)
    items += [rnd.choice([rnd.choice(kanji), rnd.choice(kata), "の", ""]) + k + rnd.choice(["", "に", "の", "ー"])
              for k in sample]
    rnd.shuffle(items)
    return ["".join(items[i:i + 12]) + "。" for i in range(0, len(items), 12)]


def _ja_kana(rnd) -> list[str]:
    """Every pair of kana (hiragana and katakana, with ー and the iteration marks) inside a kana run."""
    from vtts.frontend.ja.kana import PAIRS, SINGLE, to_katakana

    singles = list(SINGLE) + ["ー", "ゝ", "ゞ"]
    pairs = list(PAIRS) + [a + b for a in singles for b in rnd.sample(singles, 12)]
    words = []
    for pr in pairs:
        w = rnd.choice(singles) + pr + rnd.choice(["", "ー", "っ", "ん"])
        words.append(w if rnd.random() < 0.5 else to_katakana(w))
    rnd.shuffle(words)
    return ["、".join(words[i:i + 15]) + "。" for i in range(0, len(words), 15)]


def _ja_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalize_ja regex passes react to."""
    atoms = (list("0123456789") * 4 + list(":/.,-~%'+&@= ") * 2
             + ["年", "月", "日", "時", "分", "秒", "本", "人", "円", "個", "つ", "か月", "分の", "万", "億", "兆", "ガツ",
                "の", "ア", "ー", "々", "°", "°C", "°c", "℃", "¥", "$", "€", "£", "￥", "％", "：", "，", "。", "！", "？",
                "；", "…", "‥", "—", "―", "・", "「", "」", "（", "）", "　", "１", "Ａ", "〜", "～", "×", "÷", "⁠",
                "ESP", "A", "B", "Z", "x", "ab", "Ok", "Wi", "km", "kg", "m", "g", "l", "L", "GB", "MB", "ml", "mL",
                "km/h", "é", "٣", " ", "  "])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def ja_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode "ja" cases: edge cases, the Japanese eval sets, the mixed-style sentences (templates_ja x
    terms_en), Japanese sentences (data/ja/sentences.jsonl when given and present, else generated
    from the reading tables), the context tables, kana pairs, number/date/time cases and regex-dense
    random strings."""
    import json
    import random

    from vtts.frontend.ja.normalize_ja import COUNTERS

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_ja.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(JA_EDGE)
    for name in ("ood_ja.jsonl", "mixed_ja.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows if rows else _ja_generated(limit or 3000, rnd)
    texts += _ja_context(rnd) + _ja_kana(rnd)
    counters = list(COUNTERS)
    nums = []
    for _ in range(2500):
        k = rnd.randint(0, 13)
        v = rnd.choice([rnd.randint(0, 30), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**12),
                        rnd.randint(0, 10**22)])
        c = rnd.choice(counters)
        nums.append(["{}" + c, "{} " + c + "を", "{:,}円", "{}.5%", "¥{}", "第{}回", "-{}度", "{}年{}月{}日", "{}~{}" + c,
                     "{}:{}", "{}-{}-{}", "0{}", "{}万{}", "{}.{}億"][k].format(v, rnd.randint(0, 60), rnd.randint(0, 40)))
    for _ in range(400):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)}と"
                    f"{rnd.randint(0, 13)}月{rnd.randint(0, 33)}日、"
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _ja_regex_fuzz(fuzz, rnd)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        out.append(f"ja\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, "ja")))
    return out


def nfkc_lines(rnd) -> list[str]:
    """NFKC fixture (hex code points in, out): every code point NFKC changes (one per line) and
    random sequences of characters that compose, reorder or decompose."""
    import sys
    import unicodedata

    def hexs(t: str) -> str:
        return " ".join(f"{ord(c):X}" for c in t)

    singles = [chr(c) for c in range(sys.maxunicode + 1) if not 0xD800 <= c <= 0xDFFF
               and unicodedata.normalize("NFKC", chr(c)) != chr(c)]
    marks = [chr(c) for c in range(0x300, 0x370)] + ["゙", "゚", "̣", "ཱ", "ְ"]
    pool = (singles + marks * 20 + [chr(c) for c in range(0x1100, 0x1200)] * 2 + list("aeiouAEIOUnckかきくはひふカキハヒﾊｶ")
            * 30 + [chr(0xAC00 + rnd.randrange(11172)) for _ in range(300)])
    seqs = ["".join(rnd.choice(pool) for _ in range(rnd.randint(1, 10))) for _ in range(8000)]
    return [f"{hexs(t)}\t{hexs(unicodedata.normalize('NFKC', t))}" for t in singles + seqs]


LT_EDGE = [
    "", ".", "...", "¿?", "¡!", "a", "A", "x", "Y", "ñ", "é", "'", "-", "--", "¿Qué?", "¡Hola!", "Hola. Adiós.",
    "  espacios  ", "múltiples\ttabuladores", "línea\nnueva", "Wi-Fi", "iPhone 15 Pro", "ESP32-P4", "RTX3060",
    "USB, GPS y NASA.", "ONU OTAN ASEAN NATO ENEM", "GitHub y YouTube", "smart home", "weekend", "update", "e-mail",
    "don't", "it's", "x-ray", "ABCDEF", "AB", "ABCDE", "A1B2C3", "a1b2", "_x_", "x_y", "C++", "R&D", "Q&A", "2 + 3 = 5",
    "a@b.com", "#1", "3 × 4", "1/2", "10%", "10 %", "-10%", "50,5%", "1.000.000", "1,000,000", "1.234,56",
    "1,234.56", "1.234.5678", "3.14", "3,14", "0,05", "0.5", ".5", "5.", "007", "0812345678", "+34 600 123 456",
    "600-123-456", "+55 (11) 91234-5678", "(11) 91234-5678", "12 34 56 78 90 12", "1 2 3", "12 34", "123 456 789",
    "14:30", "14:30:15", "7:00 h", "7:00h", "7:00 hs", "7:00 hrs", "23:59", "24:00", "25:00", "9:5", "14h30", "14h",
    "08h", "pukul 14.30", "jam 7.15", "Pukul 08.00", "PUKUL 8.05", "jam 25.00", "5/3/2026", "05/03/26", "31/12/1999",
    "32/13/2020", "1/1/2000", "2026-03-05", "2026-13-45", "12026-1-1", "1-2-3", "10-20", "10 - 20", "10 – 20",
    "10–20", "1.º", "2.ª", "3.er", "1er", "1º", "2ª", "21º", "11.º", "12.ª", "100º", "1000º", "0º", "ke-3", "ke3",
    "Ke-1", "ke-21", "anak2", "kura2", "a2", "$5", "$ 5", "US$ 1.250,50", "R$ 1.250,50", "R$ 1,00", "R$ 1,5 milhão",
    "R$ 2 milhões", "Rp50.000", "Rp 1,5 juta", "Rp. 10 ribu", "20 €", "20€", "£7", "¥100", "5 km", "5km", "1 km",
    "21 km", "1,5 kg", "25 °C", "25°C", "30℃", "40°", "-5 °C", "100 km/h", "60 km/jam", "16 GB", "3 kWh", "5000 mAh",
    "2 h", "1 h", "30 min", "10 s", "5 m", "1 L", "2 l", "3 ha", "21 casas", "1 casa", "un 1", "21 años", "veintiún",
    "101 dálmatas", "1001 noches", "1.000.001 libros", "Sr. García", "Sra. López", "Dr. Pérez", "EE. UU.", "EE.UU.",
    "etc.", "etc. y más", "n.º 5", "nº 5", "pág. 3", "D. Juan", "Dña. María", "Jl. Sudirman No. 5", "dll.", "a.n. Budi",
    "s.d.", "yg dgn tdk utk krn", "PT. Maju", "vc pq tb tbm", "Ltda.", "Prof. Silva", "obs.", "…", "—", "–", "a — b",
    "a - b", "a—b", "eh...", "eh....", "¿Abriste Netflix en el iPhone?", "“citado”", "«citado»", "(entre) [corchetes]",
    "{llaves} <menor>", "*negrita*", "~tilde~", "a|b", "año 2026", "MÉXICO", "Ñandú", "İstanbul", "straße", "Œuvre",
    "ﬁn", "ｈｏｌａ", "𝐡𝐨𝐥𝐚", "Ⅻ", "x²", "½", "٣ ٤", "١٢:٣٠", "中文", "한국어", "Việt Nam", "ελληνικά", "русский",
    "naïve café", "façade", "Øresund", "Łódź", "Þór", "đường", "ß", "x\x1cy", "x\x85y", "a।b", "a。b", "a; b", "a ; b",
    "1999-2000", "2000-01", "100-200 km", "3-2", "-3", "- 3", "a-3", "3-a", "3.", "3,", "3, 4", "3.4.5", "1,23,456",
    "1.234,567,890", "1,234,5678", "12.345.678,9", "999.999.999.999.999", "1000000000000000000000000",
    "999999999999999999999999", "123456789012345678901234567890", "0000000000000001", "0,000", "0.00", "00,5",
    "Velocidad: 100 km/h; peso: 5 kg.", "Son las 7:30 y hace 25 °C.", "Cuesta $1.250,50 o 20 €.",
]


def _lt_words(lang: str) -> list[str]:
    """Words of the eval sets, the templates, the exception table and the word lists of a language."""
    import json

    from vtts.frontend.lexicons import load_table, load_words

    root = Path(__file__).parents[2]
    words: set[str] = set()
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                words.update(json.loads(x)["text"].split())
    for t in (root / "scripts" / "data" / "bilingual" / f"templates_{lang}.txt").read_text(encoding="utf-8").splitlines():
        words.update(t.replace("{T}", " ").split())
    for k, v in load_table(lang, "overrides").items():
        words.update({k, v, k.capitalize(), k.upper()})
    words.update(load_words(lang, "native"))
    if lang in ("id", "ms"):
        from vtts.frontend.id.g2p_id import PREFIXES, SUFFIXES

        for k in list(load_table(lang, "overrides"))[:60]:
            words.update({p + k for p in PREFIXES} | {k + s for s in SUFFIXES})
    if lang == "ms":  # the shared Indonesian e table is looked up under the Malay one
        words.update(load_table("id", "overrides"))
    return sorted(words)


# Italian and Turkish: edge cases (apostrophes, elision, suffixes, ordinals, Turkish casing)
LT2_EDGE = {
    "it": ["l'acqua", "L’acqua", "sull'iPhone", "l'app di YouTube", "dell'ONU", "c'è", "po'", "un po' d'acqua",
           "quest'anno", "sant'Antonio", "dell’ESP32", "l'", "'", "''", "l''a", "d'Italia", "all'1", "alle 9.15",
           "Alle 9.15.", "ore 14.30", "dalle 8.00 alle 9.30", "entro 7.5", "verso  10.45", "ALLE 9.15", "Ore 9.15",
           "333 1234567", "3331234567", "06 1234 5678", "0612345678", "1º 2ª 3° 4 °C 5°C 6°", "21 anni", "1 di loro",
           "101 e 102", "12,50 €", "€12,50", "EUR 3", "3 EUR", "US$ 1,01", "CHF 5", "1.000.000 di euro",
           "10**12", "1000000000000", "21000", "23ª", "ventisei", "ventitré", "pizzeria galleria geologia",
           "perché città però più così è", "ÀÈÉÌÒÙ", "IÌ İ ı", "glicine gnocchi sciopero", "Sig.ra Rossi e Dott.ssa",
           "S.p.A.", "ecc.", "cmq xké tvb", "– 10 – 20 –", "5/3/2026", "5.3.2026", "5.3.26", "1/1/2000",
           "2026-11-19", "32/13/2026", "24:00 25:00", "1:15", "12:05:30", "NATO RAI USB"],
    "tr": ["İstanbul'da", "Ankara'ya", "iPhone'u", "Google'da", "YouTube’dan", "Microsoft'un", "GitHub'ı",
           "Ahmet'in", "Türkiye'nin", "dört'üncü", "4'üncü", "1'inci", "2026'da", "5'te", "%25'i", "%50",
           "50%", "5. sınıf", "Yarışta 2. olduk.", "2.  olduk", "3. Ve", "21. yüzyıl", "saat 14.30'da",
           "Saat 9.15", "14:30'da", "19.11.2026", "19/11/2026", "2026-11-19'da", "12,50 TL", "₺50", "50 ₺",
           "$5", "20 €", "120 km/h", "120 km/sa", "25 °C", "3,5 km", "0532 123 45 67", "+90 532 123 45 67",
           "05321234567", "(0532) 123 45 67", "THY", "NATO", "IŞIK", "İLK", "ılık", "ISI", "İzmir", "Dr. Ahmet",
           "Prof. Dr. Ayşe", "vb.", "vs.", "M.Ö. 500", "T.C.", "A.Ş.", "slm tşk", "hâlâ kâr rüzgâr millî",
           "dağ yağmur değil ağaç soğuk", "gelmiyor gelmedi geliyor şehirdir kültür amacıyla", "mi misin mısınız",
           "masada Avrupa'nın Ankarada", "ˈ", "ʼ", "'da", "''", "kitap'", "'"],
}


def _lt_pseudo(lang: str, rnd, n: int) -> list[str]:
    """Random words of the language's letters (every branch of the spelling rules)."""
    vowels = {"es": "aeiouáéíóúü", "id": "aiueoé", "pt": "aeiouáéíóúâêôãõàü", "it": "aeiouàèéìíòóùîjy",
              "tr": "aeıioöuüâîû", "ms": "aiueoé"}[lang]
    cons = {"es": ["b", "c", "ch", "d", "f", "g", "gu", "gü", "h", "j", "k", "l", "ll", "m", "n", "ñ", "p", "qu", "r",
                   "rr", "s", "t", "v", "w", "x", "y", "z", "br", "cr", "pl", "tr", "ns", "st"],
            "id": ["b", "c", "d", "f", "g", "h", "j", "k", "kh", "l", "m", "n", "ng", "ngg", "ny", "p", "q", "r", "s",
                   "sy", "t", "v", "w", "x", "y", "z", "'", "kk", "nn", "tr", "st", "pr"],
            "pt": ["b", "c", "ç", "ch", "d", "f", "g", "gu", "h", "j", "k", "l", "lh", "m", "n", "nh", "p", "qu", "r",
                   "rr", "s", "ss", "sc", "t", "v", "w", "x", "xc", "y", "z", "br", "cr", "pl", "tr", "ns"],
            "it": ["b", "c", "cc", "ch", "cch", "ci", "cq", "d", "f", "g", "gg", "gh", "gi", "gl", "gli", "gn", "h",
                   "l", "ll", "m", "n", "p", "q", "qu", "r", "rr", "s", "ss", "sc", "sci", "sch", "sb", "sm", "t",
                   "tt", "v", "z", "zz", "x", "k", "w", "str", "pr", "nt", "nz", "lz", "c'", "l'", "dell'", "'"],
            "tr": ["b", "c", "ç", "d", "f", "g", "ğ", "h", "j", "k", "l", "m", "n", "p", "r", "s", "ş", "t", "v", "y",
                   "z", "kk", "nn", "ll", "tr", "st", "rk", "nt", "q", "w", "x", "'", "ˈ"],
            "ms": ["b", "c", "d", "f", "g", "gh", "dh", "th", "sh", "ch", "h", "j", "k", "kh", "l", "m", "n", "ng",
                   "ngg", "ny", "p", "q", "r", "s", "sy", "t", "v", "w", "x", "y", "z", "'", "kk", "nn", "gg", "ke",
                   "se", "tr", "st", "pr"]}[lang]
    out = []
    for _ in range(n):
        w = "".join(rnd.choice(cons) * (rnd.random() < 0.8) + rnd.choice(vowels) + rnd.choice(vowels) * (rnd.random() < 0.25)
                    for _ in range(rnd.randint(1, 4)))
        w += rnd.choice(["", "", "", "n", "s", "r", "l", "m", "z", "k", "x", "ns", "m", "ão", "ões", "ãe", "am", "em",
                         "ens", "el", "ol", "osa", "ai", "au", "ei", "oi", "nya", "kan", "lah"])
        out.append(w.capitalize() if rnd.random() < 0.2 else w.upper() if rnd.random() < 0.03 else w)
    return out


def _lt_generated(lang: str, n: int, rnd) -> list[str]:
    vocab = _lt_words(lang)
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1", "smart",
             "GitHub", "YouTube", "Netflix", "weekend", "update", "online", "router", "Spotify", "macOS", "NASA"]
    numbers = ["3", "15", "21", "100", "2026", "3,5", "1.000", "1.234,56", "50%", "9:30", "$20", "-7", "2024-05-01",
               "5/3/2026", "10-20", "25 °C", "5 km", "1º", "2ª", "ke-2", "Rp5.000", "R$ 10,50", "0812345678"]
    marks = [",", ".", "!", "?", ";", ":", "…", "—", "“", "”", "(", ")", "¿", "¡", "«", "»"]
    pseudo = _lt_pseudo(lang, rnd, 4 * n)
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 14)):
            r = rnd.random()
            if r < 0.45:
                parts.append(rnd.choice(vocab))
            elif r < 0.7:
                parts.append(rnd.choice(pseudo))
            elif r < 0.82:
                parts.append(rnd.choice(numbers))
            elif r < 0.92:
                parts.append(rnd.choice(latin))
            else:
                parts.append(rnd.choice(marks))
        out.append(" ".join(parts) + rnd.choice([".", "!", "?", "", "。", "..."]))
    return out


def _lt_regex_fuzz(lang: str, n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalizer passes react to."""
    from vtts.frontend.es import normalize_es
    from vtts.frontend.id import normalize_id
    from vtts.frontend.ms import normalize_ms
    from vtts.frontend.pt import normalize_pt

    if lang in ("it", "tr"):
        import importlib

        nm = importlib.import_module(f"vtts.frontend.{lang}.normalize_{lang}")
        atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=() ’") * 2 + list(nm.UNITS) + list(nm.CURRENCY)
                 + list(nm.ABBREVIATIONS) + ["º", "ª", "°", "°C", "alle ", "Ore ", "dalle ", "saat ", "Saat ", "'da",
                                             "'inci", "'üncü", "…", "...", "¿", "¡", "A", "I", "İ", "ı", "Z", "ESP",
                                             "x", "ab", "Ok", "Wi", "é", "è", "ç", "ş", "ğ", " ", "  ", "\t", "“",
                                             "”", "«", "»", "ʼ", "ˈ", "â", "l'", "dell'", "c'", "sull'", "5.", "3"])
        return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]
    nm = {"es": normalize_es, "id": normalize_id, "pt": normalize_pt, "ms": normalize_ms}[lang]
    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=() ") * 2 + list(nm.UNITS) + list(nm.CURRENCY)
             + [k for k in nm.ABBREVIATIONS] + ["º", "ª", "er", "h", "hs", "hrs", "ke", "Ke", "pukul ", "jam ",
                                               "ribu", "juta", "mil", "milhão", "milhões", "…", "...", "¿", "¡",
                                               "A", "B", "Z", "ESP", "x", "ab", "Ok", "Wi", "é", "ñ", "ç", "ã", " ",
                                               "  ", "\t", "“", "”", "«", "»"])
    if lang == "ms":  # month names and abbreviations (re.IGNORECASE look-alikes too), day parts, sen
        atoms += (list(normalize_ms.MONTH_ABBR) + [m for m in normalize_ms.MONTHS if m]
                  + ["Jan", "OGOS", "Sept.", "ſep", "julaİ", "\u212aok", "ı", " pagi", " PETANG", " tengah hari",
                     " tengah malam", " malam", " waktu", "sen", " sen", "bilion", "trilion", "RM", "S$"] * 2)
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def _lt_tests(lang: str) -> list[str]:
    """String constants of the language's front-end tests."""
    import ast

    root = Path(__file__).parents[2] / "tests" / "frontend"
    out = []
    for name in (f"test_normalize_{lang}.py", f"test_text_{lang}.py", f"test_{lang}_g2p.py"):
        p = root / name
        if p.exists():
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and 0 < len(node.value) < 400:
                    out.append(node.value)
    return out


def lt_lines(lang: str, paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode es|id|pt cases: edge cases, the eval sets, the mixed-style sentences (templates x terms_en),
    the tests' strings, sentences (a corpus when given and present, else generated from the vocabulary
    and random words), number/date/time/money/unit cases and regex-dense random strings. Texts for
    which the Python front-end raises (numbers like 1.234.5678) are left out."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / f"templates_{lang}.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(LT_EDGE) + LT2_EDGE.get(lang, [])
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _lt_tests(lang)
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows if rows else _lt_generated(lang, limit or 3000, rnd)
    texts += [" ".join(_lt_words(lang)[i:i + 20]) + "." for i in range(0, len(_lt_words(lang)), 20)]
    pseudo = _lt_pseudo(lang, rnd, 6000)
    texts += [" ".join(pseudo[i:i + 20]) + "." for i in range(0, len(pseudo), 20)]
    nums = []
    for _ in range(2500):
        k = rnd.randint(0, 17)
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**9),
                        rnd.randint(0, 10**15), rnd.randint(0, 10**25)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 40)
        nums.append(["{} casas", "{:,} libros", "{}.5%", "$ {}", "{}º", "-{} km", "{}/{}/2026", "{}-{} kg", "{}:{:02d}",
                     "{}h{:02d}", "pukul {}.{:02d}", "{}.{:03d}.{:03d}", "R$ {},{:02d}", "Rp{}", "{} €",
                     "ke-{}", "{},{}", "+{} {} {}"][k].format(v, a, b))
    for _ in range(500):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} y "
                    f"{rnd.randint(0, 33)}/{rnd.randint(0, 13)}/{rnd.randint(0, 99):02d} "
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    if lang == "ms":
        from vtts.frontend.ms.normalize_ms import MONTH_ABBR, MONTHS

        months = [m for m in MONTHS if m]
        abbr = list(MONTH_ABBR)
        for _ in range(2000):
            k = rnd.randint(0, 9)
            v = rnd.choice([rnd.randint(0, 99), rnd.randint(0, 99999), rnd.randint(0, 10**12), rnd.randint(0, 10**16)])
            a, b = rnd.randint(0, 40), rnd.randint(0, 99)
            mon = rnd.choice(months + abbr)
            mon = rnd.choice([mon, mon.capitalize(), mon.upper(), mon + "."])
            nums.append(["{} " + mon + " {}", "RM{}.{:02d}", "RM {:,}.{:02d}", "RM{} juta", "{} sen",
                         "pukul {}.{:02d} pagi", "{}.{:02d} malam", "{:,}.{} km", "{}.{:03d}.{:03d},{}",
                         "S$ {}"][k].format(v if k not in (0, 5, 6) else a, b, b, b))
    texts += nums + _lt_regex_fuzz(lang, fuzz, rnd)
    out, seen = [], set()
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85  "):  # line breaks of splitlines()
            continue
        seen.add(text)
        try:
            ids = text_to_ids(text, lang)
        except (ValueError, KeyError, IndexError):  # Python raises (e.g. int('.') in 1.234.5678): not a case
            continue
        out.append(f"{lang}\t{text}\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out


TH_EDGE = [
    "สวัสดีครับ", "ภาษาไทยไม่มีช่องว่างระหว่างคำ", "ไปไหนมา กินข้าวหรือยัง", "เด็กๆ ไปโรงเรียน", "ต่างๆ นานา",
    "กรุงเทพฯ และ ฯลฯ", "ฯพณฯ นายกรัฐมนตรี", "พ.ศ. 2567 และ ค.ศ. 2024", "ดร. สมชาย ผศ. สมหญิง รศ. ศ.", "จ. เชียงใหม่ อ. เมือง ต. สุเทพ",
    "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.", "รพ. ร.ร. กม. ซม. มม. กก. โทร. 02-123-4567", "ถ. สุขุมวิท",
    "วันที่ 19/11/2569", "2026-11-19", "19/13/2569", "32/1/2024", "1/2/26", "14:30", "14:30 น.", "14.30 น.", "9.05น.",
    "เวลา 8:00:15", "24:00 และ 25:00", "ราคา 1,250 บาท", "฿500", "฿ 1,000.50", "$5", "€3.5", "£7", "¥100", "50%", "-3.5 %",
    "5km", "3 kg", "30°C", "25℃", "45°", "16GB", "500ml", "2 l", "10 km/h", "-5m", "x-5km", "081-234-5678",
    "+66 81 234 5678", "02-123-4567", "0812345678", "0123", "12345678", "1234567", "10-20 คน", "10 – 20", "-5 องศา",
    "อุณหภูมิ -5", "3.14", "1,234,567", "1,23", "1.2.3", "1000000", "2000000", "1000001", "21", "101", "11", "20",
    "1000000000000", "100000000000000000000", "12.", ".5", "0", "00", "007", "ESP32-P4", "A1B2", "USB3.0", "RTX3060",
    "2 + 3 = 5", "R&D", "me@example.com", "3×4", "เปิดWi-Fiให้หน่อย", "ใช้ iPhone 15 Pro", "ต่อ Bluetooth แล้ว",
    "เปิด smart home mode", "OK ครับ", "Hello. สวัสดี! How are you? สบายดี; ขอบคุณ.", "“คำพูด” (วงเล็บ) [ก] {ข} <ค>",
    "« อ » 「ก」『ข』 · •", "รอสักครู่… แล้ว—ไป", "รอ...ก่อน", "ภาษาไทย๑๒๓", "๒๕๖๗", "ｈｅｌｌｏ　ｗｏｒｌｄ", "１２：３０",
    "จันทร์ ศาสตร์ การณ์ สัตว์ ลักษณ์ พระพุทธเจ้า", "รัฐบาล รัฐสภา เทศกาล พิษณุโลก อยุธยา", "พฤษภาคม ฤดู ฤๅษี ฦๅ ทฤษฎี อังกฤษ",
    "ปฏิบัติ ปฏิบัติการ สมบัติ บุตร เมตร จักร", "ทราย ทรัพย์ จริง สร้าง ศรี ไซร้", "เสมอ แสดง เฉลิม สนุก ขนม อร่อย หนู หมา",
    "นคร บริษัท บรม บดี", "ก๋วยเตี๋ยว ไก่ ไข่ เกี๊ยว ต๋อย", "ได้รับ อุบัติเหตุ ราชการ", "เพชร์ วงศ์ องค์ กษัตริย์", "์", "ั", "ๆ",
    "ฯ", "กๆๆ", "ก ๆ", "฿", "ฺ", "...", "", "a", "ก", "。", "ไทย。จีน！ญี่ปุ่น？", "สวัสดี.ครับ", "ก. ข.", "น. 5",
    "ภาษาไทย" * 200, "ก" * 300, "เด็ก" * 400 + "ครับ", "คำ " * 120 + "จบ",
    "Very long English " + "words " * 80 + "end.", "ตัวเลข " + "1234567890" * 20,
]


def _th_test_strings() -> list[str]:
    """String constants with Thai letters or digits from the Thai unit tests."""
    import ast

    root = Path(__file__).parents[2] / "tests" / "frontend"
    out: list[str] = []
    for name in ("test_th_g2p.py", "test_text_th.py", "test_normalize_th.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value
                if any("ก" <= c <= "๛" for c in s) and "\n" not in s and len(s) < 2000:
                    out.append(s)
    return list(dict.fromkeys(out))


def _th_generated(n: int, rnd) -> list[str]:
    """Sentences from the word list, respelled words, random letter strings, numbers, Latin words
    and punctuation (no Thai corpus in the repository)."""
    from vtts.frontend.th.g2p_th import override_table, word_set

    words, ovr = sorted(word_set()), sorted(override_table())
    letters = [chr(c) for c in range(0x0E01, 0x0E4F) if c != 0x0E3F]
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1", "smart"]
    numbers = ["3", "15", "100", "2567", "3.5", "1,000", "50%", "9:30", "฿20", "-7", "19/11/2569", "10-20",
               "081-234-5678", "25°C", "5km", "๑๒"]
    marks = [" ", " ", " ", ",", ".", "!", "?", ";", ":", "…", "“", "”", "(", ")", "ๆ", "ฯ", " ๆ "]
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 14)):
            r = rnd.random()
            if r < 0.55:
                parts.append(rnd.choice(words))
            elif r < 0.62:
                parts.append(rnd.choice(ovr))
            elif r < 0.72:
                parts.append("".join(rnd.choice(letters) for _ in range(rnd.randint(1, 5))))
            elif r < 0.82:
                parts.append(rnd.choice(numbers))
            elif r < 0.88:
                parts.append(rnd.choice(latin))
            else:
                parts.append(rnd.choice(marks))
        out.append("".join(parts) + rnd.choice(["", "", ".", "!", "?", " ครับ", " ค่ะ"]))
    return out


def _th_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalize_th regex passes react to."""
    atoms = (list("0123456789") * 4 + list(":/.,-–%'+=&@× ") * 2
             + ["น.", "น", "ก", "พ.ศ.", "จ.", "ฯ", "ๆ", "บาท", "฿", "$", "€", "£", "¥", "km", "km/h", "kg", "m", "g",
                "l", "ml", "GB", "MB", "°C", "°", "℃", "…", "—", "...", "“", "”", "（", "）", "　", "１", "๕", "Ａ",
                "ESP", "A", "B", "Z", "x", "ab", "Ok", "Wi", "é", " ", "  ", "+66", "08", "02"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def th_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode "th" cases: edge cases, the Thai eval sets, the Thai unit-test strings, the mixed-style
    sentences (templates_th x terms_en), every respelled word, the word list in groups of 8 (with and
    without spaces), Thai sentences (data/th/sentences.jsonl when given and present, else generated),
    number/date/time cases and regex-dense random strings."""
    import json
    import random

    from vtts.frontend.th.g2p_th import override_table, word_set

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_th.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(TH_EDGE)
    for name in ("ood_th.jsonl", "mixed_th.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += _th_test_strings()
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += sorted(override_table())
    words = sorted(word_set())
    rnd.shuffle(words)
    for i in range(0, len(words), 8):
        group = words[i:i + 8]
        texts.append(" ".join(group) if (i // 8) % 2 else "".join(group))
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows if rows else _th_generated(limit or 3000, rnd)
    nums = []
    for _ in range(2000):
        k = rnd.randint(0, 11)
        v = rnd.choice([rnd.randint(0, 99), rnd.randint(0, 99999), rnd.randint(0, 10**9), rnd.randint(0, 10**22)])
        nums.append(["{} คน", "ราคา {:,} บาท", "{}.5%", "฿{}", "ที่ {} ของ", "-{} องศา", "{}/{}/{}", "{}-{} คน",
                     "{}:{} น.", "{}.{} น.", "0{}", "{} กม."][k].format(v, rnd.randint(0, 60), rnd.randint(0, 40)))
    for _ in range(400):
        nums.append(f"{rnd.randint(1900, 2600)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} และ "
                    f"{rnd.randint(0, 33)}/{rnd.randint(0, 13)}/{rnd.randint(1900, 2600)} "
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _th_regex_fuzz(fuzz, rnd)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        out.append(f"th\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, "th")))
    return out


FR_EDGE = [
    "", ".", "...", "a", "A", "x", "y", "Y", "'", "''", "l'", "L'", "-", "--", "Bonjour, ça va ?", "Bonjour. Au revoir.",
    "  espaces  ", "tab\tulé", "ligne\nnouvelle", "Wi-Fi", "iPhone 15 Pro", "ESP32-P4", "RTX3060", "l'iPhone",
    "L’iPhone d’Apple", "qu'Instagram", "jusqu'au Wi-Fi", "aujourd'hui", "Aujourd’hui", "AUJOURD'HUI",
    "quelqu'un", "presqu'île", "lorsqu'il", "puisqu'elle", "quoiqu'on", "c'est-à-dire", "s'il te plaît",
    "Les amis", "les héros", "les hommes", "les haricots", "un ami", "mon ami", "bon ami", "ancien élève",
    "en effet", "très important", "quand il", "est-il", "a-t-il", "dit-elle", "peut-on", "vont-ils",
    "allez-y", "vas-y", "prends-en", "A-T-IL", "Dit-Il", "six ans", "six mois", "six.", "dix-huit", "dix-neuf",
    "dix-sept", "vingt-deux", "quatre-vingt-deux", "vingt ans", "cent ans", "cent un", "neuf ans",
    "neuf heures", "huit jours", "huit ans", "ils sont tous.", "ils sont tous là", "à l'est", "nord-est",
    "avec nous au cinéma", "nous avons", "chacun a", "les onze", "les oui", "les yeux", "les yaourts",
    "XIXe siècle", "Louis XIV", "François Ier", "Henri IV", "Le XXIe", "Ce", "Le Ve", "Chapitre V",
    "M. Dupont", "Mme Martin", "MM. Durand", "Dr Moreau", "etc.", "J.-C.", "av. J.-C.", "apr. J.-C.", "n° 5",
    "qqn", "qqch", "svp", "SVP", "stp", "c.-à-d.", "càd", "p. ex.", "Cie", "vs", "tél.", "env.", "bd", "Bd",
    "1er", "1re", "1ère", "2e", "2ème", "2nd", "2nde", "3es", "4èmes", "21ers", "1ᵉʳ", "2ᵉ", "1ʳᵉ",
    "14 h 30", "14h30", "14 h", "8 h", "1 h", "21:15", "0:05", "24 h 00", "14 h 30 min", "9:30:15", "25 h",
    "06 12 34 56 78", "0612345678", "06.12.34.56.78", "06-12-34-56-78", "+33 6 12 34 56 78",
    "+33 (0)6 12 34 56 78", "0033 6 12 34 56 78", "+1 212 555 0101", "+44 20 7946 0958", "+12345",
    "12,50 €", "0,50 €", "0,01 €", "1 €", "1,00 €", "2 €", "1 000 000 €", "3 000 000 €", "1 500 000 €",
    "1,5 million €", "2 milliards €", "3 mille €", "€ 5", "€5", "$5", "US$ 10", "5 $", "20 £", "10 CHF",
    "100 ¥", "5 EUR", "15 %", "15%", "-3 %", "25 °C", "-5 °C", "5 km", "1 km", "120 km/h", "8 Go", "1 Go",
    "3 t", "1 t", "2 min", "1 min", "10 s", "1 s", "50 m²", "3 m³", "1,5 kg", "0 km", "10 000 habitants",
    "1 250", "2 300 000", "10 000 000", "12 345 678 901", "123 4567", "3,14", "2.5", "0,05", "-7",
    "10-20", "10 – 20", "1914-1918", "14/07/1789", "1/5/2024", "1.5.2024", "31/12/99", "32/13/2020",
    "2026-11-19", "2026-13-40", "1 heure", "1 voiture", "21 pages", "31 personnes", "1,5 heure",
    "ONU OTAN UNESCO SNCF RATP", "PIB", "SIDA", "Ça & là", "a + b = c", "x × y", "1/2", "@user", "#tag",
    "§ 3", "Bon… allons-y", "« Bonjour » (dit-elle)", "[note]", "{x}", "<b>", "*_~|", "un — deux", "un - deux",
    "un – deux", "l'est", "Est-ce que", "Qu'est-ce que c'est ?", "Où es-tu ?", "Il y a",
]


def _fr_pseudo(rnd, n: int) -> list[str]:
    """Random words of French letters and letter groups (every branch of the spelling rules)."""
    vowels = ["a", "e", "i", "o", "u", "y", "é", "è", "ê", "à", "â", "î", "ô", "û", "ù", "ë", "ï", "ü", "œ", "æ",
              "ai", "ei", "au", "eau", "ou", "oi", "eu", "œu", "ui", "ie", "ue"]
    cons = ["b", "c", "ç", "ch", "d", "f", "g", "gu", "gn", "h", "j", "k", "l", "ll", "ill", "m", "mm", "n", "nn",
            "p", "ph", "pp", "qu", "r", "rr", "s", "ss", "sc", "t", "th", "tt", "v", "w", "x", "z", "br", "cr", "pl",
            "tr", "st", "sp", "ps", "pt", "mp", "nt", "ct"]
    ends = ["", "", "", "e", "es", "s", "x", "t", "d", "nt", "ent", "ment", "er", "ez", "et", "ed", "ille", "il",
            "ail", "eil", "euil", "um", "em", "en", "ien", "ient", "tion", "tie", "ier", "ent", "ents", "c", "g",
            "p", "b", "f", "l", "z", "ng", "gt", "ct", "st"]
    out = []
    for _ in range(n):
        w = "".join(rnd.choice(cons) * (rnd.random() < 0.8) + rnd.choice(vowels) for _ in range(rnd.randint(1, 4)))
        w += rnd.choice(ends)
        if rnd.random() < 0.15:
            w = rnd.choice(["l'", "d'", "qu'", "jusqu'", "s'", "z'"]) + w
        out.append(w.capitalize() if rnd.random() < 0.2 else w.upper() if rnd.random() < 0.03 else w)
    return out


def _fr_words() -> list[str]:
    """Words of the eval sets, templates, tables and word lists, and the liaison lists."""
    from vtts.frontend.fr import normalize_fr as nf
    from vtts.frontend.lexicons import load_words

    words = set(_lt_words("fr"))
    for name in ("final", "ent", "er", "ment_verbs", "c_silent", "l_silent", "f_silent"):
        words |= load_words("fr", name)
    words |= set(nf.LIAISON) | set(nf.DENASAL) | set(nf.NO_LIAISON) | set(nf.H_ASPIRE) | set(nf.FEMININE)
    words |= set(nf.ABBREVIATIONS) | set(nf.ACRONYM_WORDS)
    return sorted(words)


def _fr_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalizer passes react to."""
    from vtts.frontend.fr import normalize_fr as nf

    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=()§ ") * 2 + list(nf.UNITS) + list(nf.CURRENCY)
             + list(nf.ABBREVIATIONS) + ["er", "re", "e", "ème", "nd", "de", "h", "h ", " h ", "min", "mille", "million",
                                         "millions", "milliard", "+33", "0033", "(0)", "I", "V", "X", "L", "C", "IV",
                                         "XIX", "Louis ", "Le ", "-t-", "-T-", "il", "elle", "on", "y", "en", "-y",
                                         "…", "...", "A", "B", "Z", "ESP", "ab", "é", "ç", "ᵉ", "ʳ", "ᵈ", "’", "ʼ",
                                         " ", " ", " ", "  ", "\t", "“", "”", "«", "»", "un", "une", "les", "six",
                                         "dix", "huit", "vingt", "ans", "heures", "pages", "l'", "qu'"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def fr_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode fr cases: edge cases, both eval sets, the mixed-style sentences (templates x terms_en),
    the tests' strings, sentences of a corpus (when given), every table and list word, random French
    words, number/date/time/money/unit cases and regex-dense random strings."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_fr.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(FR_EDGE)
    for name in ("ood_fr.jsonl", "mixed_fr.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _lt_tests("fr")
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows
    words = _fr_words()
    texts += [" ".join(words[i:i + 12]) + "." for i in range(0, len(words), 12)]
    texts += words[::3]
    pseudo = _fr_pseudo(rnd, 8000)
    texts += [" ".join(pseudo[i:i + 16]) + "." for i in range(0, len(pseudo), 16)]
    nums = []
    for _ in range(2500):
        k = rnd.randint(0, 19)
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**9),
                        rnd.randint(0, 10**15), rnd.randint(0, 10**25)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 40)
        nums.append(["{} maisons", "{:,} livres", "{},5 %", "{} €", "{}e", "-{} km", "{}/{}/2026", "{}-{} kg",
                     "{}:{:02d}", "{} h {:02d}", "{}h{:02d}", "{} {:03d} {:03d}", "{},{:02d} €", "{} heures",
                     "{} pages", "{}er", "{},{}", "+{} {} {}", "{} ans", "{} millions €"][k].format(v, a, b))
    for _ in range(500):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} et "
                    f"{rnd.randint(0, 33)}/{rnd.randint(0, 13)}/{rnd.randint(0, 99):02d} "
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d} "
                    f"0{rnd.randint(1, 9)} {rnd.randint(10, 99)} {rnd.randint(10, 99)} {rnd.randint(10, 99)} "
                    f"{rnd.randint(10, 99)}")
    texts += nums + _fr_regex_fuzz(fuzz, rnd)
    out, seen = [], set()
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85  "):  # line breaks of splitlines()
            continue
        seen.add(text)
        try:
            ids = text_to_ids(text, "fr")
        except (ValueError, KeyError, IndexError):  # Python raises: not a case
            continue
        out.append(f"fr\t{text}\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out


DE_EDGE = [
    "", ".", "...", "¿?", "¡!", "a", "A", "x", "ß", "ẞ", "é", "'", "-", "--", "Hallo. Tschüss.", "  Leerzeichen  ",
    "Tab\tTab", "Wi-Fi", "iPhone 15 Pro", "ESP32-P4", "RTX3060", "USB, GPS und NATO.", "GitHub und YouTube",
    "Am 3. Mai 2026 um 14:30 Uhr.", "Am 3. Mai. Dann.", "Die 2. Klasse, im 5. Stock, der 1. Platz.",
    "Er war die Nummer 1. Danach kam ich.", "z. B. Äpfel, d. h. Birnen, u. a. Kirschen usw. Dann.",
    "usw. und etc. sind Abkürzungen.", "Das ist gut, usw. Dann aber.", "J. S. Bach und Dr. Müller.", "Nr. 5",
    "3.5.2026", "03.05.26", "3.5. ist", "3.5.123", "31.12.1999", "32.13.2026", "2026-05-03", "2026-13-45",
    "14:30", "14:30:15", "9.05 Uhr", "7 Uhr", "24:00", "25:00 Uhr", "1:00", "0:00 Uhr", "14.30", "3,50", "3.50",
    "5,50 €", "0,99 €", "1 €", "€ 5", "€5", "5 EUR", "EUR 5", "5 Euro", "1,5 Euro", "5,- €", "US$ 3", "$3,50",
    "10 CHF", "£ 2", "¥ 100", "75 %", "3,5 %", "2 ‰", "-5 %", "−5 °C", "25 °C", "100 km/h", "1 km", "1 min",
    "1 Min.", "3 h", "8 GB", "10.000 mAh", "5 m²", "2 kWh", "1 t", "1 A", "030 1234567", "+49 30 1234567",
    "(030) 1234567", "0171/1234567", "0123456", "012345", "10-20", "10 – 20", "1.000.000", "1,250.50",
    "1.250,5", "21", "101", "1001", "1999", "2026", "1100", "1099", "2000", "1000000", "1000000000000",
    "100000000000000000000", "12.", ".5", "0", "00", "007", "1 Stunde", "1 Tag", "1 Frau", "-1 Grad",
    "1 Bäckerei", "A1B2", "USB3.0", "WLAN", "Lkw", "PKW", "GmbH", "E-Mail", "e-mail", "E-Mails",
    "Café au lait", "Größe Straße Bär Öl Übel", "& + = @ # × / % ‰ § °", "Herr Dr. med.", "St. Pauli",
    "Mio. Mrd. Tsd.", "v. Chr. n. Chr.", "o. Ä.", "z.B.", "d.h.", "ca. 5 kg", "Seite 3 … Seite 4",
    "Er sagte — leise — nein.", "Ja - nein", "Nordosten, südwestlich", "übersetzen Unterricht Übersetzung",
    "Turn on the light, please.", "Please open the app.", "Das Update für den Laptop.", "Meeting im Team.",
]


def _de_words() -> list[str]:
    import json

    from vtts.frontend.de.g2p_de import stem_table
    from vtts.frontend.lexicons import load_table, load_words

    root = Path(__file__).parents[2]
    words = set()
    for name in ("ood_de.jsonl", "mixed_de.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                words.update(json.loads(x)["text"].split())
    for k in load_table("de", "overrides"):
        words.update({k, k.capitalize(), k.upper()})
    for k in stem_table():
        words.update({k, k.capitalize(), k + "en", k + "ung", k + "s"})
    words.update(load_words("de", "native") | load_words("de", "english"))
    return sorted(words)


def _de_pseudo(rnd, n: int) -> list[str]:
    vowels = ["a", "e", "i", "o", "u", "ä", "ö", "ü", "y", "ie", "ei", "au", "eu", "äu", "aa", "ee", "oo", "ah", "eh"]
    cons = ["b", "c", "ch", "chs", "ck", "d", "dt", "f", "g", "h", "j", "k", "l", "ll", "m", "n", "ng", "nk", "p",
            "pf", "ph", "qu", "r", "rr", "s", "sch", "sp", "st", "ß", "ss", "t", "th", "tz", "v", "w", "x", "z",
            "br", "tr", "gl", "kn", "schw", "str"]
    pre = ["", "", "", "be", "ge", "ver", "zer", "ent", "er", "emp", "ab", "an", "auf", "aus", "ein", "mit", "über",
           "unter", "um", "zu", "zurück", "nord", "süd"]
    suf = ["", "", "", "e", "en", "er", "ung", "heit", "keit", "lich", "ig", "isch", "chen", "ion", "ität", "ieren",
           "iert", "ie", "ien", "ik", "iker", "ismus", "ist", "ent", "ant", "al", "ell", "ett", "iv", "ös", "eur", "är",
           "at", "on", "ee", "ei", "erlei", "tor", "oren", "s", "t", "st", "te", "ten", "ige", "igt", "lein", "nis"]
    out = []
    for _ in range(n):
        w = rnd.choice(pre) + "".join(rnd.choice(cons) * (rnd.random() < 0.8) + rnd.choice(vowels)
                                      for _ in range(rnd.randint(1, 3))) + rnd.choice(suf)
        out.append(w.capitalize() if rnd.random() < 0.3 else w.upper() if rnd.random() < 0.03 else w)
    return out


def _de_regex_fuzz(n: int, rnd) -> list[str]:
    from vtts.frontend.de import normalize_de as nd

    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=()§‰° ") * 2 + list(nd.UNITS) + list(nd.CURRENCY)
             + list(nd.ABBREVIATIONS) + ["Uhr", " Uhr", "Mai", "am ", "die ", "ein ", "Stunde", "Frau", "−", ",-",
                                         "…", "...", "¿", "¡", "A", "B", "Z", "ESP", "x", "ab", "Ok", "Wi", "ä", "Ö",
                                         "ß", "é", " ", "  ", "“", "”", "«", "»", " "])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def de_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode de cases: edge cases, the eval sets, mixed-style sentences (templates x terms_en), the
    tests' strings, corpus sentences (when given and present), every stem and exception word, pseudo
    words over the spelling rules, number/date/time/money/unit cases and regex-dense random strings.
    Texts with a letter run longer than the device's word limit (VTTS_DE_MAXW = 64) are left out."""
    import json
    import random
    import re

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_de.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(DE_EDGE)
    for name in ("ood_de.jsonl", "mixed_de.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _lt_tests("de")
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows
    words = _de_words()
    texts += [" ".join(words[i:i + 12]) + "." for i in range(0, len(words), 12)]
    pseudo = _de_pseudo(rnd, 8000)
    texts += [" ".join(pseudo[i:i + 16]) + "." for i in range(0, len(pseudo), 16)]
    nums = []
    for _ in range(2500):
        k = rnd.randint(0, 19)
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**9),
                        rnd.randint(0, 10**15), rnd.randint(0, 10**25)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 40)
        nums.append(["{} Häuser", "{:,} Bücher", "{},5 %", "€ {}", "am {}. Mai", "-{} km", "{}.{}.2026", "{}-{} kg",
                     "{}:{:02d} Uhr", "{}.{:02d} Uhr", "die {}. Klasse", "{}.{:03d}.{:03d}", "{},{:02d} €", "{} Uhr",
                     "1 {} Stunde", "{}. {}", "{},{}", "+{} {} {}", "0{} {}", "{} {}"][k].format(v, a, b))
    for _ in range(500):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} und "
                    f"{rnd.randint(0, 33)}.{rnd.randint(0, 13)}.{rnd.randint(0, 99):02d} "
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _de_regex_fuzz(fuzz, rnd)
    out, seen = [], set()
    long_run = re.compile(r"[^\W\d_]{60,}")
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85  ") or long_run.search(text):
            continue
        seen.add(text)
        try:
            ids = text_to_ids(text, "de")
        except (ValueError, KeyError, IndexError):
            continue
        out.append("de\t" + text + "\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out


AR_EDGE = [
    "", ".", "،", "؟", "a", "ا", "ء", "ة", "ى", "و", "ب", "ال", "الـ", "ـــ", "مرحبا", "مرحبا، كيف حالك؟ أنا بخير؛ شكرا.",
    "ذهب الولد إلى المدرسة في الصباح.", "افتح Wi-Fi من فضلك؟ شكرا جزيلا.", "في عام 2024، بلغ عدد السكان 5 ملايين نسمة.",
    "هذا وذلك ولكن الله وبالله لله هؤلاء أولئك عمرو مائة داود طه", "الشمس والقمر بالشمس للقمر فالشمس كالقمر",
    "اِسْتِخْدَامٌ كِتَابٌ شُكْرًا عَرَبِيّ هُوَ مَعَ عِلْم عَلَم الْقَمَر الشَّمْس الِاتِّحَاد", "عـــربي ـالكتاب",
    "ک ی ٱلكتاب ۀ ھ ﻻ ﷲ ﷺ ﷼ ۖ ؐ", "ا" + "ٔ" + "َ" + "ل", "ا" + "َ" + "ٔ", "و" + "ٔ", "ي" + "ٔ" + "ِ", "ه" + "ٔ",
    "١٢٣٤٥ ۱۲۳۴۵ ٢٫٥ ١٬٢٥٠ ١٥٪", "0501234567 +966 50 123 4567 +9665012345678", "ESP32 و 5G و iPhone 15 و USB-C",
    "15/08/1947 و 2026-11-19 و 2024/1/5 و 32/13/2020 و 1/1/99", "الساعة 10:30 و 7:15 ص و 8:05 م و 23:59:59 و 24:00 مساء",
    "سنة 1445 هـ و 2024 م و 5 م و 12345 هـ", "عام 2024 والعام 1999 وبالعام 2000 في سنة 750 فالعام 2010",
    "$100 و 5 $ و 50 ر.س و 1 € و 2 £ و 3 د.إ و 11 USD و 1.50 $ و 1,000,000 ر.س و ﷼5",
    "15% و 2.5 % و 5 km و 5 كم و 3.5 كغ و 128GB و 30°C و 100 km/h و 5 كم/س", "من 10-20 وبين 10 - 20 و 5–7",
    "د. أحمد و أ.د. محمد و م. علي و كتب إلخ و ق.م و ص.ب 123", "«مرحبا» (أهلا) [نعم] {لا} \"اقتباس\"",
    "رقم -5 و -3.14 و 0.25 و 1,250.75 و 1,2345 و 12,345,678", "100000000000000 و 999999999999 و 1000000000000",
    "هل تعرف؟أنا لا.نعم!", "نعم … لا — ربما – حسنا", "A+B = C & D @ E × F # G / H",
    "ﻣﺮﺣﺒﺎ", "سلام" * 60, "كلمة " * 120 + ".", "ابن بن بنت أبو أبي", "الأهلي الماضي المغني",
    "Hello. مرحبا! How are you? بخير؛", "Café naïve", "मेरा नाम", "中文 한국어 Tiếng Việt",
]


def _ar_test_strings() -> list[str]:
    root = Path(__file__).parents[2]
    out: list[str] = []
    for name in ("test_ar_g2p.py", "test_normalize_ar.py", "test_text_ar.py"):
        src = (root / "tests" / "frontend" / name).read_text(encoding="utf-8")
        out += [m for m in re.findall(r'"([^"\n]*[؀-ۿ][^"\n]*)"', src)]
    return out


def _ar_words() -> list[str]:
    """Every table word and spelling word, bare and with clitics, endings and pronouns."""
    from vtts.frontend.ar.g2p_ar import ENDINGS, PRONOUNS, lexicon, spelling_table

    out = []
    for k in list(lexicon()) + list(spelling_table()):
        out.append(k)
        out.append(k + " " + "".join(c for c in lexicon().get(k, spelling_table().get(k, ""))))
    for i, k in enumerate(lexicon()):
        pre = ["و", "ف", "ب", "ك", "ل", "ال", "وال", "بال", "لل", "فلل", "وب"][i % 11]
        suf = [p for p, _ in PRONOUNS][i % len(PRONOUNS)]
        end = ENDINGS[i % len(ENDINGS)][0]
        stem = k.removesuffix("ة")
        out.append(f"{pre}{k} {k}{suf} {stem}{end} {pre}{stem}{end} {k[:-1] + 'ت' if k.endswith('ة') else k}{suf}")
    return [" ".join(out[i:i + 6]) for i in range(0, len(out), 6)]


_AR_LETTERS = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
_AR_MARKS = ["", "", "", "", "َ", "ُ", "ِ", "ْ", "ّ", "ًا", "ٌ", "ٍ", "َّ", "ٰ"]


def _ar_random_words(rnd, n: int) -> list[str]:
    """Random letter strings, half with random vowel marks: patterns, default reading, reader."""
    words = []
    for _ in range(n):
        k = rnd.randint(1, 8)
        marked = rnd.random() < 0.4
        w = "".join(rnd.choice(_AR_LETTERS) + (rnd.choice(_AR_MARKS) if marked else "") for _ in range(k))
        if rnd.random() < 0.3:
            w = rnd.choice(["ال", "وال", "بال", "لل", "و", "ب", "ف", "ك", "ل"]) + w
        words.append(w)
    return [" ".join(words[i:i + 15]) + rnd.choice([".", "؟", "!", "،", ""]) for i in range(0, len(words), 15)]


def _ar_generated(vocab: list[str], n: int, rnd) -> list[str]:
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "laptop",
             "software", "YouTube", "km", "GB", "USD", "kWh"]
    out = []
    for k in range(n):
        words = []
        for _ in range(rnd.randint(5, 30)):
            w = rnd.choice(vocab)
            if rnd.random() < 0.08:
                w += "،"
            words.append(w)
        if k % 3 == 0:
            for _ in range(rnd.randint(1, 3)):
                pos = rnd.randrange(len(words) + 1)
                v = rnd.choice([str(rnd.randint(0, 100)), str(rnd.randint(0, 10 ** 7)), rnd.choice(latin),
                                f"{rnd.randint(1, 28)}/{rnd.randint(1, 12)}/{rnd.randint(1900, 2100)}",
                                f"{rnd.randint(0, 23)}:{rnd.randint(0, 59):02d}", f"${rnd.randint(1, 99999)}",
                                f"{rnd.randint(1, 99)}%", "عام " + str(rnd.randint(1000, 2100)),
                                str(rnd.randint(0, 9999)).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))])
                words.insert(pos, v)
        out.append(" ".join(words) + rnd.choice([".", "؟", "!", ".", "۔"]))
    return out


def _ar_numbers(rnd) -> list[str]:
    def ind(t: str) -> str:
        return t.translate(str.maketrans("0123456789,.%", "٠١٢٣٤٥٦٧٨٩٬٫٪"))

    out = []
    for _ in range(2500):
        k = rnd.randint(0, 19)
        v = rnd.choice([rnd.randint(0, 99), rnd.randint(0, 99999), rnd.randint(0, 10 ** 9), rnd.randint(0, 10 ** 13),
                        rnd.randint(0, 10 ** 20)])
        a, b = rnd.randint(0, 40), rnd.randint(0, 70)
        t = ["عدد {} شخص", "{:,} ريال", "${}", "{} $", "{}.5%", "{} km", "{} كم", "{}GB", "{}-{} يوما", "من {}-{}",
             "{}:{} ص", "{}/{}/{}", "عام {}", "-{} درجة", "{}.{}", "هاتف 05{}", "+966 {}", "{} ر.س", "{} هـ",
             "{}-{}-{}"][k]
        text = t.format(v, a, b) if "{" in t else t
        out.append(ind(text) if rnd.random() < 0.25 else text)
    for _ in range(500):
        out.append(f"{rnd.randint(1, 35)}/{rnd.randint(0, 13)}/{rnd.randint(1000, 2999)} و "
                   f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} في "
                   f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d} "
                   f"{rnd.choice(['ص', 'م', 'صباحا', 'مساء', '', 'مساءً'])}")
    return out


def _ar_regex_fuzz(n: int, rnd) -> list[str]:
    atoms = (list("0123456789") * 4 + list(":/.,-–%'+&@=×°# ") * 2
             + ["٠", "٥", "٩", "۴", "٫", "٬", "٪", "،", "؛", "؟", "۔", "ـ", "عام", "سنة", "العام", "والعام", "من",
                "هـ", "ه", "م", "ص", "صباحا", "مساء", "ر.س", "د.إ", "د.ك", "ج.م", "﷼", "$", "US$", "USD", "€", "£",
                "km", "km/h", "كم", "كم/س", "سم", "مم", "كغ", "كجم", "m", "g", "GB", "kWh", "°C", "℃", "د.", "أ.د.",
                "م.", "إلخ", "الخ", "ق.م", "ص.ب", "ت.", "…", "—", "...", "«", "»", "(", ")", "ESP", "A", "B", "Z",
                "x", "ab", "Ok", "é", "ك", "ا", "َ", "ّ", "ٔ", " ", "  ", " ", "+966", "_", "ال", "كتاب"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 16))) for _ in range(n)]


def ar_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode "ar" cases: edge cases, the eval sets and unit-test strings, Wikipedia sentences (the given
    files when present), sentences built from their words, template x term sentences, every table
    word with clitics and endings, random (vowelled) words, number/date/time/money cases and
    regex-dense random strings."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_ar.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(AR_EDGE) + _ar_test_strings()
    for name in ("ood_ar", "mixed_ar"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / f"{name}.jsonl").read_text(
            encoding="utf-8").splitlines() if x.strip()]
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows
    vocab = sorted({w.strip(".،؟!") for t in rows + temps for w in t.replace("{T}", " ").split()} - {""})
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    if vocab:
        texts += _ar_generated(vocab, 1500, rnd)
    texts += _ar_words()
    texts += _ar_random_words(rnd, 15000)
    texts += _ar_numbers(rnd)
    texts += _ar_regex_fuzz(fuzz, rnd)
    out = []
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        out.append(f"ar\t{text}\t" + ";".join(" ".join(map(str, c)) for c in text_to_ids(text, "ar")))
    return out


FE_EDGE = {
    "fi": [
        "Hei, mitä kuuluu?", "Helsinki on Suomen pääkaupunki.", "Hän syntyi 3. toukokuuta 1950. Sitten hän muutti.",
        "Paikalla oli n. 50 henkeä, esim. Matti.", "Kokous alkaa klo 14.30 ja maksaa 12,50 €.", "Kello on nyt 15.45.",
        "kello 9 ja klo 9.05", "Päivä 3.5.2026 ja 2026-11-19 ja 19/11/2026.", "15.12. alkaen", "1 000 000 asukasta",
        "+358 40 123 4567, 040 1234567, 09 123 456", "Turn on the light.", "Spotify on hyvä.", "Avaa GitHub, kiitos.",
        "vuosina 1939–1945", "10-20 km", "15 % ja 1 %", "25 °C", "-5 astetta", "ESP32-P4, USB ja Nato",
        "kaksisataakolmekymmentäneljä", "kahdestakymmenestä", "kengät, kukka, saari, Åbo, Zürich, straße", "", "a",
        "...", "k. 1999 s. 1920 v. 1990", "Kissa & koira", "3 kpl, 2 milj. euroa", "eKr. ja jKr.", "Oy ja ry",
    ],
    "el": [
        "Τι κάνεις; Καλά.", "Γεια σου· τι λες;", "Άνοιξες το Netflix;", "ΟΔΟΣ ΑΘΗΝΑΣ", "Έχω 3 παιδιά, 3 αδελφές και 4 φίλους.",
        "200 γυναίκες και 1 ώρα", "Στις 14:30 και στις 9.15.", "Γεννήθηκε στις 3/5/1990.", "1 Μαΐου 2024", "2026-11-19",
        "12,50 € και 1 € και $20 και £3", "15% και 25 °C, 5 km και 1 km, 3 χλμ.", "1.000.000 κάτοικοι", "3,5 και -5",
        "10-20", "π.χ. η ΔΕΗ, κ.λπ.", "ΗΠΑ και ΕΕ", "Το ΑΒΓ.", "Τηλ. 210 1234567 ή +30 6912345678", "ESP32-P4",
        "Ο 2ος όροφος, η 3η θέση, το 21ο.", "Το 1821.", "Ο κ. Παπαδόπουλος.", "χλμ. σε", "άν́", "Αθήνα",
        "ἄνθρωπος ᾠδή", "ΣΑΣ Σ σ ς", "Εύβοια, αύριο, ευχαριστώ, λαϊκός, τσάι, τζάμι, παιδιά, γιατί, ποιος", "", "α",
        "...", "Turn on the light.", "Είναι περ. είκοσι.",
    ],
}


def _fe_words(lang: str) -> list[str]:
    import json

    from vtts.frontend.lexicons import load_table

    root = Path(__file__).parents[2]
    words: set[str] = set()
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                words.update(json.loads(x)["text"].split())
    for t in (root / "scripts" / "data" / "bilingual" / f"templates_{lang}.txt").read_text(encoding="utf-8").splitlines():
        words.update(t.replace("{T}", " ").split())
    for k in load_table(lang, "overrides"):
        words.update({k, k.capitalize(), k.upper()})
    if lang == "fi":
        from vtts.frontend.fi import g2p_fi, normalize_fi
        from vtts.frontend.lexicons import load_words

        words.update(load_words("fi", "native"))
        words.update(g2p_fi._all_number_parts())
        words.update(g2p_fi.UNSTRESSED)
        words.update(normalize_fi.ABBREVIATIONS.values())
    else:
        from vtts.frontend.el import g2p_el, normalize_el

        words.update(g2p_el.UNSTRESSED)
        words.update(normalize_el.ABBREVIATIONS.values())
        words.update(normalize_el.MONTHS[1:])
        words.update(normalize_el.FEMININE_WORDS)
        words.update(k.upper() for k in normalize_el.ACRONYM_WORDS)
    return sorted(w for w in words if w)


def _fe_pseudo(lang: str, rnd, n: int) -> list[str]:
    """Random words of the language's letters (every branch of the spelling rules)."""
    if lang == "fi":
        vowels = ["a", "e", "i", "o", "u", "y", "ä", "ö", "å", "aa", "ii", "uu", "yy", "ää", "öö", "ai", "uo", "ie", "yö"]
        cons = ["k", "kk", "p", "pp", "t", "tt", "s", "ss", "l", "ll", "m", "mm", "n", "nn", "r", "rr", "h", "j", "v",
                "ng", "nk", "nkk", "np", "nb", "sh", "sch", "ch", "ph", "th", "ck", "qu", "x", "z", "zz", "c", "cc",
                "q", "w", "š", "ž", "b", "d", "f", "g", "st", "pr", "tr", "kr", "sp", "ht", "ls", "rk"]
        ends = ["", "", "", "n", "t", "s", "l", "r", "k", "ng", "c", "x", "nen", "ssa", "ssä", "lla", "kin"]
    else:
        vowels = ["α", "ε", "η", "ι", "ο", "υ", "ω", "ά", "έ", "ή", "ί", "ό", "ύ", "ώ", "ϊ", "ϋ", "ΐ", "ΰ", "αι", "ει",
                  "οι", "υι", "ου", "αί", "εί", "οί", "ού", "αϊ", "άι", "αυ", "ευ", "ηυ", "αύ", "εύ", "ια", "ιά", "ιο",
                  "ιό", "ειά", "ιου", "ἀ", "ᾶ", "ὠ"]
        cons = ["β", "γ", "δ", "ζ", "θ", "κ", "λ", "μ", "ν", "ξ", "π", "ρ", "σ", "τ", "φ", "χ", "ψ", "μπ", "ντ", "γκ",
                "γγ", "γχ", "γξ", "τσ", "τζ", "λλ", "μμ", "σμ", "σβ", "τρ", "κρ", "πλ", "στ", "σκ", "γι", "χι"]
        ends = ["", "", "ς", "ν", "ς", "ος", "ες", "οι", "ους", "ας", "ης", "εις"]
    out = []
    for _ in range(n):
        w = "".join(rnd.choice(cons) * (rnd.random() < 0.8) + rnd.choice(vowels) for _ in range(rnd.randint(1, 4)))
        w += rnd.choice(ends)
        out.append(w.capitalize() if rnd.random() < 0.2 else w.upper() if rnd.random() < 0.05 else w)
    return out


def _fe_numbers(lang: str, rnd) -> list[str]:
    fi = ["{} kissaa", "{:,} kirjaa", "{},5 %", "{} %", "€ {}", "{} €", "{},{:02d} €", "-{} km", "{}.{}.2026",
          "{}.{}.", "{}. toukokuuta", "klo {}.{:02d}", "kello {}", "{}:{:02d}", "{}.{:02d}", "{}–{}",
          "{} {:03d} {:03d}", "+358 {} {}", "0{} {} {}", "{}/{}/2026", "{} {:03d}", "{} 1 km", "{}.{:03d}.{:03d}"]
    el = ["{} παιδιά", "{} αδελφές", "{} φίλους", "{} ώρες", "{} Μαΐου", "{:,} βιβλία", "{},5%", "{}%", "€{}", "{} €",
          "{},{:02d} €", "-{} km", "{}/{}/2026", "{}.{}.2026", "{}ος", "{}η", "{}ο", "{}ός", "στις {}.{:02d}",
          "{}:{:02d}", "{}-{}", "+30 {} {}", "210 {} {}", "{}.{:03d}.{:03d}", "{} χλμ.", "{} γυναίκες"]
    temps = fi if lang == "fi" else el
    out = []
    for _ in range(2500):
        t = rnd.choice(temps)
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**9),
                        rnd.randint(0, 10**15), rnd.randint(0, 10**25)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 40)
        out.append(t.format(v, a, b))
    for _ in range(500):
        out.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} ja "
                   f"{rnd.randint(0, 33)}.{rnd.randint(0, 13)}.{rnd.randint(0, 99):02d} "
                   f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d} "
                   f"{rnd.randint(0, 25)}.{rnd.randint(0, 61):02d}")
    return out


def _fe_regex_fuzz(lang: str, n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalizer passes react to."""
    if lang == "fi":
        from vtts.frontend.fi import normalize_fi as nm

        extra = ["kello ", "klo ", "toukokuuta", " a", " ä", " b", ". k", " ", " ", "ä", "ö", "å", "Ä",
                 "š", "ng", "nk", "on", "the", "Turn"]
    else:
        from vtts.frontend.el import normalize_el as nm

        extra = ["στις ", "Μαΐου", "ώρες", "παιδιά", "φίλους", "ος", "η", "ό", "ΔΕΗ", "ΑΒΓ", "ΑΘΗΝΑ", "·", ";", ";",
                 "́", "̈", "Σ", "σ", "ς", "ά", "ϊ", "ΐ", "ἀ", "α", "ε", "ι", "ου"]
    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=() ") * 2 + list(nm.UNITS) + list(nm.CURRENCY)
             + list(nm.ABBREVIATIONS) + extra + ["…", "...", "¿", "¡", "A", "B", "Z", "ESP", "x", "ab", "Ok", "Wi", "é",
                                                 " ", "  ", "\t", "“", "”", "«", "»", "²", "٣"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def fe_lines(lang: str, paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode fi|el cases (see the module docstring); texts for which Python raises are left out."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / f"templates_{lang}.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(FE_EDGE[lang])
    for name in (f"ood_{lang}.jsonl", f"mixed_{lang}.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _lt_tests(lang)
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    words = _fe_words(lang)
    pseudo = _fe_pseudo(lang, rnd, 6000)
    if not rows:  # generated sentences
        for _ in range(limit or 3000):
            parts = [rnd.choice(words) if rnd.random() < 0.6 else rnd.choice(pseudo) for _ in range(rnd.randint(2, 14))]
            rows.append(" ".join(parts) + rnd.choice([".", "!", "?", ";", ""]))
    texts += rows
    texts += [" ".join(words[i:i + 20]) + "." for i in range(0, len(words), 20)]
    texts += [" ".join(pseudo[i:i + 20]) + "." for i in range(0, len(pseudo), 20)]
    texts += _fe_numbers(lang, rnd) + _fe_regex_fuzz(lang, fuzz, rnd)
    out, seen = [], set()
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85  "):  # line breaks of splitlines()
            continue
        seen.add(text)
        try:
            ids = text_to_ids(text, lang)
        except (ValueError, KeyError, IndexError):  # Python raises: not a case
            continue
        out.append(f"{lang}\t{text}\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out


TL_EDGE = [
    "", ".", "...", "¿?", "¡!", "a", "A", "y", "t", "'t", "'y", "ñ", "é", "'", "-", "--", "ng", "Ng", "NG", "mga", "Mga",
    "MGA", "ng mga", "nang", "ngayon", "Kumain ka na ba?", "Salamat po!", "  espasyo  ", "maraming\ttab", "linya\nbago",
    "batà bata bátà hindî hindi akó ako", "BATÀ HINDÎ", "Niño Villa Quezon Cebu Pasig", "Hosé José jose Juan Jesus",
    "tao kain maaari Bagyo noon loob doon kalooban", "mag-aral pag-ibig nag-ayos MAG-ARAL Mag-Aral mag-Aral",
    "araw-araw isa-isa Araw-araw ARAW-ARAW araw-ARAW gabi-gabi bahay-bahayan", "i-share nag-email na-update mag-Facebook",
    "dalawampu't isang tao ako'y ikaw't", "kumain kinain sumulat sinulat umalis inalis", "pinakamaganda napakaganda",
    "nakapagluto makapagluto magpaluto pakiabot ipaluto", "kainan kainin bilhin sulatan", "rehiyon nayon siyudad lungsod",
    "opisyal nasyonal kapital militar papel doktor ingles", "tsinelas dyip sapatos shampoo chismis", "Wi-Fi iPhone 15 Pro",
    "ESP32-P4 RTX3060", "USB, GPS at NASA.", "DOH PAGASA NATO ASEAN UNESCO", "GitHub at YouTube", "smart home", "weekend",
    "Gng. Santos at Bb. Cruz", "Dr. Reyes, Dra. Lim", "Brgy. San Jose, Sto. Niño, Sta. Ana", "Sen. Pres. Gob. Kap.",
    "Engr. Atty. Jr. Sr.", "Mt. Apo St. Peter Hwy. 1", "atbp.", "Blg. 5", "pp. 10-20", "Kgg. Hen.",
    "alas 3:00", "alas-3:15", "ala 1:00", "Alas 3:30 ng hapon", "3:45 PM", "10:30 a.m.", "7:00 am.", "12:00 pm",
    "0:15", "13:00", "18:30", "23:59:59", "24:00", "7:5", "1:00 ng madaling araw", "2:00 ng  hatinggabi", "9:00 ng gabing",
    "₱50", "₱1", "₱2", "₱999", "₱1,000", "₱1,500.50", "₱0.50", "₱5.00", "₱ 250", "PHP 100", "Php 75.25", "₱5 milyon",
    "₱1.5 bilyon", "₱10 libong", "US$20", "$5.50", "€3", "£7", "¥100", "50%", "-3.5%", "5 km", "3kg", "100 km/h",
    "25°C", "30℃", "45°", "16GB", "2 L", "10 ha", "11/19/2026", "19/11/2026", "13/13/2026", "2026-11-19",
    "2026-13-45", "Nobyembre 19, 2026", "Nob. 19 2026", "19 Nobyembre 2026", "19 nob. 2026", "Mayo 1", "may 5",
    "Set. 5", "ſet. 5", "5 dİs.", "ika-3", "ika-1 puwesto", "Ika-21 siglo", "ika3", "ika-0", "ika-3 na",
    "10-20 tao", "10 – 20", "0917 123 4567", "+63 917 123 4567", "02-8123-4567", "0281234567", "1234567",
    "1.234,5 tao", "21,234.531,234.5", "1,234,5", "3.14", "1,000,000", "1.000.000", "0.05", "00,5", "5 tao",
    "5 na tao", "5 at 6", "3.5 tao", "100 tao", "400 tao", "1000000 tao", "1000000000000000000", "-7 grado",
    "2 + 3 = 5", "R&D", "#1", "@home", "3×4", "1/2", "Hello. Kumusta! How are you? Mabuti; salamat.",
    "“sipi” (panaklong) [a] {b} <c> «d»", "teka… sige—tara", "teka...muna", "Ⅻ ½ ² ٣٤", "İka-İka ıka",
    "Ang mga bata ay naglalaro sa labas ng bahay araw-araw.",
    "Mahabang pangungusap " + "isa dalawa tatlo apat lima anim pito walo siyam sampu " * 6 + "wakas.",
]


def _tl_words() -> list[str]:
    """Words of the Tagalog eval sets, the templates, the stress table and the word lists, with
    affixes and clitics on table words."""
    import json

    from vtts.frontend.lexicons import load_table, load_words
    from vtts.frontend.tl.g2p_tl import PREFIXES, SUFFIXES

    root = Path(__file__).parents[2]
    words: set[str] = set()
    for name in ("ood_tl.jsonl", "mixed_tl.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                words.update(json.loads(x)["text"].split())
    for t in (root / "scripts" / "data" / "bilingual" / "templates_tl.txt").read_text(encoding="utf-8").splitlines():
        words.update(t.replace("{T}", " ").split())
    table = load_table("tl", "stress")
    for k, v in table.items():
        words.update({k, v, k.capitalize(), k.upper(), k + "ng", k + "'t", k + "'y", k + "ng'y"})
    for k in list(table)[:80]:
        words.update({p + k for p in PREFIXES} | {k + s for s in SUFFIXES} | {k[0] + "um" + k[1:], k[0] + "in" + k[1:]})
        words.update({"na" + p + k for p in ("paka", "ka", "pa")})
    words.update(load_words("tl", "native"))
    return sorted(words)


def _tl_pseudo(rnd, n: int) -> list[str]:
    """Random words of Tagalog letters (every branch of the spelling and stress rules)."""
    vowels = list("aeiou") * 4 + ["á", "à", "â", "é", "è", "ê", "í", "ì", "î", "ó", "ò", "ô", "ú", "ù", "û", "aa", "ii"]
    cons = ["b", "k", "d", "g", "h", "l", "m", "n", "ng", "ngg", "p", "r", "s", "t", "w", "y", "c", "ch", "ts", "sh",
            "ll", "qu", "q", "x", "ñ", "f", "v", "z", "j", "pr", "tr", "kw", "dy", "sy", "'", "-", "kk", "nn", "bl", "st"]
    endings = ["", "", "", "n", "ng", "s", "r", "l", "t", "k", "y", "w", "yon", "yal", "nal", "tal", "dad", "ar", "el",
               "or", "an", "in", "han", "hin", "ng", "'t", "'y", "ks", "ts", "nd"]
    out = []
    for _ in range(n):
        w = rnd.choice(["", "", "", "mag", "nag", "pag", "ma", "na", "pa", "ka", "i", "maka", "naka", "pinaka", "um", "in"])
        w += "".join(rnd.choice(cons) * (rnd.random() < 0.8) + rnd.choice(vowels) for _ in range(rnd.randint(1, 4)))
        w += rnd.choice(endings)
        out.append(w.capitalize() if rnd.random() < 0.2 else w.upper() if rnd.random() < 0.03 else w)
    return out


def _tl_generated(n: int, rnd) -> list[str]:
    vocab = _tl_words()
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1", "smart",
             "GitHub", "YouTube", "Netflix", "weekend", "update", "online", "router", "Spotify", "macOS", "NASA",
             "i-share", "nag-email", "mag-Facebook"]
    numbers = ["3", "15", "21", "100", "400", "2026", "3.5", "1,000", "1,234.56", "50%", "9:30", "₱20", "₱1,500",
               "-7", "2026-05-01", "5/3/2026", "10-20", "25 °C", "5 km", "ika-2", "ika-1", "alas 3:00", "0917 123 4567",
               "Nob. 19", "19 Mayo 2026", "3:00 pm", "PHP 50"]
    marks = [",", ".", "!", "?", ";", ":", "…", "—", "“", "”", "(", ")", "¿", "¡", "«", "»"]
    pseudo = _tl_pseudo(rnd, 4 * n)
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 14)):
            r = rnd.random()
            if r < 0.45:
                parts.append(rnd.choice(vocab))
            elif r < 0.7:
                parts.append(rnd.choice(pseudo))
            elif r < 0.82:
                parts.append(rnd.choice(numbers))
            elif r < 0.92:
                parts.append(rnd.choice(latin))
            else:
                parts.append(rnd.choice(marks))
        out.append(" ".join(parts) + rnd.choice([".", "!", "?", "", "。", "..."]))
    return out


def _tl_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the Tagalog normalizer passes react to."""
    from vtts.frontend.tl import normalize_tl as nm

    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=() ") * 2 + list(nm.UNITS) + list(nm.CURRENCY)
             + list(nm.ABBREVIATIONS) + ["ika", "Ika", "ika-", "alas ", "ala ", "ALAS-", "ng ", "NG ", "hapon", "gabi",
                                          "umaga", "madaling araw", "hatinggabi", "am", "p.m.", "PM", "libo", "milyon",
                                          "mayo ", "Nob. ", "Set.", "disyembre ", "ſ", "İ", "ı", "K", "na", "tao",
                                          "araw", "-araw", "ARAW", "mag", "-aral", "-Aral", "á", "à", "â", "ñ", "Ñ",
                                          "…", "...", "¿", "¡", "A", "B", "Z", "ESP", "DOH", "x", "ab", "Ok", "Wi",
                                          " ", "  ", "\t", "“", "”", "«", "»", "́", "̀", "̃"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def tl_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode tl cases: edge cases, the eval sets, the mixed-style sentences (templates x terms_en),
    the tests' strings, sentences (corpora when given and present, else generated from the vocabulary
    and random words), every table word with affixes and clitics, number/date/time/money/unit cases
    and regex-dense random strings. Texts for which the Python front-end raises are left out."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_tl.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(TL_EDGE)
    for name in ("ood_tl.jsonl", "mixed_tl.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _lt_tests("tl")
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if limit and len(rows) > limit:
        rows = rnd.sample(rows, limit)
    texts += rows if rows else _tl_generated(limit or 3000, rnd)
    words = _tl_words()
    texts += [" ".join(words[i:i + 20]) + "." for i in range(0, len(words), 20)]
    pseudo = _tl_pseudo(rnd, 6000)
    texts += [" ".join(pseudo[i:i + 20]) + "." for i in range(0, len(pseudo), 20)]
    nums = []
    for _ in range(2500):
        k = rnd.randint(0, 19)
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**9),
                        rnd.randint(0, 10**15), rnd.randint(0, 10**25)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 40)
        nums.append(["{} tao", "{:,} libro", "{}.5%", "₱{}", "ika-{} puwesto", "-{} km", "{}/{}/2026", "{}-{} kg",
                     "{}:{:02d}", "alas {}:{:02d} ng gabi", "{}:{:02d} pm", "{}.{:03d}.{:03d}", "₱{}.{:02d}", "PHP {}",
                     "{} na", "Mayo {}, {}", "{} Nob. {}", "{},{}", "+{} {} {}", "{} {}"][k].format(v, a, b))
    for _ in range(500):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} at "
                    f"{rnd.randint(0, 33)}/{rnd.randint(0, 13)}/{rnd.randint(0, 99):02d} "
                    f"{rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _tl_regex_fuzz(fuzz, rnd)
    out, seen = [], set()
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85  "):  # line breaks of splitlines()
            continue
        seen.add(text)
        try:
            ids = text_to_ids(text, "tl")
        except (ValueError, KeyError, IndexError):
            continue
        out.append("tl\t" + text + "\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out


SW_EDGE = [
    "", ".", "...", "¿?", "¡!", "a", "A", "m", "n", "x", "'", "’", "-", "--", "Habari yako?", "Habari. Kwaheri!",
    "  nafasi  ", "tab\tkati", "mstari\nmpya", "ng'ombe", "ng’ombe", "Ng'ombe", "NG'OMBE", "ng'", "'ng", "n'gombe",
    "ngoma", "ngamia", "nge", "mtu", "mtoto", "mzee", "nchi", "nne", "wanne", "mmea", "mwana", "myaka", "mbwa",
    "nyumba", "ndizi", "njia", "nzuri", "ng'ombe-ng'ombe", "kiatu", "kaa", "Allah", "Allahu", "lazima", "Lazima",
    "LAZIMA", "lázima", "lazíma", "lazimá", "na", "ya", "kwa", "ni", "Na", "kwanza", "taxi", "quiz", "cheche",
    "shule", "thelathini", "dhambi", "ghali", "khamsini", "single", "table", "simple", "kole", "ale", "klabu",
    "takriban", "rasmi", "binafsi", "phone", "whatsapp", "hhh", "km", "kg", "mm", "nn", "sh", "ḿtu", "ńchi",
    "café", "naïve", "Øresund", "İstanbul", "ıi", "ſaa", "straße", "Œuvre", "ﬁ", "ｈａｂａｒｉ", "𝐡𝐚𝐛𝐚𝐫𝐢", "Ⅻ",
    "x²", "½", "٣ ٤", "١٢:٣٠", "中文", "한국어", "Việt Nam", "ελληνικά", "русский", "a\u0301", "e\u0301\u0301",
    "\u0301a", "o\u0323\u0301", "u\u0301\u0323", "ǘ", "Ǘ", "Á", "ḿ", "Wi-Fi", "iPhone 15 Pro", "ESP32-P4",
    "RTX3060", "USB, GPS na NASA.", "CCM TANESCO NSSF PIN RAM ROM TAMISEMI TANAPA UNESCO UNICEF COVID NATO",
    "GitHub na YouTube", "smart home", "weekend", "update", "e-mail", "don't", "it's", "x-ray", "ABCDEF", "AB",
    "ABCDE", "A1B2C3", "a1b2", "_x_", "x_y", "C++", "R&D", "Q&A", "2 + 3 = 5", "a@b.com", "#1", "3 × 4", "1/2",
    "10%", "10 %", "-10%", "50,5%", "asilimia 75%", "Asilimia 5 %", "ASILIMIA 5%", "asilimia  5%", "asilimia5%",
    "1.000.000", "1,000,000", "1,250.50", "1.000", "1,5", "3.14", "3,14", "0.5", ".5", "5.", "007", "0712345678",
    "0712 345 678", "+255 712 345 678", "+254-712-345-678", "712-345-678", "12 34 56 78 90 12", "1 2 3", "12 34",
    "14:30", "14:30:15", "saa 14:30", "Saa 9:15", "SAA 3:05", "saa  7:00", "saa7:00", "7:00", "7:15", "7:30",
    "7:45", "23:59", "24:00", "25:00", "9:5", "0:00", "19/11/2026", "tarehe 19/11/2026", "Tarehe 1/1/2000",
    "tarehe 32/13/2020", "05/03/26", "31/12/1999", "2026-03-05", "tarehe 2026-03-05", "2026-13-45", "12026-1-1",
    "1-2-3", "10-20", "10 - 20", "10 – 20", "10–20", "wa 1", "ya 2", "Wa 1", "KWA 2", "mwa 1", "la 2", "cha 1",
    "vya 2", "za 1", "pa 2", "wa 3", "wa 1.", "wa 12", "wa 1,", "wa 1:", "wa 1/2", "wa 1a", "wa  1", "kwa 1",
    "TSh 5,000", "TSh5,000", "TSh 5,000/=", "5,000/=", "5,000 /=", "Sh. 500", "Sh 500", "KSh 1,500.50",
    "KSh 1,500.05", "USh 2,000", "UGX 1,000", "TZS 100", "KES 50", "$5", "$ 5", "US$ 1,250.50", "20 €", "20€",
    "£7", "¥100", "5 shilingi", "5shilingi", "5  shilingi", "5 Sh", "5 TSh", "5 KSh", "5 Shilingi", "TSh0.50",
    "5 km", "5km", "km 190", "km  190", "kg 1.2", "kWh 3", "kW 3", "ml 250", "GB 16", "mm 5", "ha 3", "km/h 50",
    "1 km", "21 km", "1,5 kg", "25 °C", "25°C", "30℃", "40°", "-5 °C", "100 km/h", "60 km/saa", "16 GB",
    "3 kWh", "5000 mAh", "2 l", "1 L", "3 ha", "5 m", "5 g", "5 W", "5 V", "5 GHz", "5 MHz", "5 TB", "5 MB",
    "Bw. Juma", "Bi. Amina", "Dkt. Mwakyembe", "Dk. Ali", "Prof. Shivji", "Mh. Rais", "Mhe. Waziri",
    "S.L.P. 123", "Mt. Petro", "Na. 5", "Nam. 5", "mwaka 500 BK", "mwaka 50 KK", "vitabu, n.k.", "nk. na k.m.",
    "n.k. zaidi", "…", "—", "–", "a — b", "a - b", "a—b", "eh...", "eh....", "“kunukuu”", "«kunukuu»",
    "(mabano) [mabano]", "{mabano} <ndogo>", "*nzito*", "~tilde~", "a|b", "mwaka 2026", "x\x1cy", "x\x85y",
    "a।b", "a。b", "a; b", "a ; b", "1999-2000", "2000-01", "100-200 km", "3-2", "-3", "- 3", "a-3", "3-a", "3.",
    "3,", "3, 4", "3.4.5", "1,23,456", "1,234,5678", "12.345.678,9", "999,999,999,999,999", "1000000000000000",
    "999999999999999", "123456789012345678901234567890", "0000000000000001", "0,000", "0.00", "00,5", "100000",
    "250000", "999999", "1001", "1100", "1010", "1000001", "1000000001", "1234567890123",
    "Kasi: 100 km/h; uzito: 5 kg.", "Ni saa 7:30 na joto ni 25 °C.", "Bei ni TSh 1,250.50 au $20.",
]


def _sw_words() -> list[str]:
    """Words of the eval sets, the templates, the word lists and the stress table."""
    import json

    from vtts.frontend.lexicons import load_table, load_words
    from vtts.frontend.sw import g2p_sw, normalize_sw

    root = Path(__file__).parents[2]
    words: set[str] = set()
    for name in ("ood_sw.jsonl", "mixed_sw.jsonl"):
        for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines():
            if x.strip():
                words.update(json.loads(x)["text"].split())
    for t in (root / "scripts" / "data" / "bilingual" / "templates_sw.txt").read_text(encoding="utf-8").splitlines():
        words.update(t.replace("{T}", " ").split())
    for k, v in load_table("sw", "stress").items():
        words.update({k, v, k.capitalize(), k.upper()})
    words.update(load_words("sw", "native"))
    words.update(w.capitalize() for w in load_words("sw", "native"))
    words.update(g2p_sw.UNSTRESSED)
    words.update(normalize_sw.ACRONYM_WORDS)
    words.update(w.upper() for w in normalize_sw.ACRONYM_WORDS)
    words.update(normalize_sw.ABBREVIATIONS)
    words.update(normalize_sw.ABBREVIATIONS.values())
    words.update(normalize_sw.UNITS)
    words.update(normalize_sw.LETTERS.values())
    return sorted(words)


def _sw_pseudo(rnd, n: int) -> list[str]:
    """Random words of Swahili letters (every branch of the spelling rules and the spelling check)."""
    vowels = "aeiouáéíóú"
    cons = ["b", "ch", "d", "dh", "f", "g", "gh", "h", "j", "k", "kh", "l", "m", "n", "ng'", "ng", "ny", "p", "r", "s",
            "sh", "t", "th", "v", "w", "y", "z", "mb", "nd", "nj", "nz", "mw", "kw", "bw", "c", "q", "x", "tt", "ll",
            "kr", "str", "ph", "wh", "pl", "'"]
    out = []
    for _ in range(n):
        w = rnd.choice(["", "", "", "m", "n", "mm", "nn", "ng'", "M", "N"])
        w += "".join(rnd.choice(cons) * (rnd.random() < 0.85) + rnd.choice(vowels) + rnd.choice(vowels) * (rnd.random() < 0.2)
                     for _ in range(rnd.randint(1, 4)))
        w += rnd.choice(["", "", "", "", "", "n", "m", "s", "k", "le", "ble", "'le", "ng", "ng'"])
        out.append(w.capitalize() if rnd.random() < 0.2 else w.upper() if rnd.random() < 0.03 else w)
    return out


def _sw_generated(n: int, rnd) -> list[str]:
    vocab = _sw_words()
    latin = ["Wi-Fi", "USB", "iPhone", "email", "OK", "AI", "app", "Bluetooth", "ESP32", "5G", "GPU", "A1", "smart",
             "GitHub", "YouTube", "Netflix", "weekend", "update", "online", "router", "Spotify", "macOS", "NASA"]
    numbers = ["3", "15", "21", "100", "2026", "3.5", "1,000", "1,250.50", "50%", "9:30", "$20", "-7", "2024-05-01",
               "19/11/2026", "10-20", "25 °C", "5 km", "km 5", "wa 1", "ya 2", "TSh 5,000", "5,000/=", "0712345678"]
    marks = [",", ".", "!", "?", ";", ":", "…", "—", "“", "”", "(", ")", "¿", "¡", "«", "»", "’"]
    pseudo = _sw_pseudo(rnd, 4 * n)
    out = []
    for _ in range(n):
        parts = []
        for _ in range(rnd.randint(2, 14)):
            r = rnd.random()
            parts.append(rnd.choice(vocab if r < 0.45 else pseudo if r < 0.7 else numbers if r < 0.82
                                    else latin if r < 0.92 else marks))
        out.append(" ".join(parts) + rnd.choice([".", "!", "?", "", "。", "..."]))
    return out


def _sw_regex_fuzz(n: int, rnd) -> list[str]:
    """Random strings dense in the characters the normalizer passes react to."""
    from vtts.frontend.sw import normalize_sw as nm

    atoms = (list("0123456789") * 4 + list(":/.,-–—~%'+&@#×=() ") * 2 + list(nm.UNITS) + list(nm.CURRENCY)
             + list(nm.ABBREVIATIONS) + list(nm.CONCORDS) + ["/=", "shilingi", "tarehe ", "saa ", "asilimia ", "Sh",
                                                              "…", "...", "¿", "¡", "A", "B", "Z", "ESP", "x", "ab",
                                                              "Ok", "Wi", "é", "ng'", "’", " ", "  ", "\t", "“", "”",
                                                              "«", "»", "SAA ", "Tarehe ", "K", "\u212a", "\u017f"])
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 18))) for _ in range(n)]


def sw_lines(paths: list[Path], limit: int | None, fuzz: int) -> list[str]:
    """mode sw cases: edge cases, the eval sets, the mixed-style sentences (templates x terms_en), the
    tests' strings, corpus sentences (else generated ones), the word lists, number/date/time/money/
    unit cases and regex-dense random strings. Texts for which the Python front-end raises (numbers like
    1.234,5) are left out."""
    import json
    import random

    rnd = random.Random(0)
    root = Path(__file__).parents[2]
    here = root / "scripts" / "data" / "bilingual"
    terms = [t for t in (here / "terms_en.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    temps = [t for t in (here / "templates_sw.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    mixed = [tp.replace("{T}", tm) for tp in temps for tm in terms]
    texts = list(SW_EDGE)
    for name in ("ood_sw.jsonl", "mixed_sw.jsonl"):
        texts += [json.loads(x)["text"] for x in (root / "eval" / "sets" / name).read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    texts += rnd.sample(mixed, min(len(mixed), 2000))
    texts += _lt_tests("sw")
    for p in paths:
        rows = [json.loads(x)["text"] for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
        if limit and len(rows) > limit:
            rows = rnd.sample(rows, limit)
        texts += rows
    texts += _sw_generated(limit or 3000, rnd) if not any(p.exists() for p in paths) else _sw_generated(1000, rnd)
    words = _sw_words()
    texts += [" ".join(words[i:i + 20]) + "." for i in range(0, len(words), 20)]
    pseudo = _sw_pseudo(rnd, 6000)
    texts += [" ".join(pseudo[i:i + 20]) + "." for i in range(0, len(pseudo), 20)]
    nums = []
    for _ in range(2500):
        k = rnd.randint(0, 19)
        v = rnd.choice([rnd.randint(0, 31), rnd.randint(0, 999), rnd.randint(0, 99999), rnd.randint(0, 10**9),
                        rnd.randint(0, 10**15), rnd.randint(0, 10**25)])
        a, b = rnd.randint(0, 60), rnd.randint(0, 40)
        nums.append(["watu {}", "{:,} vitabu", "{}.5%", "$ {}", "wa {}", "-{} km", "{}/{}/2026", "{}-{} kg", "{}:{:02d}",
                     "saa {}:{:02d}", "TSh {:,}", "{}.{:03d}.{:03d}", "KSh {},{:02d}", "{:,}/=", "{} €",
                     "km {}", "{},{}", "+{} {} {}", "{:,}.{} shilingi", "asilimia {}%"][k].format(v, a, b))
    for _ in range(500):
        nums.append(f"{rnd.randint(1900, 2100)}-{rnd.randint(0, 13)}-{rnd.randint(0, 33)} na "
                    f"tarehe {rnd.randint(0, 33)}/{rnd.randint(0, 13)}/{rnd.randint(0, 99):02d} "
                    f"saa {rnd.randint(0, 25)}:{rnd.randint(0, 61):02d}:{rnd.randint(0, 61):02d}")
    texts += nums + _sw_regex_fuzz(fuzz, rnd)
    out, seen = [], set()
    for text in texts:
        text = text.replace("\t", " ").replace("\n", " ")
        if text in seen or any(c in text for c in "\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"):  # line breaks of splitlines()
            continue
        seen.add(text)
        try:
            ids = text_to_ids(text, "sw")
        except (ValueError, KeyError, IndexError):  # Python raises (e.g. int(',') in 1.234,5): not a case
            continue
        out.append(f"sw\t{text}\t" + ";".join(" ".join(map(str, c)) for c in ids))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lt", choices=("es", "id", "pt", "it", "tr", "ms"),
                    help="mode es|id|pt|it|tr|ms (token set es-en|id-en|pt-en|it-en|tr-en|ms-en) cases")
    ap.add_argument("--tl", action="store_true", help="mode tl (token set tl-en) cases")
    ap.add_argument("--sw", action="store_true", help="mode sw (token set sw-en) cases")
    ap.add_argument("--fe", choices=("fi", "el"), help="mode fi|el (token set fi-en|el-en) cases")
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--zh", action="store_true", help="mode zh (token set zh-en) cases")
    ap.add_argument("--ko", action="store_true", help="mode ko (token set ko-en) cases")
    ap.add_argument("--hi", action="store_true", help="mode hi (token set hi-en) cases")
    ap.add_argument("--th", action="store_true", help="mode th (token set th-en) cases")
    ap.add_argument("--nx", choices=("nl", "sv", "no"), help="mode nl|sv|no cases (export_text_parity_nx.py)")
    ap.add_argument("--de", action="store_true", help="mode de (token set de-en) cases")
    ap.add_argument("--ar", action="store_true", help="mode ar (token set ar-en) cases")
    ap.add_argument("--ja", action="store_true", help="mode ja (token set ja-en) cases")
    ap.add_argument("--fr", action="store_true", help="mode fr (token set fr-en) cases")
    ap.add_argument("--nfkc-out", type=Path, default=None, help="--ja: also write the NFKC fixture")
    ap.add_argument("--sentences", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fuzz", type=int, default=3000, help="--zh, --ko, --hi, --ja, --lt, --th: regex-dense random strings")
    a = ap.parse_args()
    if a.nx:
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from export_text_parity_nx import nx_lines

        lines = nx_lines(a.nx, a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.sw:
        lines = sw_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.tl:
        lines = tl_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.fe:
        lines = fe_lines(a.fe, a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.de:
        lines = de_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.fr:
        lines = fr_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.sw:
        lines = sw_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.tl:
        lines = tl_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.lt:
        lines = lt_lines(a.lt, a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if a.ja:
        import random

        lines = ja_lines(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        if a.nfkc_out:
            nl = nfkc_lines(random.Random(1))
            a.nfkc_out.write_text("\n".join(nl) + "\n", encoding="utf-8")
            print(f"wrote {len(nl)} NFKC cases to {a.nfkc_out}")
        return
    if a.zh or a.ko or a.hi or a.th or a.ar:
        lines = (zh_lines if a.zh else ko_lines if a.ko else hi_lines if a.hi else th_lines if a.th
                 else ar_lines)(a.sentences, a.limit, a.fuzz)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    if not a.sentences:
        ap.error("--sentences is required")
    if a.v2:
        lines = v2_lines(a.sentences, a.limit)
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} cases to {a.out}")
        return
    lines = []
    for f in a.sentences:
        for t in f.read_text(encoding="utf-8").splitlines():
            t = t.strip().replace("\t", " ")
            if t and supported(t):
                chunks = text_to_ids(t)
                lines.append(t + "\t" + ";".join(" ".join(map(str, c)) for c in chunks))
    if a.limit:
        lines = lines[: a.limit]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} cases to {a.out}")


if __name__ == "__main__":
    main()
