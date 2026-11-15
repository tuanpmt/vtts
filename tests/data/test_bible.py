import io
import zipfile

import numpy as np
import soundfile as sf

from vtts.data.bible import clean_bible_text, prepare_bible


def _wav_bytes(seconds=1.5, sr=48000):
    t = np.arange(int(sr * seconds)) / sr
    buf = io.BytesIO()
    sf.write(buf, 0.3 * np.sin(2 * np.pi * 220 * t), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _make_zip(path, items):
    with zipfile.ZipFile(path, "w") as z:
        for name, audio, text in items:
            z.writestr(f"{name}.mp3", audio)
            z.writestr(f"{name}.txt", text.encode("utf-8"))


def test_clean_bible_text_collapses_space_and_pipes():
    assert clean_bible_text("  Kìa,  Đức Chúa Trời |vĩ đại.\n") == "Kìa, Đức Chúa Trời vĩ đại."
    assert clean_bible_text("   ") == ""


def test_prepare_bible_tiny(tmp_path):
    z = tmp_path / "data.zip"
    _make_zip(z, [
        ("GEN_001_01", _wav_bytes(), "Ban đầu, Đức Chúa Trời sáng tạo trời đất. "),
        ("GEN_001_02", _wav_bytes(), "   "),
        ("GEN_001_03", b"not audio", "Có ánh sáng."),
        ("PSA_023_01", _wav_bytes(2.0), "Chúa là Đấng chăn giữ tôi;"),
    ])
    out = tmp_path / "prepared"
    report = prepare_bible(z, out, workers=2)

    assert report.n_in == 4 and report.n_out == 2
    assert sorted(report.skipped) == [("GEN_001_02", "empty_transcript"), ("GEN_001_03", "bad_audio")]
    lines = (out / "metadata.csv").read_text(encoding="utf-8").splitlines()
    assert [ln.split("|")[0] for ln in lines] == ["bible_GEN_001_01", "bible_PSA_023_01"]
    assert lines[0].split("|")[1] == "Ban đầu, Đức Chúa Trời sáng tạo trời đất."
    x, sr = sf.read(out / "wavs" / "bible_PSA_023_01.wav")
    assert sr == 22050 and 0 < len(x) <= 2.0 * 22050
    assert abs(float(lines[1].split("|")[2]) - len(x) / 22050) < 1e-3


def test_prepare_bible_limit(tmp_path):
    z = tmp_path / "data.zip"
    _make_zip(z, [(f"GEN_001_{i:02d}", _wav_bytes(0.5), "câu") for i in range(1, 6)])
    report = prepare_bible(z, tmp_path / "p", workers=1, limit=3)
    assert report.n_in == 3 and report.n_out == 3
