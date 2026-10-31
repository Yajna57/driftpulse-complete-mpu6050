// TEST 0: I2C scanner. Expect 0x57 (MAX30102) and 0x68 (MPU6050).
// Serial Monitor: 115200 baud.
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  Wire.begin();
  Serial.println(F("[T00] I2C scan start (SDA=A4, SCL=A5)"));
}

void loop() {
  uint8_t found = 0;
  bool max30102 = false, mpu6050 = false;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      found++;
      Serial.print(F("[T00] device at 0x"));
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
      if (addr == 0x57) max30102 = true;
      if (addr == 0x68 || addr == 0x69) mpu6050 = true;
    }
  }
  Serial.print(F("[T00] devices found: "));
  Serial.println(found);
  Serial.println(max30102 ? F("[T00] MAX30102 0x57: PASS") : F("[T00] MAX30102 0x57: FAIL (check SDA/SCL/VIN/GND)"));
  Serial.println(mpu6050 ? F("[T00] MPU6050 0x68: PASS") : F("[T00] MPU6050 0x68: FAIL (check SDA/SCL/VCC/GND, AD0->GND)"));
  Serial.println();
  delay(3000);
}
