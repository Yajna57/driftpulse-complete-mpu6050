// TEST 2: MAX30102 PPG. Library: "SparkFun MAX3010x Pulse and Proximity Sensor Library".
// Wiring: SDA=A4, SCL=A5, VIN per module rating (3.3 V safest), GND.
// Serial Monitor: 115200 baud.
// Pass: init ok; with no finger IR is low (<~20000); with finger on sensor IR rises (>50000) and wobbles with pulse.
#include <Wire.h>
#include "MAX30105.h"

MAX30105 sensor;
const uint32_t FINGER_THRESHOLD = 50000;

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  Serial.println(F("[T02] MAX30102 test start"));

  if (!sensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println(F("[T02] FAIL: sensor not found at 0x57. Run t00_i2c_scan, check wiring/power."));
    while (true) {}
  }
  Serial.print(F("[T02] part id = 0x"));
  Serial.println(sensor.readPartID(), HEX);  // expect 0x15

  // ledBrightness, sampleAverage, ledMode(2=red+IR), sampleRate, pulseWidth, adcRange
  sensor.setup(0x3F, 4, 2, 100, 411, 16384);
  Serial.println(F("[T02] place fingertip gently on sensor. columns: red | ir | die_temp_C | status"));
}

uint32_t lastTemp = 0;
float dieTemp = 0;
uint32_t irMin = 0xFFFFFFFF, irMax = 0;
uint32_t lastReset = 0;

void loop() {
  sensor.check();
  while (sensor.available()) {
    uint32_t red = sensor.getFIFORed();
    uint32_t ir = sensor.getFIFOIR();
    sensor.nextSample();

    if (ir < irMin) irMin = ir;
    if (ir > irMax) irMax = ir;

    static uint32_t lastPrint = 0;
    if (millis() - lastPrint >= 100) {
      lastPrint = millis();
      const char *status = (ir > FINGER_THRESHOLD) ? "FINGER" : "NO FINGER";
      Serial.print(F("[T02] "));
      Serial.print(red); Serial.print(F(" | "));
      Serial.print(ir); Serial.print(F(" | "));
      Serial.print(dieTemp, 1); Serial.print(F(" | "));
      Serial.println(status);
    }
  }

  if (millis() - lastTemp > 2000) {
    lastTemp = millis();
    dieTemp = sensor.readTemperature();
  }

  // Every 5 s: summary verdict from IR range seen.
  if (millis() - lastReset > 5000) {
    lastReset = millis();
    uint32_t span = (irMax >= irMin) ? irMax - irMin : 0;
    Serial.print(F("[T02] SUMMARY 5s: ir min="));
    Serial.print(irMin);
    Serial.print(F(" max="));
    Serial.print(irMax);
    Serial.print(F(" span="));
    Serial.print(span);
    if (irMax > FINGER_THRESHOLD && span > 200) Serial.println(F(" -> PASS (finger + pulse ripple)"));
    else if (irMax > FINGER_THRESHOLD) Serial.println(F(" -> finger seen, weak ripple: press lighter/steady"));
    else Serial.println(F(" -> no finger detected (sensor alive; put finger to confirm PASS)"));
    irMin = 0xFFFFFFFF;
    irMax = 0;
  }
}
