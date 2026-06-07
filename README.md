# TinyML Final Project

Arduino Nano 33 BLE keyword spotting project for detecting the spoken word
`stop`.

This project is based on the Lab4 `micro_speech` workflow. The model was
retrained with Speech Commands data and exported as a TensorFlow Lite Micro C++
array for Arduino deployment.

## Main Files

- `STOP_KWS_Lab4.ipynb`: Lab4-style notebook used to train/export the STOP KWS model.
- `STOP_KWS_Lab4.executed.ipynb`: executed notebook with training results.
- `stop_log_micro_speech/`: Arduino firmware for Nano 33 BLE.
- `stop_log_micro_speech/micro_features_model.cpp`: exported STOP TFLite Micro model.
- `event_reporter/event_reporter.h`: shared board-side module that sends a detection over Serial.
- `event_reporter_test/`: standalone sketch that sends STOP periodically to test the PC pipeline.
- `serial_logger.py`: PC-side receiver that logs detections to daily CSVs under `result/`.
- `tests/test_serial_logger.py`: unit + end-to-end tests for the logger.
- `debug_notes/serial_port_drop_root_cause.md`: notes about the serial port drop issue and fix.
- `proposal/` and `Mid-Project Checkpoint Report/`: project report materials.

## Arduino Firmware

The firmware prints a line like this when STOP is detected:

```text
STOP,0.875
```

It now also routes the same event through the shared `event_reporter` module
(see below), so during this integration step the line is printed twice per
detection. Compiling therefore requires passing the module folder as a library:

```sh
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble \
  --library event_reporter stop_log_micro_speech
```

Upload:

```sh
arduino-cli upload -p /dev/cu.usbmodem2101 \
  --fqbn arduino:mbed_nano:nano33ble \
  stop_log_micro_speech
```

Monitor:

```sh
arduino-cli monitor -p /dev/cu.usbmodem2101 -c baudrate=115200
```

## Detection Reporting & PC Logging

When STOP is detected on the board, the event is sent over USB Serial and a
Python script on the PC records it to a timestamped CSV. The board has no clock,
so the PC stamps the time.

### `event_reporter/` — shared board-side reporter module

Header-only module that owns *sending* a detection over Serial, kept separate
from the keyword model so the two can be developed and tested independently.

- `reporter_begin(baud)` — open Serial (not needed inside the micro_speech
  firmware, which already brings Serial up).
- `report_detection()` — send the line `STOP`.
- `report_detection(score)` — send `STOP,<score>` (matches the firmware output).
- Built-in 2 s cooldown so one spoken "stop" is reported once, not several times.

It lives in its own folder so both the test sketch and the real firmware share
one copy. Pass it as a library when building any sketch that uses it:
`--library event_reporter`.

### `event_reporter_test/` — standalone send test

Flash `event_reporter_test.ino` and the board sends `STOP` every 3 seconds (no
microphone needed), to verify the whole PC pipeline end to end.

```sh
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble \
  --library event_reporter event_reporter_test
arduino-cli upload -p /dev/cu.usbmodemXXXX \
  --fqbn arduino:mbed_nano:nano33ble event_reporter_test
```

### `serial_logger.py` — PC-side receiver

Reads STOP events from Serial and appends one row per detection to a daily CSV.

```sh
.venv/bin/python serial_logger.py --port /dev/cu.usbmodemXXXX --baud 115200
```

- One CSV per day named `YYYY-MM-DD.csv`.
- Real detections go to `result/`; test runs use `--out-dir test_result`.
- Columns: `timestamp_iso, date, time, day_of_week, event, confidence, raw_line, port`.

### Tests

```sh
.venv/bin/python tests/test_serial_logger.py
```

Unit tests for the parser plus an end-to-end test that runs the real logger
against a fake serial port (a pseudo-terminal) and checks the CSV. Output goes
to `test_result/`. Requires `pyserial` in the project venv.

## Progress

- [x] STOP keyword model trained, quantized, and running on the Nano 33 BLE.
- [x] PC-side `serial_logger.py` records detections to daily CSVs.
- [x] Board-side `event_reporter` module + standalone send test.
- [x] End-to-end verified on real hardware: board send → PC receive → CSV.
- [x] `event_reporter` wired into the real firmware *alongside* the original
      Serial output (added, not replacing it yet).
- [ ] Live microphone test of the integrated firmware ("stop" → logged row).
- [ ] Collapse the duplicate STOP output once integration is confirmed.

## Notes

Large downloaded datasets, TensorFlow source files, logs, and checkpoints are
ignored by git. Re-download Speech Commands data or rerun the notebook if those
artifacts are needed locally.

`test_result/` and `.venv/` are git-ignored. Real logs in `result/` are kept.
