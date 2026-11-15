"""Build a self-contained A/B listening page (HTML with embedded mp3) from rendered eval sets.

Usage: uv run python scripts/eval/make_listening_page.py --config listening.json --out page.html
config: {"ids": [...], "set": "eval/sets/ood.jsonl",
         "systems": [{"key", "name", "note", "dir", "report"}...]}
"""

import argparse
import base64
import html
import json
import subprocess
import tempfile
from pathlib import Path


def mp3_b64(wav: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "48k",
                        f.name], check=True)
        return base64.b64encode(Path(f.name).read_bytes()).decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg = json.loads(a.config.read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in map(json.loads, Path(cfg["set"]).read_text(encoding="utf-8").splitlines())}
    systems = cfg["systems"]
    metrics = []
    for s in systems:
        rep = json.loads(Path(s["report"]).read_text())
        o = rep.get("ood", rep)
        metrics.append((s, o.get("corpus_cer", o.get("cer")), o.get("mean_utmos", o.get("utmos")),
                        o.get("mean_whistle", o.get("whistle"))))
    body = []
    for sid in cfg["ids"]:
        cells = []
        for s in systems:
            src = mp3_b64(Path(s["dir"]) / f"{sid}.wav")
            cells.append(f'<div class="cell"><span class="sys">{html.escape(s["name"])}</span>'
                         f'<audio controls preload="none" src="data:audio/mpeg;base64,{src}"></audio></div>')
        body.append(f'<section class="sent"><p class="text">{html.escape(rows[sid]["text"])}</p>'
                    f'<p class="group">{html.escape(rows[sid]["group"])}</p><div class="grid">{"".join(cells)}</div></section>')
    table = "".join(
        f"<tr><td>{html.escape(s['name'])}<span class='note'>{html.escape(s['note'])}</span></td>"
        f"<td>{cer:.3f}</td><td>{ut:.2f}</td><td>{wh:.0f}</td></tr>" for s, cer, ut, wh in metrics)
    page = TEMPLATE.replace("{{TABLE}}", table).replace("{{BODY}}", "".join(body))
    a.out.write_text(page, encoding="utf-8")
    print(f"wrote {a.out} ({a.out.stat().st_size // 1024} KB)")


TEMPLATE = """<title>Nghe thử giọng Việt</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* layout: one reading column; each sentence is a block with a grid of players, metrics table on top */
:root { --bg:#f6f7f5; --panel:#ffffff; --fg:#1d2420; --muted:#5f6b64; --line:#dde3de; --accent:#1f7a5a;
  --display:"Be Vietnam Pro", system-ui, sans-serif; --mono:"JetBrains Mono", ui-monospace, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#121714; --panel:#1a211d; --fg:#e4ebe6; --muted:#9aa8a0; --line:#2c3630; --accent:#5cc49b; color-scheme: dark } }
:root[data-theme="dark"] { --bg:#121714; --panel:#1a211d; --fg:#e4ebe6; --muted:#9aa8a0; --line:#2c3630; --accent:#5cc49b; color-scheme: dark }
body { background:var(--bg); color:var(--fg); font-family:var(--display); font-size:15px; line-height:1.55;
  padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); padding-block:24px 48px; }
main { max-width:980px; margin:0 auto; display:flex; flex-direction:column; gap:28px; }
h1 { font-size:1.7rem; margin:0; text-wrap:balance; }
.lead { color:var(--muted); max-width:65ch; margin:6px 0 0; }
.tablewrap { overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--panel); }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th, td { text-align:left; padding:8px 12px; border-bottom:1px solid var(--line); }
th { font-size:.75rem; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); font-weight:600; }
td:not(:first-child), th:not(:first-child) { font-family:var(--mono); text-align:right; }
tr:last-child td { border-bottom:none; }
.note { display:block; color:var(--muted); font-size:.8rem; }
.sent { display:flex; flex-direction:column; gap:10px; padding-block:18px; border-top:1px solid var(--line); }
.text { font-size:1.15rem; font-weight:600; margin:0; text-wrap:balance; }
.group { margin:0; font-family:var(--mono); font-size:.75rem; color:var(--accent); letter-spacing:.06em; text-transform:uppercase; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:10px; }
.cell { display:flex; flex-direction:column; gap:4px; background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px; min-width:0; }
.sys { font-size:.85rem; font-weight:600; }
audio { width:100%; }
</style>
<main>
<header>
<h1>Nghe thử giọng đọc tiếng Việt</h1>
<p class="lead">Cùng một câu, các hệ thống khác nhau. Student là model nhỏ sẽ chạy trên ESP32-P4; audio của student được tạo bằng chính runtime C int8 dùng trên chip. CER: tỉ lệ lỗi ký tự khi ASR (PhoWhisper-large) nghe lại, thấp là tốt. UTMOS: dự đoán độ tự nhiên, cao là tốt. Rít: mật độ tiếng rít, thấp là tốt. Số đo trên 50 câu ngoài miền.</p>
</header>
<div class="tablewrap"><table><thead><tr><th>Hệ thống</th><th>CER</th><th>UTMOS</th><th>Rít</th></tr></thead><tbody>{{TABLE}}</tbody></table></div>
{{BODY}}
</main>
"""

if __name__ == "__main__":
    main()
