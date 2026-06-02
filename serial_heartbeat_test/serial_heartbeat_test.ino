void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  static unsigned long last_ms = 0;
  if (millis() - last_ms >= 1000) {
    last_ms = millis();
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    Serial.print("HEARTBEAT,");
    Serial.println(millis());
  }
}
