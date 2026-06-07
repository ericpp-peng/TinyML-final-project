# Focus Time: A Voice-Triggered Distraction Tracker

**Course:** EE P 564 A Sp 26: Tiny Machine Learning For Ultra Low-Power Edge Computing — Spring 2026
**Instructor:** Radha Poovendran

## Project Proposal Requirements

- **Format**: 3-5 page PDF (excluding any dedicated title page)
- **Title page**: Project title, names, and student IDs of all team members (may be a separate page)
- **Required content**:
        - Problem Statement: What problem are you solving? Why is it relevant for TinyML?
        - Dataset(s): What dataset will you use or collect? Key features?
        - Modeling Approach: Will you use audio, vision, IMU models? Type(s) of neural net(s)? Compression?
        - Deployment Plan: How will you deploy and evaluate your model? (e.g., Arduino Nano BLE)
        - Challenges & Solutions: Anticipated bottlenecks and your strategies
        - Estimated Timeline and Division of Work: When do you plan to work on the different components of your project? And if more than one person is in your group, how do you plan to divide work among all people?
        - Request for Additional Hardware: See the course announcement for details

---

## 1. Problem Statement

Distraction is a widespread challenge that affects productivity and self-awareness. Many people struggle to recognize how often they lose focus during work or study sessions, making it difficult to identify patterns and improve their habits.

This project addresses that problem with a lightweight, always-on voice-triggered distraction logger. When a user notices they have become distracted and wants to return to work, they say the fixed trigger phrase **"focus time"**. The Arduino Nano 33 BLE Sense detects this phrase using a TinyML model running on-device. Upon detection, a timestamp is logged to a CSV file on the user's computer via the Serial connection. Over time, this log reveals how frequently and at what times of day the user tends to get distracted, enabling meaningful self-assessment.

This problem is a natural fit for TinyML because the solution requires:
- **Always-on keyword detection** with low power consumption
- **On-device inference** with no dependency on cloud or internet connectivity
- **Real-time response** to a short spoken trigger phrase
- Deployment on a **resource-constrained microcontroller** (256 KB RAM, 1 MB Flash)

---

## 2. Dataset

### Base Negative Dataset
**Google Speech Commands Dataset v0.02**
- Source: `https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz`
- Contains over 100,000 one-second WAV audio clips at 16 kHz
- Covers 35 spoken words including "stop", "yes", "no", "go", etc.
- Also includes background noise and silence samples for robust training

This dataset is mainly used for `unknown` and background examples. It helps the model learn that general speech, short words, and environmental noise should not trigger a log event.

### Custom Trigger Dataset
The target trigger phrase is **"focus time"**, recorded directly with the Arduino Nano 33 BLE Sense microphone. Recording with the same microphone used at deployment reduces the acoustic mismatch between training and real-world inference.

The project uses a 2-second capture window so the full phrase can fit naturally without requiring the user to align speech perfectly to a sliding inference window.

### Key Features Used
| Feature | Details |
|---------|---------|
| Target phrase | "focus time" |
| Negative class | Background noise + other words + personal non-trigger phrases |
| Sample rate | 16,000 Hz |
| Clip duration | 2 seconds |
| Audio features | MFCC (Mel-Frequency Cepstral Coefficients) |

### Personal Unknown Recordings
To reduce false positives, the custom dataset also includes personal recordings of phrases that should **not** trigger the logger, such as:

- "hello"
- "stop"
- "oh shoot"
- "work time"
- ordinary speech
- short Chinese phrases
- room noise and keyboard noise

---

## 3. Modeling Approach

### Sensor
- **Microphone** (built-in on Arduino Nano 33 BLE Sense)

### Audio Preprocessing Pipeline
The low-level preprocessing follows Lab 4:
1. Raw audio captured at 16 kHz
2. Short-Time Fourier Transform (STFT) -> Spectrogram
3. Mel-filter bank applied -> Mel Spectrogram
4. Log compression -> MFCC-style micro features (40 coefficients)

The current firmware follows the stock Lab 4 `micro_speech` loop: it continuously classifies the latest audio window, but the model input has been expanded from the original 1-second keyword window to a 2-second phrase window. This keeps the implementation close to the verified Lab 4 Arduino workflow while allowing the full phrase "focus time" to fit into one inference input.

One limitation of this approach is phrase alignment. A sliding inference window may capture only the beginning or ending of the phrase, depending on when the user starts speaking. The planned improvement is a voice-activity-triggered capture strategy:

Runtime states:

```
IDLE:
  Monitor microphone energy.

TRIGGERED:
  When speech energy rises above a threshold, record a full 2-second clip.

INFER:
  Generate features for that complete clip and run the TinyML model once.

COOLDOWN:
  Ignore repeated triggers briefly so one spoken phrase logs one event.
```

### Neural Network Architecture
- **Type:** Depthwise Separable Convolutional Neural Network (DS-CNN)
  - Well-suited for audio classification on microcontrollers
  - Significantly fewer parameters than standard CNNs
- **Input:** Micro feature matrix (99 × 40) for a 2-second clip
- **Output:** 3 classes — `silence`, `unknown`, and `focus_time`

### Compression for Deployment
- **Post-Training Quantization:** Convert 32-bit float weights to 8-bit integers using TensorFlow Lite
- **Target model size:** small enough to fit within Arduino Nano 33 BLE Sense Flash and RAM
- Quantization reference data: subset of Speech Commands dataset (same as Lab 4)

---

## 4. Deployment Plan

### Hardware
- **Board:** Arduino Nano 33 BLE Sense
- **Sensors used:** Built-in MP34DT05 PDM microphone
- **No additional hardware required**

### Deployment Steps
Following the Lab 4 hardware workflow:
1. Record custom `focus_time` clips using the Nano 33 BLE Sense microphone
2. Train and quantize model with Speech Commands negatives + personal trigger recordings -> export as TensorFlow Lite `.cc` file
3. Replace `micro_features_model.cpp` in the Arduino sketch with the new model
4. Upload sketch to Arduino Nano 33 BLE Sense via Arduino IDE or `arduino-cli`

### Current Runtime Behavior
```
Microphone streams audio continuously
        ↓
Latest 2-second window is converted to micro features
        ↓
On-device micro feature computation
        ↓
TinyML model inference (DS-CNN)
        ↓
"focus_time" detected -> Serial output: timestamp string
        ↓
Python logging script on PC → append row to distraction_log.csv
```

### Planned Alignment Improvement
```
Microphone monitors for speech energy
        ↓
Speech detected -> hold a full 2-second clip
        ↓
Run one inference on the aligned phrase window
        ↓
Log only high-confidence focus_time detections
```

### Logging Script
A simple Python script reads from the Serial port and writes each detection event to a CSV file with columns: `timestamp`, `date`, `time`, `day_of_week`.

### Evaluation
- **Accuracy** measured on held-out test split of Speech Commands dataset (10%)
- **False positive rate** tested in realistic ambient noise (typing, music, conversation)
- **Latency** measured from speech onset to Serial output (target: < 1 second)

---

## 5. Challenges & Solutions

| Challenge | Strategy |
|-----------|----------|
| False positives from normal speech | Include diverse personal unknown recordings such as "hello", "stop", "oh shoot", and ordinary speech |
| Acoustic mismatch between dataset (studio recordings) and real-world use | Supplement with personal recordings in the actual use environment |
| Model size exceeding Flash memory limit | Apply 8-bit quantization; use DS-CNN architecture which is compact by design |
| Serial logging reliability | Add simple handshake protocol; buffer missed events |
| Phrase alignment with inference window | Current implementation uses a 2-second Lab 4-style sliding window; planned improvement is voice-activity-triggered 2-second capture |

---

## 6. Estimated Timeline and Division of Work

This is a solo project. The following timeline is planned across three weeks:

| Week | Tasks |
|------|-------|
| **Week 1** | Download Speech Commands dataset · Run Lab 4 Colab notebook end-to-end · Verify baseline `micro_speech` example works on hardware |
| **Week 2** | Collect `focus_time` recordings · Retrain phrase model with personal negatives · Quantize and export TFLite model · Deploy to Arduino and test detection accuracy |
| **Week 3** | Implement voice-activity-triggered 2-second capture · Write Python Serial logging script · Test full pipeline in real use conditions · Collect distraction log data · Prepare final report and demo |

---

## 7. Request for Additional Hardware

No additional hardware is requested. This project uses only the **Arduino Nano 33 BLE Sense** already available, specifically its built-in microphone. All other components (PC for logging, USB cable) are standard and already on hand.
