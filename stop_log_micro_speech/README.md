# Focus Time Arduino Sketch

This sketch is based on the Lab 4 `micro_speech` example. It continuously
listens on the Arduino Nano 33 BLE Sense microphone, runs the TensorFlow Lite
Micro phrase model, and sends one CSV-like event line when a new
high-confidence `focus_time` detection is accepted:

```text
FOCUS_TIME,0.604
```

That line is compatible with `../serial_logger.py`. The PC-side logger stamps
the real date/time because the board does not have a clock:

```sh
python ../serial_logger.py --port /dev/cu.usbmodemXXXX --baud 115200 --keyword FOCUS_TIME
```

## Event Reporting

The sketch routes accepted detections through `../event_reporter/`:

```cpp
report_detection("FOCUS_TIME", score / 255.0f);
```

The reporter owns the Serial event format and a 2-second cooldown, so one
spoken phrase does not create several CSV rows. Debug output such as
`Heard focus_time (...)` is not meant to be logged as an event.

Build with the reporter folder as an Arduino library:

```sh
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble \
  --library ../event_reporter \
  .
```

## Model Settings

The current firmware is wired for these output labels:

```text
silence, unknown, focus_time, hard_negative
```

The model input uses the same Lab 4 micro feature pipeline, expanded to a
2-second phrase window:

- 16 kHz audio
- 2 second window
- 40 feature bins
- 99 slices
- int8 input tensor with 3960 elements

If the model is retrained, keep `micro_features_micro_model_settings.{h,cpp}`
consistent with the exported model's label order and feature dimensions.

## Model Array Alignment

Keep the Lab 4-style 4-byte alignment on `g_model` in
`micro_features_model.cpp`:

```cpp
const unsigned char g_model[] DATA_ALIGN_ATTRIBUTE = { ... };
```

Without this alignment, the Nano 33 BLE application firmware can crash early
when TensorFlow Lite Micro reads the FlatBuffer. When that happens, the USB
serial port may disappear until the board is put into bootloader mode with a
double reset.

## Tuning

The command recognizer is configured in `stop_log_micro_speech.ino`:

```cpp
static RecognizeCommands static_recognizer(error_reporter, 1000, 150, 1500, 3);
```

The final trigger gate is in `arduino_command_responder.cpp`:

```cpp
constexpr uint8_t kTriggerThreshold = 150;
```

Lowering the threshold alone previously caused false positives. The current
threshold works because the model has a dedicated `hard_negative` class.
