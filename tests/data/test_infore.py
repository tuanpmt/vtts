import io

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import soundfile as sf

from vtts.data.infore import prepare_infore


def _wav_bytes(seconds=1.5, sr=44100):
    t = np.arange(int(sr * seconds)) / sr
    buf = io.BytesIO()
    sf.write(buf, 0.3 * np.sin(2 * np.pi * 220 * t), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_prepare_infore_tiny(tmp_path):
    raw = tmp_path / "raw" / "data"
    raw.mkdir(parents=True)
    audio = [{"bytes": _wav_bytes(), "path": f"{i}.wav"} for i in range(3)]
    table = pa.table({"audio": audio, "transcription": ["xin chào", "", "tạm biệt"]})
    pq.write_table(table, raw / "train-00000-of-00001.parquet")

    out = tmp_path / "prepared"
    report = prepare_infore(tmp_path / "raw", out)

    assert report.n_in == 3 and report.n_out == 2
    assert report.skipped == [(1, "empty_transcript")]
    lines = (out / "metadata.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[0].startswith("infore_00000|xin chào|")
    x, sr = sf.read(out / "wavs" / "infore_00002.wav")
    assert sr == 22050 and len(x) > 0


def test_prepare_infore_corrupt_audio(tmp_path):
    raw = tmp_path / "raw" / "data"
    raw.mkdir(parents=True)
    audio = [{"bytes": b"not a wav", "path": "0.wav"}, {"bytes": _wav_bytes(), "path": "1.wav"}]
    pq.write_table(pa.table({"audio": audio, "transcription": ["a", "b"]}), raw / "t.parquet")
    report = prepare_infore(tmp_path / "raw", tmp_path / "out")
    assert report.n_out == 1 and report.skipped == [(0, "bad_audio")]
