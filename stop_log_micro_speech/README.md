# STOP keyword Arduino sketch

This sketch is based on the Lab 4 `micro_speech` example. It continuously
listens on the Arduino Nano 33 BLE Sense microphone, runs the TensorFlow Lite
Micro keyword model, and prints one CSV-like line when a new high-confidence
`stop` detection is accepted:

```text
STOP,0.863
```

That line is compatible with `../serial_logger.py`.

## Important model note

The copied `micro_features_model.cpp` is still the Lab 4 example model until
you replace it. The sketch is wired for these output labels:

```text
silence, unknown, stop
```

So the replacement model must have 3 output scores in that same order, or you
must update `micro_features_micro_model_settings.{h,cpp}` to match your model.

For this Lab 4 style pipeline, the model input must also match the sketch's
feature settings:

- 16 kHz audio
- 1 second window
- 40 feature bins
- 49 slices
- int8 input tensor with 1960 elements

## Replacing the model

In `TinyML_Lab4.ipynb`, set:

```python
WANTED_WORDS = "stop"
```

Then run the Lab 4 export cell that creates `kws.cc`:

```python
MODEL_TFLITE = '/content/models/model.tflite'
MODEL_TFLITE_MICRO = 'kws.cc'
!xxd -i {MODEL_TFLITE} > {MODEL_TFLITE_MICRO}
REPLACE_TEXT = MODEL_TFLITE.replace('/', '_').replace('.', '_')
!sed -i 's/'{REPLACE_TEXT}'/g_model/g' {MODEL_TFLITE_MICRO}
```

Copy the generated `g_model` array from `kws.cc` into
`micro_features_model.cpp`, replacing the old hex array. Keep the exported
symbols expected by `micro_features_model.h`:

```cpp
const unsigned char g_model[] = { ... };
const int g_model_len = ...;
```

## Tuning

The final serial gate is in `arduino_command_responder.cpp`:

```cpp
constexpr uint8_t kStopThreshold = 220;
```

Lower it if real `STOP` commands are missed; raise it if normal speech creates
false positives.
