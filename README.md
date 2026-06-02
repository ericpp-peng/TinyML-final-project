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
- `debug_notes/serial_port_drop_root_cause.md`: notes about the serial port drop issue and fix.
- `proposal/` and `Mid-Project Checkpoint Report/`: project report materials.

## Arduino Firmware

The firmware prints a line like this when STOP is detected:

```text
STOP,0.875
```

Compile:

```sh
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble stop_log_micro_speech
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

## Notes

Large downloaded datasets, TensorFlow source files, logs, and checkpoints are
ignored by git. Re-download Speech Commands data or rerun the notebook if those
artifacts are needed locally.
