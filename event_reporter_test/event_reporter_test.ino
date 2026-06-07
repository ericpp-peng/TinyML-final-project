// event_reporter_test.ino
// Flash this to the Arduino and it pretends the keyword model keeps firing:
// it calls report_detection() on a fixed interval, so you can verify the whole
// PC pipeline (Serial -> serial_logger.py -> test_result/<date>.csv) WITHOUT
// having to actually speak "focus time".
//
// The reporter module lives in its own folder (../event_reporter) so the real
// firmware can share it. Pass that folder as a library when building:
//   arduino-cli compile --fqbn arduino:mbed_nano:nano33ble \
//       --library ../event_reporter event_reporter_test
//   arduino-cli upload  --fqbn arduino:mbed_nano:nano33ble \
//       -p /dev/cu.usbmodemXXXX event_reporter_test
//
// On the PC, record into the test folder so it stays separate from real data:
//   python serial_logger.py --port /dev/cu.usbmodemXXXX \
//       --baud 115200 --out-dir test_result --keyword FOCUS_TIME
//
// The built-in LED toggles on every send so you can see the board is alive.

#include "event_reporter.h"

// How often the fake "detection" fires. Kept above REPORTER_COOLDOWN_MS (2 s)
// so every call actually sends. Drop it below 2000 to watch the cooldown
// swallow the extra events.
constexpr unsigned long kSendIntervalMs = 3000;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  reporter_begin(115200);
}

void loop() {
  static unsigned long last_ms = 0;
  if (millis() - last_ms >= kSendIntervalMs) {
    last_ms = millis();
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    report_detection();  // bare "FOCUS_TIME"; use report_detection(0.9f) for a score
  }
}
