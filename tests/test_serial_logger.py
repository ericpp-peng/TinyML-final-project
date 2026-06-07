#!/usr/bin/env python3
"""Tests for serial_logger.py (the PC-side keyword receiver).

Two layers:
  1. parse_detection() unit tests   -- pure logic, no hardware, no pyserial.
  2. end-to-end serial test         -- spawns the real logger against a fake
                                       serial port (a pseudo-terminal) and
                                       checks a row actually lands in the CSV.

Run it directly:
    .venv/bin/python tests/test_serial_logger.py
or with pytest:
    .venv/bin/python -m pytest tests/test_serial_logger.py
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Make serial_logger importable when running this file from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SERIAL_LOGGER = PROJECT_ROOT / "serial_logger.py"

# Test output goes here, kept separate from real detections in result/.
TEST_RESULT_DIR = PROJECT_ROOT / "test_result"

import serial_logger as sl  # noqa: E402  (path set above)


# --------------------------------------------------------------------------
# 1. parse_detection() unit tests -- the core "is this an event?" logic.
# --------------------------------------------------------------------------

def test_plain_stop_is_detected():
    """Our agreed firmware contract: a bare 'STOP' line."""
    event = sl.parse_detection("STOP", keyword="STOP")
    assert event is not None
    assert event.event == "STOP"
    assert event.confidence == ""


def test_stop_with_score_is_detected():
    """The real Lab4 firmware actually prints 'STOP,<score>'."""
    event = sl.parse_detection("STOP,0.875", keyword="STOP")
    assert event is not None
    assert event.event == "STOP"
    assert event.confidence == "0.875"


def test_focus_time_with_score_is_detected():
    event = sl.parse_detection("FOCUS_TIME,0.604", keyword="FOCUS_TIME")
    assert event is not None
    assert event.event == "FOCUS_TIME"
    assert event.confidence == "0.604"


def test_focus_time_debug_line_is_ignored():
    """Debug output must not create an extra CSV row."""
    assert sl.parse_detection("Heard focus_time (166) @102384ms", keyword="FOCUS_TIME") is None


def test_noise_line_is_ignored():
    assert sl.parse_detection("noise", keyword="STOP") is None


def test_blank_line_is_ignored():
    assert sl.parse_detection("   ", keyword="STOP") is None


def test_boot_message_is_ignored():
    """Garbage the board prints on reset must not be logged as a detection."""
    assert sl.parse_detection("Mbed OS started", keyword="STOP") is None


def test_csv_row_has_timestamp_fields():
    """Python stamps the time; the board never sends it."""
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        event = sl.parse_detection("STOP", keyword="STOP")
        path = sl.append_event(out_dir, event, port="test")

        # File is named after today's date inside the result folder.
        assert path.parent == out_dir
        assert path.name.endswith(".csv")

        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        assert len(rows) == 1
        row = rows[0]
        # All time fields are populated by the PC side.
        assert row["date"]
        assert row["time"]
        assert row["day_of_week"]
        assert row["event"] == "STOP"
        # The file name matches the stamped date.
        assert path.name == f"{row['date']}.csv"


# --------------------------------------------------------------------------
# 2. End-to-end test over a fake serial port (pseudo-terminal).
#    This exercises the *real* logger process: open port -> read -> write CSV.
# --------------------------------------------------------------------------

def _read_dir_rows(out_dir: Path) -> list[dict]:
    """Read all rows from whatever dated CSV(s) the logger created."""
    rows: list[dict] = []
    for path in sorted(out_dir.glob("*.csv")):
        rows.extend(csv.DictReader(path.open(encoding="utf-8")))
    return rows


def test_end_to_end_over_fake_serial():
    try:
        import serial  # noqa: F401  (only to skip cleanly if missing)
    except ImportError:
        print("  SKIP test_end_to_end_over_fake_serial: pyserial not installed")
        return

    import pty

    # A pty gives us a master/slave pair. The slave looks like a real serial
    # device (/dev/ttysNN); we hand that to the logger and play "Arduino" by
    # writing to the master end.
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)

    # Write into test_result/ so the artifact is inspectable and kept apart from
    # real data in result/. Clear old CSVs first so the row count is deterministic.
    out_dir = TEST_RESULT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.csv"):
        stale.unlink()

    cmd = [
        sys.executable,
        str(SERIAL_LOGGER),
        "--port", slave_name,
        "--baud", "115200",
        "--out-dir", str(out_dir),
        "--warmup", "0",
        "--keyword", "STOP",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        # Give the logger a moment to import pyserial, open the port, and
        # flush its input buffer before we start sending real data.
        time.sleep(2.0)
        if proc.poll() is not None:
            err = proc.stderr.read().decode(errors="replace")
            raise AssertionError(f"logger exited early:\n{err}")

        # Play the board. \r\n mimics Arduino's Serial.println().
        os.write(master_fd, b"Mbed OS started\r\n")   # boot noise -> ignored
        os.write(master_fd, b"STOP\r\n")              # plain contract
        os.write(master_fd, b"STOP,0.91\r\n")         # real firmware form

        # Poll the result folder until both detections show up (or time out).
        deadline = time.time() + 5.0
        rows: list[dict] = []
        while time.time() < deadline:
            rows = _read_dir_rows(out_dir)
            if len(rows) >= 2:
                break
            time.sleep(0.1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        os.close(master_fd)
        os.close(slave_fd)

    assert len(rows) == 2, f"expected 2 logged STOPs, got {len(rows)}: {rows}"
    assert all(r["event"] == "STOP" for r in rows)
    assert rows[1]["confidence"] == "0.91"
    # Time was stamped by the PC, not sent by the board.
    assert rows[0]["date"] and rows[0]["time"]


# --------------------------------------------------------------------------
# Plain runner (so it works without pytest installed).
# --------------------------------------------------------------------------

def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
