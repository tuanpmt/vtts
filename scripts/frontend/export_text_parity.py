"""Write the C front-end parity fixture: sentences the device front-end supports + expected ids.

Usage: uv run python scripts/frontend/export_text_parity.py --sentences FILE... --out runtime/test/text_parity.tsv
       uv run python scripts/frontend/export_text_parity.py --v2 --sentences data/bilingual/sentences.jsonl \
           eval/sets/*.jsonl --out runtime/test/text_parity_v2.tsv
       uv run python scripts/frontend/export_text_parity.py --zh --sentences data/zh/sentences.jsonl \
           --limit 3000 --out runtime/test/text_parity_zh.tsv
--v2 writes "mode<TAB>text<TAB>ids" lines (phoneme set v2) for vi, en and auto mode; --zh writes the
same format for mode zh (token set zh-en). Without data/zh/sentences.jsonl, --zh generates Chinese
sentences from the reading tables.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--zh", action="store_true", help="mode zh (token set zh-en) cases")
    ap.add_argument("--sentences", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fuzz", type=int, default=3000, help="--zh: regex-dense random strings")
    a = ap.parse_args()
    if a.zh:
        lines = zh_lines(a.sentences, a.limit, a.fuzz)
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
