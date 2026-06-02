# STOP KWS Firmware Serial Port Drop Debug Notes

## Background

This final project is based on Lab4 `micro_speech`.

The goal was to keep the Lab4 keyword spotting firmware structure, but replace
the original yes/no model with a model trained to detect:

- `silence`
- `unknown`
- `stop`

The STOP model was generated from the Lab4-style notebook and copied into
`stop_log_micro_speech/micro_features_model.cpp`.

## Problem Seen

After uploading the STOP firmware to the Arduino Nano 33 BLE, the upload itself
could finish successfully, but immediately after reset the serial port often
disappeared.

Typical symptoms:

- Arduino IDE showed timeout when opening Serial Monitor.
- `arduino-cli monitor -p /dev/cu.usbmodem2101 -c baudrate=115200` failed.
- `arduino-cli board list` no longer showed `/dev/cu.usbmodem2101`.
- Upload only worked again after double reset, because double reset forced the
  board into bootloader mode.

This made it look like upload or bootloader was broken, but upload was actually
working. The application firmware was crashing or failing very early after boot.

## Why Double Reset Helped

Double reset does not fix the application firmware. It puts the Nano 33 BLE into
bootloader mode.

In bootloader mode, the board exposes a USB serial port again, so `arduino-cli`
or Arduino IDE can upload new firmware.

After the broken application firmware started running again, the USB serial port
would disappear again.

That is why the pattern was:

1. Double reset.
2. Port appears.
3. Upload succeeds.
4. Firmware starts.
5. Port disappears again.

## Debug Steps

We tested the firmware in smaller stages:

1. Minimal Serial heartbeat firmware worked.
2. STOP model allocation by itself worked.
3. PDM microphone begin/callback tests worked.
4. Full firmware still made the serial port disappear.
5. Lab4 source files were compared against the final project files.

The important clue was that the generated STOP model array was not aligned the
same way as the Lab4 model array.

## Root Cause

The generated STOP model in `micro_features_model.cpp` was declared like this:

```cpp
const unsigned char g_model[] = {
  ...
};
```

But the Lab4 model uses 4-byte alignment:

```cpp
const unsigned char g_model[] DATA_ALIGN_ATTRIBUTE = {
  ...
};
```

TensorFlow Lite Micro reads the model as a FlatBuffer. On Cortex-M boards such
as the Nano 33 BLE, unaligned model data can cause invalid memory access or a
HardFault when the firmware maps or reads the model.

When that happens very early in the firmware, the USB CDC serial connection may
never finish starting, so macOS and Arduino IDE lose the serial port.

So the board was not bricked, and the bootloader was not the main problem. The
application firmware was likely crashing because the TFLite model array was not
properly aligned.

## Fix Applied

The STOP model array now has the same alignment helper style as Lab4:

```cpp
#ifdef __has_attribute
#define HAVE_ATTRIBUTE(x) __has_attribute(x)
#else
#define HAVE_ATTRIBUTE(x) 0
#endif
#if HAVE_ATTRIBUTE(aligned) || (defined(__GNUC__) && !defined(__clang__))
#define DATA_ALIGN_ATTRIBUTE __attribute__((aligned(4)))
#else
#define DATA_ALIGN_ATTRIBUTE
#endif

const unsigned char g_model[] DATA_ALIGN_ATTRIBUTE = {
  ...
};
```

This fix is in:

```text
stop_log_micro_speech/micro_features_model.cpp
```

## Other Changes Kept Lab4-Compatible

To avoid mixing debug changes with the real firmware, these files were restored
to Lab4 behavior:

- `stop_log_micro_speech/feature_provider.cpp`
- `stop_log_micro_speech/arduino_audio_provider.cpp`
- `stop_log_micro_speech/stop_log_micro_speech.ino`

The final `.ino` is intentionally almost the same as Lab4. The meaningful
differences are:

- `kTensorArenaSize` is `60 * 1024` because the STOP model is larger than the
  original Lab4 model.
- The model labels are changed to `silence`, `unknown`, `stop`.
- `arduino_command_responder.cpp` prints `STOP,<score>` when STOP is detected.

## Verification

After applying the alignment fix:

1. Upload completed successfully.
2. `/dev/cu.usbmodem2101` still appeared in `arduino-cli board list` after reset.
3. Serial Monitor connected without timeout.
4. Speaking "stop" produced output similar to:

```text
Heard stop (223) @43328ms
STOP,0.875
```

This confirms:

- The board firmware is no longer killing the USB serial port.
- The STOP model is running.
- STOP detection is reaching the command responder.

## Useful Commands

Check whether the board is visible:

```sh
arduino-cli board list
```

Upload firmware:

```sh
arduino-cli upload -p /dev/cu.usbmodem2101 \
  --fqbn arduino:mbed_nano:nano33ble \
  stop_log_micro_speech
```

Open serial monitor:

```sh
arduino-cli monitor -p /dev/cu.usbmodem2101 -c baudrate=115200
```

If the port disappears again, double reset the board to enter bootloader mode,
then upload again.

## Short Explanation

The serial port kept disappearing because the application firmware was likely
crashing immediately after boot. The most likely trigger was that the generated
STOP TFLite model array did not have the 4-byte alignment used by the original
Lab4 model. After adding the alignment macro back, the firmware uploaded,
the serial port stayed visible, and STOP detection worked.
