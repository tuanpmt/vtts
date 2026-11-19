import numpy as np
import torch

from vtts.teacher.config import TeacherConfig
from vtts.teacher.infer import Teacher
from vtts.teacher.model import build_generator

TINY = {"inter_channels": 32, "hidden_channels": 32, "filter_channels": 64, "n_layers": 2,
        "upsample_initial_channel": 32}


def _ckpt(tmp_path):
    cfg = TeacherConfig(**TINY)
    path = tmp_path / "ckpt_0000001.pt"
    torch.save({"g": build_generator(cfg).state_dict(), "config": cfg.__dict__, "step": 1}, path)
    return path


def test_synthesize_deterministic(tmp_path):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    a, b = t.synthesize("xin chào"), t.synthesize("xin chào")
    assert a.dtype == np.float32 and len(a) > 0
    assert np.array_equal(a, b)


def test_synthesize_multi_chunk(tmp_path):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    one = t.synthesize("xin chào bạn.")
    three = t.synthesize("xin chào bạn. hôm nay trời đẹp. cảm ơn nhiều.")
    assert len(three) > len(one)


def test_empty_text_gives_empty_audio(tmp_path):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    assert len(t.synthesize("...")) == 0


def test_synthesize_bilingual_uses_v2_ids(tmp_path, monkeypatch):
    t = Teacher.load(_ckpt(tmp_path), "cpu")
    seen = []
    monkeypatch.setattr(t, "synthesize_ids", lambda ids: seen.append(ids) or np.zeros(10, np.float32))
    t.synthesize("Bật Bluetooth nhé. Play some music.", lang="mixed")
    from vtts.frontend.text import text_to_ids
    assert seen == text_to_ids("Bật Bluetooth nhé. Play some music.", "vi")  # mixed is read in vi mode
    seen.clear()
    t.synthesize("Play some music.", lang="en")
    assert seen == text_to_ids("Play some music.", "en")


def test_synthesize_pair_languages_use_pair_token_sets(tmp_path, monkeypatch):
    from vtts.frontend.text import text_to_ids
    from vtts.teacher.data import encode_text

    t = Teacher.load(_ckpt(tmp_path), "cpu")
    seen = []
    monkeypatch.setattr(t, "synthesize_ids", lambda ids: seen.append(ids) or np.zeros(10, np.float32))
    for lang, text in [("zh", "打开Wi-Fi设置。"), ("ko", "Wi-Fi를 켜 주세요."), ("ja", "Wi-Fiを設定してください。"),
                       ("es", "Abre GitHub, por favor."), ("pt", "Abra o GitHub, por favor."), ("hi", "कृपया GitHub खोलो।"), ("th", "ช่วยเปิด GitHub ให้หน่อย"), ("id", "Tolong buka GitHub, ya."),
                       ("fr", "Ouvre GitHub, s'il te plaît."), ("de", "Öffne bitte GitHub."),
                       ("it", "Apri GitHub, per favore."), ("tr", "GitHub'ı aç, lütfen."),
                       ("ru", "Открой GitHub, пожалуйста."), ("pl", "Otwórz GitHub, proszę."),
                       ("ar", "افتح GitHub من فضلك."),
                       ("fi", "Avaa GitHub, kiitos."), ("el", "Άνοιξε το GitHub;"),
                       ("ms", "Tolong buka GitHub, ya."), ("tl", "Pakibuksan ang GitHub."), ("sw", "Tafadhali fungua GitHub."),
                       ("nl", "Open GitHub, alsjeblieft."), ("sv", "Öppna GitHub, tack."), ("no", "Åpne GitHub, takk.")]:
        seen.clear()
        t.synthesize(text, lang=lang)
        assert seen == text_to_ids(text, lang) == [encode_text(text, lang)]  # as in training
