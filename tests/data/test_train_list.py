import json

import pytest

from vtts.data.train_list import Source, build_rows, parse_source


def _run(tmp_path, name, items, statuses=None, missing=()):
    """sentences.jsonl + synth dir with manifest and (empty) audio files."""
    d = tmp_path / name
    (d / "synth" / "audio").mkdir(parents=True)
    (d / "sentences.jsonl").write_text(
        "".join(json.dumps({"id": i, "text": t, "lang": lang}, ensure_ascii=False) + "\n"
                for i, t, lang, _ in items), encoding="utf-8")
    man = []
    for i, _, _, dur in items:
        st = (statuses or {}).get(i, "ok")
        man.append(json.dumps({"id": i, "status": st, "dur": dur}))
        if i not in missing:
            (d / "synth" / "audio" / f"{i}.flac").write_bytes(b"")
    (d / "synth" / "manifest.jsonl").write_text("\n".join(man) + "\n")
    return d / "sentences.jsonl", d / "synth"


def test_parse_source():
    s = parse_source("sentences=a/s.jsonl,synth=a/synth,only=en,hours=35")
    assert s.sentences.as_posix() == "a/s.jsonl" and s.synth.as_posix() == "a/synth"
    assert s.only == "en" and s.hours == 35 and s.lang is None
    with pytest.raises(ValueError):
        parse_source("sentences=a.jsonl")  # synth missing
    with pytest.raises(ValueError):
        parse_source("sentences=a.jsonl,synth=b,colour=red")


def test_rows_from_several_sources_with_audio_paths(tmp_path):
    zs, zsyn = _run(tmp_path, "zh", [("zh0", "今天天气很好。", "zh", 2.0),
                                     ("zh1", "打开灯。", "zh", 1.0)],
                    statuses={"zh1": "failed"})
    bs, bsyn = _run(tmp_path, "bi", [("en0", "Hello there.", "en", 1.5),
                                     ("vi0", "Xin chào.", "vi", 1.0)])
    rows = build_rows([Source(zs, zsyn), Source(bs, bsyn, only="en")], root=tmp_path)
    assert rows == [
        "zh0|今天天气很好。|2.000|zh|zh/synth/audio/zh0.flac",
        "en0|Hello there.|1.500|en|bi/synth/audio/en0.flac",
    ]


def test_missing_audio_unreadable_and_pipe_rows_left_out(tmp_path):
    s, syn = _run(tmp_path, "zh", [("a", "你好。", "zh", 1.0), ("b", "我龘好。", "zh", 1.0),
                                   ("c", "a|b", "zh", 1.0), ("d", "好的。", "zh", 1.0)],
                  missing={"d"})
    assert [r.split("|")[0] for r in build_rows([Source(s, syn)], root=tmp_path)] == ["a"]


def test_unreadable_per_pair_language():
    from vtts.data.train_list import unreadable

    assert unreadable("我龘好。", "zh") and not unreadable("你好。", "zh")
    assert unreadable("Hola Москва.", "es") and not unreadable("¿Qué tal, François?", "es")
    assert unreadable("Halo Москва.", "id") and not unreadable("Apa kabar, Kafé?", "id")
    assert unreadable("Olá Москва.", "pt") and not unreadable("Olá, tudo bem? François", "pt")
    assert not unreadable("Москва", "vi")  # languages without a check keep every row


def test_lang_override_and_absolute_path_outside_root(tmp_path):
    s, syn = _run(tmp_path, "x", [("a", "Hello.", "vi", 1.0)])
    other_root = tmp_path / "elsewhere"
    other_root.mkdir()
    (row,) = build_rows([Source(s, syn, lang="en")], root=other_root)
    _, _, _, lang, audio = row.split("|")
    assert lang == "en" and audio == str((syn / "audio" / "a.flac").resolve())


def test_hours_cap_is_a_seeded_subset(tmp_path):
    items = [(f"zh{i:03d}", "你好。", "zh", 60.0) for i in range(100)]
    s, syn = _run(tmp_path, "zh", items)
    rows = build_rows([Source(s, syn, hours=0.5)], root=tmp_path)
    assert len(rows) == 30  # 30 x 60 s
    assert rows == build_rows([Source(s, syn, hours=0.5)], root=tmp_path)
    ids = [r.split("|")[0] for r in rows]
    assert ids == sorted(ids) and ids != [f"zh{i:03d}" for i in range(30)]


def test_duplicate_ids_across_sources_rejected(tmp_path):
    s1, syn1 = _run(tmp_path, "a", [("x", "Hello.", "en", 1.0)])
    s2, syn2 = _run(tmp_path, "b", [("x", "Hi.", "en", 1.0)])
    with pytest.raises(ValueError, match="duplicate"):
        build_rows([Source(s1, syn1), Source(s2, syn2)], root=tmp_path)


def test_source_from_an_existing_train_csv(tmp_path):
    """A run whose manifest is gone: texts and durations come from its synth_to_csv list."""
    syn = tmp_path / "bi" / "synth"
    (syn / "audio").mkdir(parents=True)
    for uid in ("en0", "en1", "vi0"):
        (syn / "audio" / f"{uid}.flac").write_bytes(b"")
    csv = tmp_path / "bi" / "train.csv"
    csv.write_text("vi0|Xin chào.|1.000|vi\nen1|Good night.|2.000|en\nen0|Hello.|1.500|en\n"
                   "en9|No audio.|1.0|en\n", encoding="utf-8")
    s = parse_source(f"csv={csv},synth={syn},only=en")
    assert s.csv == csv and s.sentences is None
    assert build_rows([s], root=tmp_path) == ["en0|Hello.|1.500|en|bi/synth/audio/en0.flac",
                                              "en1|Good night.|2.000|en|bi/synth/audio/en1.flac"]
    with pytest.raises(ValueError):
        parse_source(f"csv={csv},sentences=a.jsonl,synth={syn}")
