import numpy as np
import pytest
import soundfile as sf
import torch

from vtts.frontend.phoneme_set import VOCAB_SIZE
from vtts.teacher.config import TeacherConfig
from vtts.teacher.data import BucketSampler, TeacherDataset, collate


def _make(tmp_path, items, cache="cache"):
    wavs = tmp_path / "wavs"
    wavs.mkdir()
    lines = []
    for uid, text, sec in items:
        t = np.arange(int(22050 * sec)) / 22050
        sf.write(wavs / f"{uid}.wav", 0.3 * np.sin(2 * np.pi * 220 * t), 22050, subtype="PCM_16")
        lines.append(f"{uid}|{text}|{sec}")
    (tmp_path / "train.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TeacherDataset(tmp_path / "train.csv", wavs, cache and tmp_path / cache, TeacherConfig())


def test_item_shapes(tmp_path):
    ds = _make(tmp_path, [("a", "Xin chào Việt Nam.", 1.2)])
    item = ds[0]
    assert item["spec"].shape[0] == 513
    assert item["spec"].shape[1] * 256 == item["wav"].shape[1]
    assert int(item["ids"].max()) < VOCAB_SIZE and item["ids"][0] == 1 and item["ids"][-1] == 2


def test_cache_reused(tmp_path):
    ds = _make(tmp_path, [("a", "xin chào", 1.0)])
    ds[0]
    cached = tmp_path / "cache" / "a.spec.pt"
    mtime = cached.stat().st_mtime_ns
    ds[0]
    assert cached.stat().st_mtime_ns == mtime


def test_no_cache_writes_nothing(tmp_path):
    ds = _make(tmp_path, [("a", "xin chào", 1.0)], cache=None)
    item = ds[0]
    assert item["spec"].shape[0] == 513
    assert sorted(p.name for p in tmp_path.iterdir()) == ["train.csv", "wavs"]


def test_collate_pads_short_audio(tmp_path):
    ds = _make(tmp_path, [("a", "có", 0.2), ("b", "xin chào bạn", 1.0)])
    batch = collate([ds[0], ds[1]], segment_frames=32)
    assert batch["spec"].shape[2] >= 32
    assert batch["wav"].shape[2] == batch["spec"].shape[2] * 256
    assert batch["spec_lengths"].tolist()[0] < 32  # true length kept
    assert batch["ids"].shape[0] == 2 and batch["ids_lengths"].dtype == torch.long


def test_bucket_sampler_covers_all_once():
    lengths = list(range(10, 110))
    s = BucketSampler(lengths, batch_size=8, n_buckets=5, seed=1)
    batches = list(s)
    flat = sorted(i for b in batches for i in b)
    assert flat == list(range(100))
    s.set_epoch(1)
    assert list(s) != batches


def test_bilingual_rows_and_flac_resampled(tmp_path):
    wavs = tmp_path / "wavs"
    wavs.mkdir()
    t = np.arange(24000) / 24000
    sf.write(wavs / "en1.flac", 0.3 * np.sin(2 * np.pi * 220 * t), 24000, subtype="PCM_16")
    sf.write(wavs / "vi1.flac", 0.3 * np.sin(2 * np.pi * 220 * t), 24000, subtype="PCM_16")
    (tmp_path / "train.csv").write_text("en1|Hello world.|1.0|en\nvi1|Xin chào.|1.0|vi\n", encoding="utf-8")
    ds = TeacherDataset(tmp_path / "train.csv", wavs, None, TeacherConfig())
    en, vi = ds[0], ds[1]
    assert int(en["ids"].max()) >= 65 and int(en["ids"].max()) < 107
    assert int(vi["ids"].max()) < 65
    assert abs(en["wav"].shape[1] - 22050) <= 256


def test_bucket_sampler_frame_budget():
    lengths = [100] * 40 + [1000] * 40
    s = BucketSampler(lengths, batch_size=16, n_buckets=2, seed=0, max_frames=4000)
    batches = list(s)
    assert sorted(i for b in batches for i in b) == list(range(80))
    assert all(len(b) * max(lengths[i] for i in b) <= 4000 for b in batches)
    assert max(len(b) for b in batches) == 16  # short items still fill whole batches


def test_encode_text_zh_uses_zhen_ids_and_english_rows_match():
    from vtts.frontend.phoneme_set import VOCAB_SIZE_V2, VOCAB_SIZE_ZHEN
    from vtts.frontend.text import text_to_ids
    from vtts.teacher.data import encode_text

    zh = encode_text("打开Wi-Fi设置。", "zh")
    assert max(zh) >= VOCAB_SIZE_V2 and max(zh) < VOCAB_SIZE_ZHEN
    assert zh == text_to_ids("打开Wi-Fi设置。", "zh")[0]
    en = "Turn on the light, please."
    assert encode_text(en, "en") == text_to_ids(en, "zh")[0] == text_to_ids(en, "en")[0]


def test_encode_text_ko_uses_koen_ids_and_english_rows_match():
    from vtts.frontend.phoneme_set import VOCAB_SIZE_KOEN, VOCAB_SIZE_V2
    from vtts.frontend.text import text_to_ids
    from vtts.teacher.data import encode_text

    ko = encode_text("Wi-Fi를 켜 주세요.", "ko")
    assert max(ko) >= VOCAB_SIZE_V2 and max(ko) < VOCAB_SIZE_KOEN
    assert ko == text_to_ids("Wi-Fi를 켜 주세요.", "ko")[0]
    en = "Turn on the light, please."
    assert encode_text(en, "en") == text_to_ids(en, "ko")[0] == text_to_ids(en, "en")[0]


def test_encode_text_ja_uses_jaen_ids_and_english_rows_match():
    from vtts.frontend.phoneme_set import VOCAB_SIZE_JAEN, VOCAB_SIZE_V2
    from vtts.frontend.text import text_to_ids
    from vtts.teacher.data import encode_text

    ja = encode_text("Wi-Fiを設定してください。", "ja")
    assert max(ja) >= VOCAB_SIZE_V2 and max(ja) < VOCAB_SIZE_JAEN
    assert ja == text_to_ids("Wi-Fiを設定してください。", "ja")[0]
    en = "Turn on the light, please."
    assert encode_text(en, "en") == text_to_ids(en, "ja")[0] == text_to_ids(en, "en")[0]


WORD_PAIR_ROWS = [("nl", "nl-en", "Open GitHub en zet muziek aan, alsjeblieft."), ("no", "no-en", "Åpne GitHub og sett på musikk, takk."), ("sv", "sv-en", "Öppna GitHub och sätt på musik, tack."), ("sw", "sw-en", "Tafadhali fungua GitHub."), ("tl", "tl-en", "Pakibuksan ang GitHub, salamat."), ("ms", "ms-en", "Tolong buka GitHub, ya."), ("el", "el-en", "Άνοιξε το GitHub, παρακαλώ."), ("fi", "fi-en", "Avaa GitHub, kiitos."), ("ar", "ar-en", "افتح GitHub من فضلك."), ("pl", "pl-en", "Otwórz GitHub, proszę."), ("ru", "ru-en", "Открой GitHub, пожалуйста."), ("tr", "tr-en", "GitHub'ı aç, lütfen."), ("it", "it-en", "Apri GitHub, per favore."), ("hi", "hi-en", "कृपया GitHub खोलो।"), ("th", "th-en", "ช่วยเปิด GitHub ให้หน่อยนะ"), ("pt", "pt-en", "Abra o GitHub, por favor."), ("id", "id-en", "Tolong buka GitHub, ya."), ("es", "es-en", "Abre GitHub y pon música, por favor."), ("de", "de-en", "Öffne bitte GitHub.")]


@pytest.mark.parametrize("lang, token_set, text", WORD_PAIR_ROWS)
def test_encode_text_word_pairs_use_their_token_set(lang, token_set, text):
    from vtts.frontend.phoneme_set import TOKEN_SETS, VOCAB_SIZE_V2
    from vtts.frontend.text import text_to_ids
    from vtts.teacher.data import encode_text

    ids = encode_text(text, lang)
    assert max(ids) >= VOCAB_SIZE_V2 and max(ids) < len(TOKEN_SETS[token_set])
    assert ids == text_to_ids(text, lang)[0]
    en = ("Close the door, please." if lang == "tr"  # tr: on (ten), turn fit Turkish
          else "Thank you, see you soon." if lang == "pl"  # on, to: Polish
          else "Turn on the light, please.")
    assert encode_text(en, "en") == text_to_ids(en, lang)[0] == text_to_ids(en, "en")[0]


def test_encode_text_french_uses_fr_en():
    """fr-en like the word pairs above ("on" is a French word, so the English sentence has none)."""
    from vtts.frontend.phoneme_set import TOKEN_SETS, VOCAB_SIZE_V2
    from vtts.frontend.text import text_to_ids
    from vtts.teacher.data import encode_text

    text = "Ouvre GitHub et mets de la musique, s'il te plaît."
    ids = encode_text(text, "fr")
    assert VOCAB_SIZE_V2 <= max(ids) < len(TOKEN_SETS["fr-en"])
    assert ids == text_to_ids(text, "fr")[0]
    en = "Please check the light."
    assert encode_text(en, "en") == text_to_ids(en, "fr")[0] == text_to_ids(en, "en")[0]


def test_audio_path_column_relative_absolute_and_old_rows(tmp_path):
    """A fifth column names the audio file (relative to wav_dir or absolute); 3- and 4-column rows
    still read WAVS/<uid>.wav|.flac."""
    root = tmp_path / "data"
    for sub in ("zh/synth/audio", "bi/synth/audio", "wavs"):
        (root / sub).mkdir(parents=True)
    t = np.arange(24000) / 24000
    tone = 0.3 * np.sin(2 * np.pi * 220 * t)
    sf.write(root / "zh/synth/audio/zh1.flac", tone, 24000, subtype="PCM_16")
    sf.write(root / "bi/synth/audio/en1.flac", tone[:12000], 24000, subtype="PCM_16")
    sf.write(root / "old1.wav", tone, 24000, subtype="PCM_16")
    absolute = (root / "bi/synth/audio/en1.flac").resolve()
    (tmp_path / "train.csv").write_text(
        "zh1|打开灯。|1.0|zh|zh/synth/audio/zh1.flac\n"
        f"en1|Hello.|0.5|en|{absolute}\n"
        "old1|Xin chào.|1.0|vi\n", encoding="utf-8")
    ds = TeacherDataset(tmp_path / "train.csv", root, None, TeacherConfig())
    assert ds.frame_lengths() == [86, 43, 86]
    zh, en, old = ds[0], ds[1], ds[2]
    assert abs(zh["wav"].shape[1] - 22050) <= 256 and abs(en["wav"].shape[1] - 11025) <= 256
    assert abs(old["wav"].shape[1] - 22050) <= 256
