import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import soundfile as sf

from vtts.data import voxcpm_client as vc

KEY = "test-secret-key"


def _wav(seconds: float, sr: int = 24000) -> bytes:
    t = np.arange(int(sr * seconds)) / sr
    buf = io.BytesIO()
    sf.write(buf, 0.3 * np.sin(2 * np.pi * 220 * t), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class Fake:
    """Scripted responses per input text: a list of (status, body) consumed in order."""

    def __init__(self):
        self.script: dict[str, list[tuple[int, bytes]]] = {}
        self.calls: dict[str, int] = {}


@pytest.fixture
def server(tmp_path):
    fake = Fake()

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.headers["Authorization"] == f"Bearer {KEY}"
            text = body["input"]
            fake.calls[text] = fake.calls.get(text, 0) + 1
            status, payload = fake.script[text].pop(0)
            self.send_response(status)
            if status == 429:
                self.send_header("Retry-After", "0")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = tmp_path / "voxcpm.env"
    env.write_text(f"VOXCPM_URL=http://127.0.0.1:{srv.server_port}\nVOXCPM_KEY={KEY}\n")
    yield fake, env
    srv.shutdown()


def _run(fake, env, out, items):
    return vc.run(items, out, "nam-1", workers=2, per_minute=6000, env=env, log_every=0)


def test_retries_then_ok(server, tmp_path, monkeypatch):
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)
    fake, env = server
    fake.script["a"] = [(500, b"x"), (500, b"x"), (200, _wav(1.0))]
    c = _run(fake, env, tmp_path / "o", [{"id": "a", "text": "a", "lang": "vi"}])
    rec = json.loads((tmp_path / "o" / "manifest.jsonl").read_text())
    assert c["ok"] == 1 and rec["attempts"] == 3 and rec["status"] == "ok"
    x, sr = sf.read(tmp_path / "o" / "audio" / "a.flac")
    assert sr == 24000 and abs(len(x) / sr - 1.0) < 0.01


def test_empty_audio_is_rejected_without_file(server, tmp_path):
    fake, env = server
    fake.script["b"] = [(200, _wav(0.1))]
    c = _run(fake, env, tmp_path / "o", [{"id": "b", "text": "b"}])
    assert c["bad_audio"] == 1
    assert not (tmp_path / "o" / "audio" / "b.flac").exists()
    assert not list((tmp_path / "o" / "audio").glob("*.tmp*"))


def test_resume_skips_done(server, tmp_path):
    fake, env = server
    fake.script["c"] = [(200, _wav(0.5))]
    _run(fake, env, tmp_path / "o", [{"id": "c", "text": "c"}])
    c = _run(fake, env, tmp_path / "o", [{"id": "c", "text": "c"}])
    assert c["skipped"] == 1 and fake.calls["c"] == 1


def test_bad_request_not_retried_and_key_never_logged(server, tmp_path):
    fake, env = server
    fake.script["d"] = [(400, b"{}")]
    c = _run(fake, env, tmp_path / "o", [{"id": "d", "text": "d"}])
    assert c["failed"] == 1 and fake.calls["d"] == 1
    assert KEY not in (tmp_path / "o" / "manifest.jsonl").read_text()
