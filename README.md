# TinyML Final Project

Arduino Nano 33 BLE Sense TinyML project for detecting the spoken trigger phrase
`focus time`.

The project is based on the Lab 4 `micro_speech` workflow. The final firmware
uses a quantized TensorFlow Lite Micro model with four classes:

- `silence`
- `unknown`
- `focus_time`
- `hard_negative`

Only `focus_time` creates a log event. The `hard_negative` class contains
personal recordings of normal speech and near-trigger phrases that should not
fire, which helped improve recall while preserving the observed low
false-positive behavior.

## Reproducibility Status

Someone who clones this repository can reproduce the deployed demo behavior by
compiling and uploading the included Arduino firmware. The final model is
already embedded in:

```text
stop_log_micro_speech/micro_features_model.cpp
```

The final TFLite artifact is also included:

```text
models_focus_time/model.tflite
```

The personal training clips used for the final `focus_time` model are included:

```text
recorded_audio/focus_time/
recorded_audio/hard_negative/
```

The public Google Speech Commands v0.02 dataset is not committed because it is
large. To retrain from scratch, download it separately:

```text
https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz
```

Because TensorFlow training can depend on package versions, random
initialization, and the exact training environment, retraining from scratch may
not produce byte-for-byte identical weights. It should reproduce the same
pipeline and a similar result, but the most reliable way to reproduce the exact
deployed firmware is to use the committed `micro_features_model.cpp`.

## Main Files

- `stop_log_micro_speech/`: Arduino firmware for Nano 33 BLE Sense.
- `stop_log_micro_speech/micro_features_model.cpp`: final embedded
  `focus_time` TFLite Micro model.
- `stop_log_micro_speech/micro_features_micro_model_settings.*`: class labels
  and audio model settings.
- `models_focus_time/model.tflite`: final quantized model before C array export.
- `recorded_audio/focus_time/`: personal positive trigger recordings.
- `recorded_audio/hard_negative/`: personal non-trigger speech recordings used
  for the explicit `hard_negative` class.
- `prepare_focus_time_audio.py`: copies recorded positives into a Speech
  Commands-style dataset folder with deterministic train/validation/test names.
- `prepare_hard_negative_audio.py`: copies hard negatives into a Speech
  Commands-style dataset folder.
- `record_nano_audio.py`: PC-side helper for recording WAV clips from the Nano.
- `serial_logger.py`: PC-side receiver that logs detections to CSV.
- `debug_notes/focus_time_evaluation.md`: experiment log for threshold,
  alignment, hard-negative, and recall tests.
- `debug_notes/serial_port_drop_root_cause.md`: notes about the early serial
  port drop issue and model alignment fix.
- `proposal/design_doc.md`: final design document and implementation reasoning.

Older STOP files and notebooks are kept as project history because the final
design evolved from the initial STOP keyword experiment.

## Arduino Firmware

Compile:

```sh
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble \
  --library event_reporter \
  stop_log_micro_speech
```

Upload:

```sh
arduino-cli upload -p /dev/cu.usbmodemXXXX \
  --fqbn arduino:mbed_nano:nano33ble \
  stop_log_micro_speech
```

Monitor:

```sh
arduino-cli monitor -p /dev/cu.usbmodemXXXX -c baudrate=115200
```

When the board detects the trigger phrase, it prints a line like:

```text
FOCUS_TIME,0.604
```

## PC Logging

The board has no real-time clock, so the PC timestamps each detection event.

```sh
python serial_logger.py --port /dev/cu.usbmodemXXXX --baud 115200 --keyword FOCUS_TIME
```

For a bounded test run, add either:

```sh
python serial_logger.py --port /dev/cu.usbmodemXXXX --baud 115200 --duration 60
python serial_logger.py --port /dev/cu.usbmodemXXXX --baud 115200 --max-events 10
```

The logger writes one CSV per day under `result/` with columns:

```text
timestamp_iso, date, time, day_of_week, event, confidence, raw_line, port
```

## Retraining Outline

1. Download and extract Speech Commands v0.02 into a local `dataset/` folder.
2. Copy the personal positive clips:

   ```sh
   python prepare_focus_time_audio.py --dataset-root dataset
   ```

3. Copy the personal hard negatives used by the final model:

   ```sh
   python prepare_hard_negative_audio.py --dataset-root dataset --latest
   ```

4. Run the Lab 4-style Speech Commands training/export workflow with wanted
   words `focus_time,hard_negative`.
5. Convert the exported TFLite model into a C array and replace the model in
   `stop_log_micro_speech/micro_features_model.cpp`.
6. Keep the Lab 4-style 4-byte `DATA_ALIGN_ATTRIBUTE` on `g_model`; without it,
   the Nano 33 BLE firmware can crash early and make the USB serial port
   disappear.

## Tests

```sh
python tests/test_serial_logger.py
```

These tests cover the PC-side serial logger parser and CSV output path. The
on-device keyword behavior was evaluated manually with the Nano 33 BLE Sense;
the latest notes are in `debug_notes/focus_time_evaluation.md`.

## Current Result

The current best version is the explicit `hard_negative` model with a lower
command threshold.

- Baseline recall: 15 / 40 = 37.5%
- Current recall test: 15 / 16 = 93.75%
- Informal live testing: no false positives observed during normal speech

The main implementation lesson is that lowering thresholds alone caused false
positives. The improvement came from adding realistic personal hard negatives as
a separate class, then lowering the threshold after the model had learned that
boundary.
