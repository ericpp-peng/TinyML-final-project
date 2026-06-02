# STOP & LOG: A Voice-Triggered Distraction Tracker

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

This project addresses that problem with a lightweight, always-on voice-triggered distraction logger. When a user notices they have become distracted, they say the keyword **"STOP"**. The Arduino Nano 33 BLE Sense detects this keyword in real time using a TinyML model running on-device. Upon detection, a timestamp is logged to a CSV file on the user's computer via the Serial connection. Over time, this log reveals how frequently and at what times of day the user tends to get distracted, enabling meaningful self-assessment.

This problem is a natural fit for TinyML because the solution requires:
- **Always-on keyword detection** with low power consumption
- **On-device inference** with no dependency on cloud or internet connectivity
- **Real-time response** to a single spoken word
- Deployment on a **resource-constrained microcontroller** (256 KB RAM, 1 MB Flash)

---

## 2. Dataset

### Primary Training Dataset
**Google Speech Commands Dataset v0.02**
- Source: `https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz`
- Contains over 100,000 one-second WAV audio clips at 16 kHz
- Covers 35 spoken words including "stop", "yes", "no", "go", etc.
- Also includes background noise and silence samples for robust training

### Key Features Used
| Feature | Details |
|---------|---------|
| Target keyword | "stop" (already in dataset) |
| Negative class | Background noise + other words |
| Sample rate | 16,000 Hz |
| Clip duration | 1 second |
| Audio features | MFCC (Mel-Frequency Cepstral Coefficients) |

### Optional: Custom Supplementary Recordings
To improve accuracy for the user's own voice and environment, additional personal recordings of "stop" (~50–100 samples) can be collected using the Google Colab audio recorder from Lab 4 and merged with the Speech Commands dataset.

---

## 3. Modeling Approach

### Sensor
- **Microphone** (built-in on Arduino Nano 33 BLE Sense)

### Audio Preprocessing Pipeline
Following the pipeline established in Lab 4:
1. Raw audio captured at 16 kHz
2. Short-Time Fourier Transform (STFT) → Spectrogram
3. Mel-filter bank applied → Mel Spectrogram
4. Log compression → MFCC features (40 coefficients)

### Neural Network Architecture
- **Type:** Depthwise Separable Convolutional Neural Network (DS-CNN)
  - Well-suited for audio classification on microcontrollers
  - Significantly fewer parameters than standard CNNs
- **Input:** MFCC feature matrix (49 × 40)
- **Output:** 2 classes — `stop` and `background/unknown`

### Compression for Deployment
- **Post-Training Quantization:** Convert 32-bit float weights to 8-bit integers using TensorFlow Lite
- **Target model size:** < 20 KB (fits within Arduino Nano 33 BLE Sense Flash)
- Quantization reference data: subset of Speech Commands dataset (same as Lab 4)

---

## 4. Deployment Plan

### Hardware
- **Board:** Arduino Nano 33 BLE Sense
- **Sensors used:** Built-in MP34DT05 PDM microphone
- **No additional hardware required**

### Deployment Steps
Following the Lab 4 hardware workflow:
1. Train and quantize model in Google Colab → export as TensorFlow Lite `.cc` file
2. Replace `micro_features_model.cpp` in the `micro_speech` Arduino sketch with the new model
3. Upload sketch to Arduino Nano 33 BLE Sense via Arduino IDE

### Runtime Behavior
```
Microphone captures audio (1-second windows)
        ↓
On-device MFCC computation
        ↓
TinyML model inference (DS-CNN)
        ↓
"stop" detected → Serial output: timestamp string
        ↓
Python logging script on PC → append row to distraction_log.csv
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
| False positives from similar-sounding words (e.g., "shop", "top") | Include diverse negative examples during training; tune detection threshold |
| Acoustic mismatch between dataset (studio recordings) and real-world use | Supplement with personal recordings in the actual use environment |
| Model size exceeding Flash memory limit | Apply 8-bit quantization; use DS-CNN architecture which is compact by design |
| Serial logging reliability | Add simple handshake protocol; buffer missed events |
| Low detection confidence in noisy environments | Require two consecutive high-confidence predictions before logging |

---

## 6. Estimated Timeline and Division of Work

This is a solo project. The following timeline is planned across three weeks:

| Week | Tasks |
|------|-------|
| **Week 1** | Download Speech Commands dataset · Run Lab 4 Colab notebook end-to-end · Verify baseline `micro_speech` example works on hardware |
| **Week 2** | Retrain model targeting only "stop" vs. background · Quantize and export TFLite model · Deploy to Arduino and test detection accuracy |
| **Week 3** | Write Python Serial logging script · Test full pipeline in real use conditions · Collect distraction log data · Prepare final report and demo |

---

## 7. Request for Additional Hardware

No additional hardware is requested. This project uses only the **Arduino Nano 33 BLE Sense** already available, specifically its built-in microphone. All other components (PC for logging, USB cable) are standard and already on hand.