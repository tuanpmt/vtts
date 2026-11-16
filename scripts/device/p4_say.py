"""Talk to the ESP32-P4 TTS firmware over serial.

Usage: uv run --with pyserial python scripts/device/p4_say.py PORT [--reset] ["command or sentence" ...]
Prints the board output until each command's DONE line (or the timeout).
"""

import argparse
import base64
import sys
import time
import wave
from pathlib import Path

import serial


def read_until(ser, marker: str, timeout: float) -> list[str]:
    lines, buf, end = [], b"", time.time() + timeout
    while time.time() < end:
        buf += ser.read(ser.in_waiting or 1)
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            line = raw.decode("utf-8", "replace").rstrip("\r")
            lines.append(line)
            if not line.startswith("B"):  # base64 PCM lines are kept quiet
                print(line, flush=True)
            if marker in line:
                return lines
    return lines


def save_dump(lines: list[str], path: Path) -> None:
    """Rebuild a WAV from a `dump` command's PCM/B lines."""
    header = next(x for x in lines if x.startswith("PCM "))
    sr, n = map(int, header.split()[1:3])
    pcm = b"".join(base64.b64decode(x[1:]) for x in lines if x.startswith("B") and not x.startswith("Build"))
    if len(pcm) != 2 * n:
        sys.exit(f"dump truncated: {len(pcm)} bytes for {n} samples")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    print(f"saved {path} ({n / sr:.2f} s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("cmds", nargs="*")
    ap.add_argument("--reset", action="store_true", help="reset the board and wait for READY")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--dump-dir", type=Path, default=None,
                    help="save each `dump <text>` result here as dump_<n>.wav")
    a = ap.parse_args()
    ser = serial.Serial(a.port, 115200, timeout=0.1)
    if a.reset:
        ser.dtr, ser.rts = False, True
        time.sleep(0.1)
        ser.rts = False
        read_until(ser, "READY", 30)
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.write(b"\n")  # terminate any noise the port open left in the board's line buffer
    time.sleep(0.2)
    ser.reset_input_buffer()
    n_dump = 0
    for c in a.cmds:
        ser.write((c + "\n").encode("utf-8"))
        lines = read_until(ser, "DONE", a.timeout)
        if not any("DONE" in x for x in lines):
            sys.exit(f"no DONE for: {c}")
        if c.startswith("dump ") and a.dump_dir:
            save_dump(lines, a.dump_dir / f"dump_{n_dump}.wav")
            n_dump += 1


if __name__ == "__main__":
    main()
