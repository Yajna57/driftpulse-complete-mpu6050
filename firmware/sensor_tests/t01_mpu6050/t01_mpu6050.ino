// TEST 1: MPU6050 accel + gyro. No library needed (raw Wire).
// Wiring: SDA=A4, SCL=A5, AD0=GND (0x68). Serial Monitor: 115200 baud.
// Pass: WHO_AM_I ok, |accel| ~1 g at rest, values change when you move/tilt board.
#include <Wire.h>

const uint8_t MPU_ADDR = 0x68;

bool writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool readRegs(uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(MPU_ADDR, n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  Wire.begin();
  Serial.println(F("[T01] MPU6050 test start"));

  uint8_t who = 0;
  if (!readRegs(0x75, &who, 1)) {
    Serial.println(F("[T01] FAIL: no I2C response at 0x68. Check wiring/power/AD0."));
    while (true) {}
  }
  Serial.print(F("[T01] WHO_AM_I = 0x"));
  Serial.println(who, HEX);
  // Genuine MPU6050 = 0x68. Some clones return 0x70/0x72/0x98.
  if (who != 0x68) Serial.println(F("[T01] WARN: unexpected WHO_AM_I (clone?). Continuing."));

  if (!writeReg(0x6B, 0x00)) {  // wake from sleep
    Serial.println(F("[T01] FAIL: cannot wake chip."));
    while (true) {}
  }
  writeReg(0x1C, 0x00);  // accel +-2 g
  writeReg(0x1B, 0x00);  // gyro +-250 dps
  delay(100);
  Serial.println(F("[T01] columns: ax_g ay_g az_g | gx_dps gy_dps gz_dps | |a|_g | temp_C | status"));
}

void loop() {
  uint8_t b[14];
  if (!readRegs(0x3B, b, 14)) {
    Serial.println(F("[T01] FAIL: read error"));
    delay(1000);
    return;
  }
  int16_t ax = (b[0] << 8) | b[1];
  int16_t ay = (b[2] << 8) | b[3];
  int16_t az = (b[4] << 8) | b[5];
  int16_t tr = (b[6] << 8) | b[7];
  int16_t gx = (b[8] << 8) | b[9];
  int16_t gy = (b[10] << 8) | b[11];
  int16_t gz = (b[12] << 8) | b[13];

  float axg = ax / 16384.0f, ayg = ay / 16384.0f, azg = az / 16384.0f;
  float mag = sqrt(axg * axg + ayg * ayg + azg * azg);
  float tempC = tr / 340.0f + 36.53f;

  bool allZero = (ax == 0 && ay == 0 && az == 0);
  bool allFF = (ax == -1 && ay == -1 && az == -1);
  const char *status;
  if (allZero || allFF) status = "FAIL(no data)";
  else if (mag > 0.8f && mag < 1.2f) status = "PASS(rest ~1g)";
  else status = "MOVING/CHECK";

  Serial.print(F("[T01] "));
  Serial.print(axg, 3); Serial.print(' ');
  Serial.print(ayg, 3); Serial.print(' ');
  Serial.print(azg, 3); Serial.print(F(" | "));
  Serial.print(gx / 131.0f, 1); Serial.print(' ');
  Serial.print(gy / 131.0f, 1); Serial.print(' ');
  Serial.print(gz / 131.0f, 1); Serial.print(F(" | "));
  Serial.print(mag, 3); Serial.print(F(" | "));
  Serial.print(tempC, 1); Serial.print(F(" | "));
  Serial.println(status);
  delay(200);
}
