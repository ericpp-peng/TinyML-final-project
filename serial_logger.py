#!/usr/bin/env python3
"""Log Arduino keyword-detection events from Serial to CSV.

Expected Arduino output examples:
  STOP
  STOP,0.91
  FOCUS_TIME,0.61
  stop detected confidence=0.87
  {"event": "STOP", "confidence": 0.93}
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_BAUD = 115200
DEFAULT_OUT_DIR = "result"
STOP_REQUESTED = False


@dataclass
class DetectionEvent:
    event: str
    confidence: str
    raw_line: str


def parse_detection(line: str, keyword: str) -> DetectionEvent | None:
    """Return a detection when the serial line is an explicit event record."""
    raw = line.strip()
    if not raw:
        return None

    lowered_keyword = keyword.lower()
    canonical_event = keyword.upper()

    if raw.startswith("{") and raw.endswith("}"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        event = str(payload.get("event", payload.get("label", ""))).strip()
        if event.lower() == lowered_keyword:
            confidence = payload.get("confidence", payload.get("score", ""))
            return DetectionEvent(event=canonical_event, confidence=str(confidence), raw_line=raw)

    csv_like = [part.strip() for part in raw.split(",")]
    if csv_like and csv_like[0].lower() == lowered_keyword:
        confidence = ""
        if len(csv_like) >= 2 and re.fullmatch(r"[0-9]*\.?[0-9]+", csv_like[1]):
            confidence = csv_like[1]
        return DetectionEvent(event=canonical_event, confidence=confidence, raw_line=raw)

    detected_match = re.fullmatch(
        rf"{re.escape(keyword)}\s+detected(?:\s+(?:confidence|score)\s*[=:]\s*([0-9]*\.?[0-9]+))?",
        raw,
        re.I,
    )
    if detected_match:
        return DetectionEvent(
            event=canonical_event,
            confidence=detected_match.group(1) or "",
            raw_line=raw,
        )

    return None


def ensure_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames())
        writer.writeheader()


def fieldnames() -> list[str]:
    return [
        "timestamp_iso",
        "date",
        "time",
        "day_of_week",
        "event",
        "confidence",
        "raw_line",
        "port",
    ]


def dated_csv_path(out_dir: Path, now: datetime) -> Path:
    """One CSV per day: result/2026-06-06.csv."""
    return out_dir / f"{now.strftime('%Y-%m-%d')}.csv"


def append_event(out_dir: Path, event: DetectionEvent, port: str) -> Path:
    """Append one detection to result/<today>.csv, creating it if needed.

    Returns the path written so callers can show / verify it. The date is
    stamped here by the PC (the board has no clock), and it also picks which
    daily file the row lands in, so logging across midnight rolls over cleanly.
    """
    now = datetime.now().astimezone()
    path = dated_csv_path(out_dir, now)
    ensure_header(path)
    row = {
        "timestamp_iso": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "event": event.event,
        "confidence": event.confidence,
        "raw_line": event.raw_line,
        "port": port,
    }
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames())
        writer.writerow(row)
    return path


def dry_run_lines(keyword: str) -> Iterable[str]:
    yield "noise"
    yield f"{keyword.upper()},0.92"
    yield f"{keyword.lower()} detected confidence=0.88"
    yield json.dumps({"event": keyword.upper(), "confidence": 0.95})


def list_ports() -> int:
    try:
        from serial.tools import list_ports as serial_list_ports
    except ImportError:
        print("pyserial is not installed. Install it with: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    ports = list(serial_list_ports.comports())
    if not ports:
        print("No Serial ports found.")
        return 0

    for port in ports:
        print(f"{port.device}\t{port.description}")
    return 0


def request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def run_logger(args: argparse.Namespace) -> int:
    global STOP_REQUESTED
    STOP_REQUESTED = False
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        logged_count = 0
        for line in dry_run_lines(args.keyword):
            event = parse_detection(line, args.keyword)
            if event:
                path = append_event(out_dir, event, port="dry-run")
                logged_count += 1
                print(f"logged: {event.raw_line} -> {path}")
                if args.max_events and logged_count >= args.max_events:
                    break
        print(f"Wrote dry-run events under {out_dir}/")
        return 0

    try:
        import serial
    except ImportError:
        print("pyserial is not installed. Install it with: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    print(f"Listening on {args.port} at {args.baud} baud. Writing daily CSVs under {out_dir}/.")
    print("Press Ctrl+C to stop.")

    try:
        logged_count = 0
        started_at = time.monotonic()
        with serial.Serial(args.port, args.baud, timeout=0.2) as ser:
            time.sleep(args.warmup)
            ser.reset_input_buffer()
            while not STOP_REQUESTED:
                if args.duration and (time.monotonic() - started_at) >= args.duration:
                    break
                raw_bytes = ser.readline()
                if not raw_bytes:
                    continue
                line = raw_bytes.decode("utf-8", errors="replace").strip()
                if args.echo:
                    print(line)
                event = parse_detection(line, args.keyword)
                if event:
                    path = append_event(out_dir, event, port=args.port)
                    logged_count += 1
                    print(f"logged: {event.raw_line} -> {path}")
                    if args.max_events and logged_count >= args.max_events:
                        break
        print("\nStopped.")
        return 0
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log Arduino keyword detections from Serial to CSV.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port, e.g. /dev/ttyACM0 or /dev/cu.usbmodemXXXX.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Serial baud rate. Default: {DEFAULT_BAUD}.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Folder for daily CSVs (one file per day, named YYYY-MM-DD.csv). Default: {DEFAULT_OUT_DIR}.")
    parser.add_argument("--keyword", default="FOCUS_TIME", help="Keyword/event label to log. Default: FOCUS_TIME.")
    parser.add_argument("--warmup", type=float, default=2.0, help="Seconds to wait after opening Serial. Default: 2.")
    parser.add_argument("--duration", type=float, default=0.0, help="Stop automatically after this many seconds. Default: 0, run until stopped.")
    parser.add_argument("--max-events", type=int, default=0, help="Stop automatically after logging this many events. Default: 0, unlimited.")
    parser.add_argument("--echo", action="store_true", help="Print every Serial line, not only logged detections.")
    parser.add_argument("--dry-run", action="store_true", help="Write sample detections without opening Serial.")
    parser.add_argument("--list-ports", action="store_true", help="List available Serial ports and exit.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.list_ports:
        return list_ports()
    return run_logger(args)


if __name__ == "__main__":
    raise SystemExit(main())
