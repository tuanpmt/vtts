"""README.md, docs/voices.md, docs/architecture.md, the firmware README and docs/index.html share generated
blocks with docs/site.json."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sync_docs", ROOT / "scripts/docs/sync_docs.py")
sync_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_docs)

EXPECTED = {
    "README.md": {"released"},
    "docs/voices.md": {"voices", "hardware", "samples"},
    "docs/architecture.md": {"tech"},
    "firmware/esp32/README.md": {"boards"},
    "docs/index.html": {"boards", "tech"},
}


def test_every_target_has_its_blocks():
    for rel, names in EXPECTED.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        found = set(re.findall(r"<!-- BEGIN:(\w+) -->", text))
        assert found == names, f"{rel}: {sorted(found)}"
        for n in names:
            assert f"<!-- END:{n} -->" in text, f"{rel}: END:{n} missing"


def test_generated_blocks_match_site_json():
    stale = sync_docs.sync(write=False)
    assert stale == [], f"run: uv run python scripts/docs/sync_docs.py  (stale: {stale})"


def test_replace_blocks_keeps_text_outside_markers():
    text = "intro\n<!-- BEGIN:x -->\nold\n<!-- END:x -->\noutro"
    assert sync_docs.replace_blocks(text, lambda n: "new " + n) == "intro\n<!-- BEGIN:x -->\nnew x\n<!-- END:x -->\noutro"


def test_html_escapes_text():
    assert sync_docs.h_inline("a < b `c` **d**") == "a &lt; b <code>c</code> <b>d</b>"


def test_listen_models_reference_known_audio():
    import json
    site = json.loads((ROOT / "docs/site.json").read_text(encoding="utf-8"))
    for tab in site["listen"]:
        ids = {m["id"] for m in tab["models"]}
        for s in tab["samples"]:
            assert set(s.get("audio", {})) <= ids, (tab["id"], s["text"])
            for src in s.get("audio", {}).values():
                assert (ROOT / "docs" / src).is_file(), src


def test_released_voices_point_to_listen_models():
    import json
    site = json.loads((ROOT / "docs/site.json").read_text(encoding="utf-8"))
    models = {m["id"] for tab in site["listen"] for m in tab["models"]}
    for v in site["voices"]:
        assert not any(k.endswith("_vi") for k in v), v["name"]
        if v["status"] == "released":
            assert set(v["models"]) <= models and v["release"].startswith("v") and v["pair"] and v["hf"], v["name"]
    assert not (ROOT / "README.vi.md").exists()
