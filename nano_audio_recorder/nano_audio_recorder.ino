/*
  Nano 33 BLE Sense PDM audio recorder.

  Serial protocol:
    Host sends: REC\n
    Board replies:
      AUDIO_BEGIN <sample_rate> <sample_count>\n
      <raw signed 16-bit little-endian PCM bytes>
      \nAUDIO_END\n

  The built-in LED blinks three times before recording and stays on while
  recording. Speak during the solid-on LED window.
*/

#include <PDM.h>

namespace {
constexpr int kSampleRate = 16000;
constexpr int kChannels = 1;
constexpr int kRecordingMs = 2000;
constexpr int kRecordingSamples = kSampleRate * kRecordingMs / 1000;
constexpr unsigned long kRecordingTimeoutMs = 2500;
constexpr int kSerialBaud = 921600;

int16_t audio_buffer[kRecordingSamples];
volatile int samples_captured = 0;
volatile bool is_recording = false;

void DiscardPdmBytes(int bytes_available) {
  uint8_t discard[128];
  while (bytes_available > 0) {
    const int bytes_to_read = min(bytes_available, static_cast<int>(sizeof(discard)));
    PDM.read(discard, bytes_to_read);
    bytes_available -= bytes_to_read;
  }
}

void OnPdmData() {
  int bytes_available = PDM.available();
  if (bytes_available <= 0) {
    return;
  }

  if (!is_recording || samples_captured >= kRecordingSamples) {
    DiscardPdmBytes(bytes_available);
    return;
  }

  const int samples_available = bytes_available / sizeof(int16_t);
  const int samples_remaining = kRecordingSamples - samples_captured;
  const int samples_to_read = min(samples_available, samples_remaining);
  const int bytes_to_read = samples_to_read * sizeof(int16_t);

  if (bytes_to_read > 0) {
    PDM.read(audio_buffer + samples_captured, bytes_to_read);
    samples_captured += samples_to_read;
    bytes_available -= bytes_to_read;
  }

  if (bytes_available > 0) {
    DiscardPdmBytes(bytes_available);
  }
}

void BlinkCountdown() {
  for (int i = 0; i < 3; ++i) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(150);
    digitalWrite(LED_BUILTIN, LOW);
    delay(350);
  }
}

void RecordAndSendClip() {
  Serial.println("REC_COUNTDOWN");
  Serial.flush();
  BlinkCountdown();

  noInterrupts();
  samples_captured = 0;
  is_recording = true;
  interrupts();

  digitalWrite(LED_BUILTIN, HIGH);
  const unsigned long start_ms = millis();
  while ((samples_captured < kRecordingSamples) &&
         ((millis() - start_ms) < kRecordingTimeoutMs)) {
    delay(1);
  }

  noInterrupts();
  is_recording = false;
  const int final_sample_count = samples_captured;
  interrupts();

  digitalWrite(LED_BUILTIN, LOW);

  Serial.print("AUDIO_BEGIN ");
  Serial.print(kSampleRate);
  Serial.print(" ");
  Serial.println(final_sample_count);
  Serial.write(reinterpret_cast<const uint8_t*>(audio_buffer),
               final_sample_count * sizeof(int16_t));
  Serial.println();
  Serial.println("AUDIO_END");
  Serial.flush();
}
}  // namespace

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(kSerialBaud);
  const unsigned long serial_start_ms = millis();
  while (!Serial && (millis() - serial_start_ms < 5000)) {
    delay(10);
  }

  PDM.onReceive(OnPdmData);
  if (!PDM.begin(kChannels, kSampleRate)) {
    Serial.println("PDM_BEGIN_FAILED");
    while (true) {
      digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
      delay(100);
    }
  }
  PDM.setGain(20);

  Serial.println("READY");
  Serial.print("SAMPLE_RATE ");
  Serial.println(kSampleRate);
  Serial.print("SAMPLE_COUNT ");
  Serial.println(kRecordingSamples);
}

void loop() {
  if (!Serial.available()) {
    delay(5);
    return;
  }

  String command = Serial.readStringUntil('\n');
  command.trim();

  if (command == "REC") {
    RecordAndSendClip();
  } else if (command == "PING") {
    Serial.println("READY");
  } else if (command.length() > 0) {
    Serial.print("UNKNOWN_COMMAND ");
    Serial.println(command);
  }
}
