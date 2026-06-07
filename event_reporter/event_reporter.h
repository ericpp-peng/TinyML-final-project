// event_reporter.h
// Standalone "send a detection to the PC" module for the voice logging project.
//
// The keyword model decides *whether* a trigger phrase happened; this module owns
// *reporting* it over Serial. Keeping them apart lets the model work and the
// reporting work be developed and tested independently.
//
// Contract with the PC-side serial_logger.py:
//   - one line per event: "FOCUS_TIME" (or "FOCUS_TIME,<score>")
//   - the PC stamps the time; the board has no clock
//   - a cooldown here collapses the repeated firings of one spoken phrase into
//     a single logged event
//
// Header-only and kept in its own folder so several sketches can share one
// copy. Build any sketch that uses it by passing this folder as a library:
//   arduino-cli compile --fqbn arduino:mbed_nano:nano33ble \
//       --library ../event_reporter <sketch>
//
// To use it inside the real firmware (stop_log_micro_speech): #include
// "event_reporter.h" and call report_detection("FOCUS_TIME", score) where the
// model currently detects the trigger phrase. The micro_speech firmware already
// opens Serial, so reporter_begin() is mainly for standalone test sketches.

#ifndef EVENT_REPORTER_H_
#define EVENT_REPORTER_H_

#include "Arduino.h"

// Ignore events that arrive within this window of the last one sent, so a
// single spoken "stop" is logged once instead of several times.
#ifndef REPORTER_COOLDOWN_MS
#define REPORTER_COOLDOWN_MS 2000
#endif

#ifndef REPORTER_DEFAULT_EVENT
#define REPORTER_DEFAULT_EVENT "FOCUS_TIME"
#endif

// Open the Serial link to the PC. Call once from setup().
// 115200 matches the existing firmware and serial_logger.py's default baud.
inline void reporter_begin(unsigned long baud = 115200) {
  Serial.begin(baud);
}

// Shared cooldown gate. Returns true only if enough time has passed since the
// last send. Both report_detection() overloads go through this single gate.
inline bool reporter_should_send() {
  static unsigned long last_sent_ms = 0;
  static bool have_sent = false;
  unsigned long now = millis();
  if (have_sent && (now - last_sent_ms) < REPORTER_COOLDOWN_MS) {
    return false;  // still cooling down -> drop this event
  }
  last_sent_ms = now;
  have_sent = true;
  return true;
}

// Report a detection with no score: sends the line "<event>".
inline void report_detection(const char* event) {
  if (!reporter_should_send()) {
    return;
  }
  Serial.println(event);
}

// Report a detection with no score using the default event label.
inline void report_detection() {
  report_detection(REPORTER_DEFAULT_EVENT);
}

// Report a detection with a confidence score in [0, 1]: sends "<event>,<score>".
// Use this overload when you want the score logged by the PC side.
inline void report_detection(const char* event, float score) {
  if (!reporter_should_send()) {
    return;
  }
  Serial.print(event);
  Serial.print(",");
  Serial.println(score, 3);
}

// Report a detection with a confidence score using the default event label.
inline void report_detection(float score) {
  report_detection(REPORTER_DEFAULT_EVENT, score);
}

#endif  // EVENT_REPORTER_H_
