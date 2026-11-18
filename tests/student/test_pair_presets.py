import json

from vtts.frontend.phoneme_set import PAIR_MODES, TOKEN_SETS
from vtts.student.config import PRESETS
from vtts.student.distill_data import pack_inputs


def test_pair_presets_cover_their_token_sets():
    assert {"zh-en", "ko-en", "ja-en", "es-en", "id-en"} <= set(PAIR_MODES.values())
    for pair in PAIR_MODES.values():
        size = len(TOKEN_SETS[pair])
        for base in ("M-vocos-p", "S-vocos-p"):
            assert PRESETS[f"{base}-{pair}"].vocab == size
        assert PRESETS[f"M-vocos-p-{pair}-s3"].v_mult == 2


def test_pack_inputs_uses_the_pair_token_set(tmp_path):
    rows = [{"text": "今天天气很好。", "lang": "zh"}, {"text": "Turn on the light.", "lang": "en"},
            {"text": "오늘 날씨가 좋아요.", "lang": "ko"}, {"text": "今日はいい天気です。", "lang": "ja"},
            {"text": "Hoy hace buen tiempo.", "lang": "es"}, {"text": "Hari ini cuacanya cerah.", "lang": "id"}]
    p = tmp_path / "s.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    packs = pack_inputs(p, None)
    assert len(packs) == len(rows)
    for r, ids in zip(rows, packs, strict=True):
        if r["lang"] == "en":
            assert max(ids) <= 106  # English uses the shared ids in every pair
        else:  # language block above the shared ids, inside the pair's token set
            assert 106 < max(ids) < len(TOKEN_SETS[PAIR_MODES[r["lang"]]])
