#!/usr/bin/env python3
"""Log Arduino keyword-detection events from Serial to CSV.

Expected Arduino output examples:
  STOP
  STOP,0.91
  stop detected confidence=0.87
  {"event": "STOP", "confidence": 0.93}
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_BAUD = 115200
DEFAULT_OUTPUT = "distraction_log.csv"


@dataclass
class DetectionEvent:
    event: str
    confidence: str
    raw_line: str


def parse_detection(line: str, keyword: str) -> DetectionEvent | None:
    """Return a detection when the serial line appears to contain the keyword."""
    raw = line.strip()
    if not raw:
        return None

    lowered_keyword = keyword.lower()

    if raw.startswith("{") and raw.endswith("}"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        event = str(payload.get("event", payload.get("label", ""))).strip()
        if event.lower() == lowered_keyword:
            confidence = payload.get("confidence", payload.get("score", ""))
            return DetectionEvent(event=event.upper(), confidence=str(confidence), raw_line=raw)

    if lowered_keyword not in raw.lower():
        return None

    confidence = ""
    match = re.search(r"(?:confidence|score)\s*[=:]\s*([0-9]*\.?[0-9]+)", raw, re.I)
    if match:
        confidence = match.group(1)
    else:
        csv_like = [part.strip() for part in raw.split(",")]
        if len(csv_like) >= 2 and re.fullmatch(r"[0-9]*\.?[0-9]+", csv_like[1]):
            confidence = csv_like[1]

    return DetectionEvent(event=keyword.upper(), confidence=confidence, raw_line=raw)


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


def append_event(path: Path, event: DetectionEvent, port: str) -> None:
    now = datetime.now().astimezone()
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


def run_logger(args: argparse.Namespace) -> int:
    output = Path(args.output)
    ensure_header(output)

    if args.dry_run:
        for line in dry_run_lines(args.keyword):
            event = parse_detection(line, args.keyword)
            if event:
                append_event(output, event, port="dry-run")
                print(f"logged: {event.raw_line}")
        print(f"Wrote dry-run events to {output}")
        return 0

    try:
        import serial
    except ImportError:
        print("pyserial is not installed. Install it with: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    print(f"Listening on {args.port} at {args.baud} baud. Writing to {output}.")
    print("Press Ctrl+C to stop.")

    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser:
            time.sleep(args.warmup)
            ser.reset_input_buffer()
            while True:
                raw_bytes = ser.readline()
                if not raw_bytes:
                    continue
                line = raw_bytes.decode("utf-8", errors="replace").strip()
                if args.echo:
                    print(line)
                event = parse_detection(line, args.keyword)
                if event:
                    append_event(output, event, port=args.port)
                    print(f"logged: {event.raw_line}")
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log Arduino STOP detections from Serial to CSV.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port, e.g. /dev/ttyACM0 or /dev/cu.usbmodemXXXX.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Serial baud rate. Default: {DEFAULT_BAUD}.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output CSV path. Default: {DEFAULT_OUTPUT}.")
    parser.add_argument("--keyword", default="STOP", help="Keyword to log. Default: STOP.")
    parser.add_argument("--warmup", type=float, default=2.0, help="Seconds to wait after opening Serial. Default: 2.")
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
