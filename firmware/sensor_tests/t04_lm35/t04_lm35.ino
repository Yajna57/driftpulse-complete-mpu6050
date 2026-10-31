// TEST 4: LM35 temperature. No library.
// Wiring: VCC=5V, OUT=A1, GND. Serial Monitor: 115200 baud.
// Uno/Nano 5 V ADC reference: 10 mV/degC -> degC = raw * 5000 / 1024 / 10.
// Pass: reading 15-40 C at room temp; rises when you pinch the sensor body with fingers.
const uint8_t PIN_LM35 = A1;
const float BASELINE_ALERT_RISE = 1.0f;  // C rise to report "heat detected"

float baseline = NAN;

float readTempC() {
  analogRead(PIN_LM35);  // discard, settle mux
  uint32_t sum = 0;
  for (uint8_t i = 0; i < 32; i++) sum += analogRead(PIN_LM35);
  float raw = sum / 32.0f;
  return raw * 500.0f / 1024.0f;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  Serial.println(F("[T04] LM35 test start"));
  Serial.println(F("[T04] columns: temp_C | status. Pinch sensor to warm it."));
  delay(500);
  baseline = readTempC();
  Serial.print(F("[T04] baseline = "));
  Serial.print(baseline, 2);
  Serial.println(F(" C"));
}

void loop() {
  float t = readTempC();
  const char *status;
  if (t < 5.0f || t > 60.0f) status = "FAIL (out of range: check wiring/5V/GND; floating pin?)";
  else if (t - baseline >= BASELINE_ALERT_RISE) status = "PASS (heat change detected)";
  else status = "OK (in range; pinch to confirm response)";

  Serial.print(F("[T04] "));
  Serial.print(t, 2);
  Serial.print(F(" C | "));
  Serial.println(status);
  delay(500);
}
