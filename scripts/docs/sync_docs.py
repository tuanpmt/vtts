"""Regenerate the content shared by the READMEs and the website from docs/site.json.

Generated blocks sit between `<!-- BEGIN:name -->` and `<!-- END:name -->` markers in README.md
(English Markdown), README.vi.md (Vietnamese Markdown) and docs/index.html (English HTML).
Text outside the markers is never touched, so prose stays hand-written.

Usage: uv run python scripts/docs/sync_docs.py [--check]
--check exits with status 1 if a file is out of date (tests/docs/test_docs_sync.py runs it).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EMOJI = {"vi": "🇻🇳", "en": "🇺🇸", "zh": "🇨🇳"}
LANG_NAME = {"vi": "Vietnamese", "en": "English", "zh": "Chinese"}
RAW = "https://raw.githubusercontent.com/tuanpmt/vtts/main/docs/"

T = {
    "en": {
        "voices_head": ["Voice", "Languages", "Quality model (M)", "Lite model (S)", "Status"],
        "cs": "code-switching",
        "hw_head": ["Board", "Chip", "Lite model RTF", "Quality model RTF"],
        "hw_note": "Both models run on both chips. RTF below 1 means faster than real time.",
        "boards_head": ["`BOARD=`", "Board", "Speaker path", "Default volume"],
        "default": " (default)",
        "sentence": "Sentence",
    },
    "vi": {
        "voices_head": ["Giọng", "Ngôn ngữ", "Model chất lượng (M)", "Model nhẹ (S)", "Trạng thái"],
        "cs": "đọc câu trộn",
        "hw_head": ["Board", "Chip", "RTF model nhẹ", "RTF model chất lượng"],
        "hw_note": "Cả hai model đều chạy trên cả hai chip. RTF dưới 1 nghĩa là nhanh hơn thời gian thực.",
        "boards_head": ["`BOARD=`", "Board", "Loa", "Âm lượng mặc định"],
        "default": " (mặc định)",
        "sentence": "Câu",
    },
}


def pick(d: dict, key: str, lang: str) -> str:
    return d.get(f"{key}_vi", d[key]) if lang == "vi" else d[key]


# ---------- Markdown (READMEs) ----------

def md_table(head: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def md_langs(v: dict, lang: str) -> str:
    s = " + ".join(f"{EMOJI[c]} {c}" for c in v["langs"])
    return s + (f", {T[lang]['cs']}" if v.get("code_switching") else "")


def md_voices(site: dict, samples: dict, lang: str) -> str:
    rows = []
    for v in site["voices"]:
        status = pick(v, "status_text", lang)
        if v["status"] != "planned":
            status = f"**{status}**"
        rows.append([pick(v, "name", lang), md_langs(v, lang), pick(v, "quality", lang), pick(v, "lite", lang), status])
    return md_table(T[lang]["voices_head"], rows)


def md_hardware(site: dict, samples: dict, lang: str) -> str:
    rows = [[h["boards"], h["chip"], h["rtf_lite"], h["rtf_quality"]] for h in site["hardware"]]
    return md_table(T[lang]["hw_head"], rows) + "\n\n" + T[lang]["hw_note"]


def md_boards(site: dict, samples: dict, lang: str) -> str:
    rows = [[f"`{b['id']}`" + (T[lang]["default"] if b.get("default") else ""), b["name"], b["speaker"], b["volume"]]
            for b in site["boards"]]
    return md_table(T[lang]["boards_head"], rows)


def md_tech(site: dict, samples: dict, lang: str) -> str:
    pipe = " → ".join(site["pipeline"])
    items = [f"- **{pick(t, 'title', lang)}:** {pick(t, 'text', lang)}" for t in site["tech"]]
    return f"`{pipe}`\n\n" + "\n".join(items)


def md_samples(site: dict, samples: dict, lang: str) -> str:
    out = []
    for tab in site["listen"]:
        if not any(s.get("audio") for s in tab["samples"]):
            continue
        rows = []
        for s in tab["samples"]:
            cells = [f"[▶ {m['name']}]({RAW}{s['audio'][m['id']]})" if s.get("audio", {}).get(m["id"]) else "—"
                     for m in tab["models"]]
            rows.append([pick(s, "text", lang), *cells])
        flags = " ".join(EMOJI[f] for f in tab["flags"])
        out += [f"{flags} **{tab['label']}**", "", md_table([T[lang]["sentence"], *(m["name"] for m in tab["models"])], rows), ""]
    return "\n".join(out).rstrip()


MD = {"voices": md_voices, "hardware": md_hardware, "boards": md_boards, "tech": md_tech, "samples": md_samples}


# ---------- HTML (docs/index.html, English) ----------

def h_inline(s: str) -> str:
    """Escape, then render the two Markdown marks site.json uses: `code` and **bold**."""
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def h_flag(c: str) -> str:
    return f'<svg class="flag" role="img" aria-label="{LANG_NAME[c]}"><use href="#flag-{c}"/></svg> {c}'


def h_table(head: list[tuple[str, str]], rows: list[list[tuple[str, str]]]) -> str:
    """head/rows are (html, css class) pairs."""
    def cell(tag: str, c: tuple[str, str]) -> str:
        return f'<{tag} class="{c[1]}">{c[0]}</{tag}>' if c[1] else f"<{tag}>{c[0]}</{tag}>"
    th = "".join(cell("th", c) for c in head)
    body = "\n".join("      <tr>" + "".join(cell("td", c) for c in r) + "</tr>" for r in rows)
    return (f'<div class="tablewrap">\n  <table>\n    <thead><tr>{th}</tr></thead>\n    <tbody>\n{body}\n'
            f"    </tbody>\n  </table>\n</div>")


STATUS_TAG = {"released": "tag ok", "training": "tag", "planned": "tag plan"}


def h_voices(site: dict, samples: dict) -> str:
    head = [(h, "") for h in ["Voice", "Languages", "Quality (M)", "Lite (S)", "Status"]]
    rows = []
    for v in site["voices"]:
        langs = " + ".join(h_flag(c) for c in v["langs"])
        rows.append([(h_inline(v["name"]), ""), (langs, "wrap"), (h_inline(v["quality"]), "wrap"), (h_inline(v["lite"]), "wrap"),
                     (f'<span class="{STATUS_TAG[v["status"]]}">{v["status"]}</span>', "")])
    return h_table(head, rows)


def h_hardware(site: dict, samples: dict) -> str:
    head = [("Board", ""), ("Chip", ""), ("RTF lite", "num"), ("RTF quality", "num")]
    rows = [[(h_inline(h["boards"]), "wrap"), (h_inline(h["chip"]), "wrap"), (h["rtf_lite"], "num"), (h["rtf_quality"], "num")] for h in site["hardware"]]
    return h_table(head, rows) + f'\n<p class="muted">{h_inline(T["en"]["hw_note"])}</p>'


def h_boards(site: dict, samples: dict) -> str:
    head = [(h, "") for h in ["BOARD=", "Board", "Speaker path", "Default volume"]]
    rows = [[(f"<code>{b['id']}</code>", ""), (h_inline(b["name"]), ""), (b["speaker"], ""), (h_inline(b["volume"]), "")]
            for b in site["boards"]]
    return h_table(head, rows)


def h_tech(site: dict, samples: dict) -> str:
    steps = "\n".join(f"  <li>{h_inline(s)}</li>" for s in site["pipeline"])
    cards = "\n".join(f'  <div class="card"><h3>{h_inline(t["title"])}</h3><p>{h_inline(t["text"])}</p></div>'
                      for t in site["tech"])
    return f'<ol class="pipeline">\n{steps}\n</ol>\n<div class="cards">\n{cards}\n</div>'


HTML = {"voices": h_voices, "hardware": h_hardware, "boards": h_boards, "tech": h_tech}


# ---------- driver ----------

def replace_blocks(text: str, make) -> str:
    def sub(m: re.Match) -> str:
        return f"<!-- BEGIN:{m.group(1)} -->\n{make(m.group(1))}\n<!-- END:{m.group(1)} -->"
    return re.sub(r"<!-- BEGIN:(\w+) -->.*?<!-- END:\1 -->", sub, text, flags=re.DOTALL)


def targets(site: dict, samples: dict) -> list[tuple[str, callable]]:
    return [
        ("README.md", lambda n: MD[n](site, samples, "en")),
        ("README.vi.md", lambda n: MD[n](site, samples, "vi")),
        ("docs/index.html", lambda n: HTML[n](site, samples)),
    ]


def sync(root: Path = ROOT, write: bool = True) -> list[str]:
    """Return the files that were (or, with write=False, would be) changed."""
    site = json.loads((root / "docs/site.json").read_text(encoding="utf-8"))
    samples = site["listen"]
    stale = []
    for rel, make in targets(site, samples):
        p = root / rel
        old = p.read_text(encoding="utf-8")
        new = replace_blocks(old, make)
        if new != old:
            stale.append(rel)
            if write:
                p.write_text(new, encoding="utf-8")
    return stale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report stale files without writing")
    a = ap.parse_args()
    stale = sync(write=not a.check)
    if a.check and stale:
        print("out of date: " + ", ".join(stale) + " (run scripts/docs/sync_docs.py)")
        return 1
    print(("updated: " + ", ".join(stale)) if stale else "all files are in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
