#include <Wire.h>

// DriftPulse wiring check: reports SDA/SCL line levels and every I2C device found.
// Expected: 0x57 = MAX30102, 0x68 = MPU6050 (AD0 to GND). Serial: 230400 baud.

void scanOnce() {
  // Idle I2C lines must be HIGH. LOW means a short to GND, a dead module or no power.
  pinMode(SDA, INPUT_PULLUP);
  pinMode(SCL, INPUT_PULLUP);
  delay(5);
  int sda = digitalRead(SDA);
  int scl = digitalRead(SCL);
  Serial.print("LINES SDA(A4)=");
  Serial.print(sda ? "HIGH" : "LOW-STUCK");
  Serial.print(" SCL(A5)=");
  Serial.println(scl ? "HIGH" : "LOW-STUCK");

  Wire.begin();
  Wire.setClock(100000);
#if defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(3000, true);
#endif

  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.print("FOUND 0x");
      if (addr < 16) Serial.print('0');
      Serial.print(addr, HEX);
      if (addr == 0x57) Serial.print(" MAX30102");
      if (addr == 0x68) Serial.print(" MPU6050");
      if (addr == 0x69) Serial.print(" MPU6050 (AD0 is HIGH - connect AD0 to GND)");
      Serial.println();
      found++;
    } else if (err == 5) {
      Serial.println("TIMEOUT - I2C bus stuck; check SDA/SCL wiring");
      break;
    }
  }

  if (found == 0) Serial.println("NO I2C DEVICES FOUND");

  // Read WHO_AM_I so clone chips (MPU6500/MPU9250 etc.) are recognised.
  Wire.beginTransmission(0x68);
  Wire.write(0x75);
  if (Wire.endTransmission(false) == 0 && Wire.requestFrom(0x68, 1) == 1) {
    Serial.print("MPU WHO_AM_I=0x");
    Serial.println(Wire.read(), HEX);
  }
  Wire.beginTransmission(0x57);
  Wire.write(0xFF);
  if (Wire.endTransmission(false) == 0 && Wire.requestFrom(0x57, 1) == 1) {
    Serial.print("MAX PART_ID=0x");
    Serial.println(Wire.read(), HEX);
  }
  Wire.end();
  Serial.println("SCAN DONE");
}

void setup() {
  Serial.begin(230400);
  Serial.println("INFO:I2C_SCANNER");
}

void loop() {
  scanOnce();
  delay(2000);
}
