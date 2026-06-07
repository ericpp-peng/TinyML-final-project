#!/usr/bin/env python3
"""Pretend to be the Arduino so you can test serial_logger.py without hardware.

It opens a fake serial port (a pseudo-terminal) and periodically sends a STOP
line, exactly like the firmware's report_detection() will. Use it to verify the
PC side end-to-end before the board is flashed.

Terminal 1:
    .venv/bin/python fake_arduino.py
  -> prints the fake port name, e.g. /dev/ttys004

Terminal 2 (use the port it printed; test output goes to test_result/):
    .venv/bin/python serial_logger.py --port /dev/ttys004 --baud 115200 \
        --warmup 0 --echo --out-dir test_result

Watch test_result/<today>.csv fill up. Ctrl+C either side to stop.
"""

from __future__ import annotations

import argparse
import os
import pty
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Fake Arduino STOP sender over a pseudo-terminal.")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between STOP messages. Default: 3.")
    parser.add_argument("--score", type=float, default=None,
                        help="If set, send 'STOP,<score>' like the real firmware instead of bare 'STOP'.")
    args = parser.parse_args()

    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)

    message = "STOP" if args.score is None else f"STOP,{args.score}"

    print(f"Fake Arduino is up. Sending '{message}' every {args.interval}s.")
    print(f"Fake serial port: {slave_name}")
    print("In another terminal run:")
    print(f"    .venv/bin/python serial_logger.py --port {slave_name} --baud 115200 --warmup 0 --echo --out-dir test_result")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            os.write(master_fd, (message + "\r\n").encode())
            print(f"sent: {message}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    finally:
        os.close(master_fd)
        os.close(slave_fd)


if __name__ == "__main__":
    raise SystemExit(main())
