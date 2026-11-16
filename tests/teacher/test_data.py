import numpy as np
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
