#!/usr/bin/env python3
"""Record 1-second WAV clips from a Nano 33 BLE Sense over Serial."""

from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path


DEFAULT_PORT = "/dev/cu.usbmodem2101"
DEFAULT_BAUD = 921600
DEFAULT_OUTPUT_DIR = "recorded_audio"


def next_index(label_dir: Path, label: str) -> int:
    existing = sorted(label_dir.glob(f"{label}_user_*.wav"))
    max_index = 0
    for path in existing:
        try:
            max_index = max(max_index, int(path.stem.rsplit("_", 1)[-1]))
        except ValueError:
            continue
    return max_index + 1


def read_line(ser, timeout_s: float = 10.0) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        return raw.decode("utf-8", errors="replace").strip()
    raise TimeoutError("Timed out waiting for a line from the board.")


def wait_for_audio_begin(ser) -> tuple[int, int]:
    while True:
        line = read_line(ser, timeout_s=15.0)
        print(f"board: {line}")
        if line.startswith("AUDIO_BEGIN "):
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(f"Bad AUDIO_BEGIN line: {line}")
            return int(parts[1]), int(parts[2])


def read_exact(ser, byte_count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining > 0:
        chunk = ser.read(remaining)
        if not chunk:
            raise TimeoutError(f"Timed out with {remaining} bytes remaining.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def save_wav(path: Path, sample_rate: int, pcm_bytes: bytes) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)


def record_one(ser, output_path: Path) -> None:
    ser.reset_input_buffer()
    ser.write(b"REC\n")
    ser.flush()

    sample_rate, sample_count = wait_for_audio_begin(ser)
    pcm_bytes = read_exact(ser, sample_count * 2)

    # Consume the newline after the binary payload and then AUDIO_END.
    while True:
        line = read_line(ser, timeout_s=5.0)
        if not line:
            continue
        if line == "AUDIO_END":
            break
        print(f"board: {line}")

    save_wav(output_path, sample_rate, pcm_bytes)
    duration = sample_count / sample_rate
    print(f"saved: {output_path} ({duration:.2f}s, {sample_count} samples)")


def list_ports() -> int:
    try:
        from serial.tools import list_ports as serial_list_ports
    except ImportError:
        print("pyserial is not installed. Install it with: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    for port in serial_list_ports.comports():
        print(f"{port.device}\t{port.description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"Serial port. Default: {DEFAULT_PORT}")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate. Default: {DEFAULT_BAUD}")
    parser.add_argument("--label", default="stop", help="Label/directory name for saved clips. Default: stop")
    parser.add_argument("--count", type=int, default=20, help="Number of clips to record. Default: 20")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Output root directory. Default: {DEFAULT_OUTPUT_DIR}")
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds to pause between clips. Default: 1.0")
    parser.add_argument("--manual", action="store_true", help="Wait for Enter before each clip.")
    parser.add_argument("--list-ports", action="store_true", help="List Serial ports and exit.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.list_ports:
        return list_ports()

    try:
        import serial
    except ImportError:
        print("pyserial is not installed. Install it with: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    label = args.label.strip()
    if not label:
        print("Label cannot be empty.", file=sys.stderr)
        return 1

    label_dir = Path(args.output_dir) / label
    label_dir.mkdir(parents=True, exist_ok=True)
    index = next_index(label_dir, label)

    print(f"Opening {args.port} at {args.baud} baud.")
    print("Watch the board LED: 3 blinks, then solid-on means recording.")
    print(f"Saving {args.count} clips to {label_dir}")

    with serial.Serial(args.port, args.baud, timeout=2, write_timeout=2) as ser:
        time.sleep(2.0)
        ser.reset_input_buffer()
        ser.write(b"PING\n")
        ser.flush()
        try:
            print(f"board: {read_line(ser, timeout_s=5.0)}")
        except TimeoutError:
            print("No READY line seen, continuing anyway.")

        for clip_number in range(1, args.count + 1):
            output_path = label_dir / f"{label}_user_{index:04d}.wav"
            print(f"\nclip {clip_number}/{args.count}: {output_path.name}")
            if args.manual:
                input("Press Enter, then watch LED and speak during solid-on...")
            else:
                print("Get ready...")
                time.sleep(args.pause)
            record_one(ser, output_path)
            index += 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
