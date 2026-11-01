#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"

// DriftPulse Phase 1
// Hardware: Arduino Uno/Nano + MAX30102 + AD8232 + LM35 + MPU6050
// Serial output: CSV @ ~100 Hz, 115200 baud

const uint8_t ECG_PIN = A0;
const uint8_t TEMP_PIN = A1;
const uint8_t ECG_LO_PLUS_PIN = 7;
const uint8_t ECG_LO_MINUS_PIN = 6;

const unsigned long SAMPLE_PERIOD_US = 10000UL; // 100 Hz
unsigned long nextSampleUs = 0;

MAX30105 max30102;

// MPU6050 over raw Wire (same method as firmware/sensor_tests/t01_mpu6050).
// The Adafruit library rejects clone chips whose WHO_AM_I is not 0x68.
uint8_t MPU_ADDR = 0x68;  // 0x69 when AD0 is tied to 3.3V
const float ACCEL_LSB_PER_G = 8192.0f;   // +-4 g
const float GYRO_LSB_PER_DPS = 65.5f;    // +-500 dps
const float G_MS2 = 9.80665f;
const float DEG_TO_RAD_F = 0.01745329f;
float accelX = 0, accelY = 0, accelZ = 0;
float gyroX = 0, gyroY = 0, gyroZ = 0;

uint32_t latestIR = 0;
uint32_t latestRed = 0;
unsigned long lastBeatMs = 0;
float heartRateBpm = 0.0f;
bool max30102Ready = false;
bool mpu6050Ready = false;
bool i2cBusReady = false;

// Quick ACK probe (uses the Wire timeout) before handing the bus to a library.
bool i2cDevicePresent(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool setupMAX30102() {
  // 100 kHz is more tolerant of breadboard wires and two modules on one bus.
  if (!max30102.begin(Wire, I2C_SPEED_STANDARD)) {
    return false;
  }

  byte ledBrightness = 60;
  byte sampleAverage = 4;
  byte ledMode = 2;      // Red + IR
  int sampleRate = 100;  // Hz
  int pulseWidth = 411;
  int adcRange = 4096;

  max30102.setup(
    ledBrightness,
    sampleAverage,
    ledMode,
    sampleRate,
    pulseWidth,
    adcRange
  );
  return true;
}

bool mpuWriteReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool mpuReadRegs(uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(MPU_ADDR, n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

bool setupMPU6050() {
  // Accept either I2C address, then wake the chip. WHO_AM_I is not checked
  // because clone chips report other IDs.
  if (i2cDevicePresent(0x68)) MPU_ADDR = 0x68;
  else if (i2cDevicePresent(0x69)) MPU_ADDR = 0x69;
  else return false;
  uint8_t who = 0;
  if (!mpuReadRegs(0x75, &who, 1)) {
    Serial.println("ERROR:MPU6050_WHO_AM_I_READ_FAILED");
    return false;
  }
  Serial.print("INFO:MPU6050_ADDR 0x");
  Serial.print(MPU_ADDR, HEX);
  Serial.print(" WHO_AM_I 0x");
  Serial.println(who, HEX);
  if (!mpuWriteReg(0x6B, 0x00)) {  // wake from sleep
    Serial.println("ERROR:MPU6050_WAKE_FAILED");
    return false;
  }
  mpuWriteReg(0x1A, 0x04);  // DLPF ~21 Hz
  mpuWriteReg(0x1B, 0x08);  // gyro +-500 dps
  mpuWriteReg(0x1C, 0x08);  // accel +-4 g
  delay(100);
  return true;
}

uint8_t mpuReadFailures = 0;

void readMPU6050() {
  uint8_t b[14];
  if (!mpuReadRegs(0x3B, b, 14)) {
    // Keep last values; after 50 straight failures re-run setup (loop retries).
    if (++mpuReadFailures >= 50) {
      mpuReadFailures = 0;
      mpu6050Ready = false;
      Serial.println("ERROR:MPU6050_READ_FAILED");
    }
    return;
  }
  mpuReadFailures = 0;
  int16_t ax = (b[0] << 8) | b[1];
  int16_t ay = (b[2] << 8) | b[3];
  int16_t az = (b[4] << 8) | b[5];
  int16_t gx = (b[8] << 8) | b[9];
  int16_t gy = (b[10] << 8) | b[11];
  int16_t gz = (b[12] << 8) | b[13];
  accelX = ax / ACCEL_LSB_PER_G * G_MS2;
  accelY = ay / ACCEL_LSB_PER_G * G_MS2;
  accelZ = az / ACCEL_LSB_PER_G * G_MS2;
  gyroX = gx / GYRO_LSB_PER_DPS * DEG_TO_RAD_F;
  gyroY = gy / GYRO_LSB_PER_DPS * DEG_TO_RAD_F;
  gyroZ = gz / GYRO_LSB_PER_DPS * DEG_TO_RAD_F;
}

void updateMAX30102() {
  if (!max30102Ready) return;

  max30102.check();

  while (max30102.available()) {
    latestRed = max30102.getRed();
    latestIR = max30102.getIR();

    if (latestIR > 50000 && checkForBeat(latestIR)) {
      unsigned long currentBeatMs = millis();

      if (lastBeatMs != 0) {
        unsigned long deltaMs = currentBeatMs - lastBeatMs;
        if (deltaMs > 0) {
          float instantBpm = 60000.0f / deltaMs;
          if (instantBpm >= 30.0f && instantBpm <= 220.0f) {
            heartRateBpm = (heartRateBpm == 0.0f)
              ? instantBpm
              : (heartRateBpm * 0.80f + instantBpm * 0.20f);
          }
        }
      }
      lastBeatMs = currentBeatMs;
    }

    // Weak/no finger contact on the optical sensor.
    if (latestIR < 50000) {
      heartRateBpm = 0.0f;
      lastBeatMs = 0;
    }

    max30102.nextSample();
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("INFO:DRIFTPULSE_BOOT");

  pinMode(ECG_LO_PLUS_PIN, INPUT);
  pinMode(ECG_LO_MINUS_PIN, INPUT);

  // An idle I2C bus must read HIGH. If SDA or SCL is held LOW (short to GND,
  // unpowered module, wire in the wrong row) every I2C call can hang forever,
  // so skip the I2C sensors and keep streaming ECG + temperature.
  pinMode(SDA, INPUT_PULLUP);
  pinMode(SCL, INPUT_PULLUP);
  delay(5);
  bool i2cBusOk = digitalRead(SDA) == HIGH && digitalRead(SCL) == HIGH;

  if (i2cBusOk) {
    i2cBusReady = true;
    Wire.begin();
#if defined(WIRE_HAS_TIMEOUT)
    Wire.setWireTimeout(25000 /* us */, true /* reset bus on timeout */);
#endif
    // Boot scan: shows exactly which I2C addresses answer (expect 0x57 and 0x68).
    for (uint8_t addr = 1; addr < 127; addr++) {
      if (i2cDevicePresent(addr)) {
        Serial.print("INFO:I2C_FOUND 0x");
        Serial.println(addr, HEX);
      }
    }
    max30102Ready = i2cDevicePresent(0x57) && setupMAX30102();
    if (!max30102Ready) Serial.println("ERROR:MAX30102_NOT_FOUND");
    if (max30102Ready) Serial.println("INFO:MAX30102_OK");
    mpu6050Ready = setupMPU6050();
    if (!mpu6050Ready) Serial.println("ERROR:MPU6050_NOT_FOUND");
    if (mpu6050Ready) Serial.println("INFO:MPU6050_OK");
  } else {
    Serial.print("ERROR:I2C_BUS_STUCK_LOW SDA=");
    Serial.print(digitalRead(SDA) ? "HIGH" : "LOW");
    Serial.print(" SCL=");
    Serial.println(digitalRead(SCL) ? "HIGH" : "LOW");
  }

  if (!max30102Ready) Serial.println("WARN:MAX30102_DISABLED");
  if (!mpu6050Ready) Serial.println("WARN:MPU6050_DISABLED");

  nextSampleUs = micros();

  Serial.println(
    "arduino_ms,max30102_ir,max30102_red,heart_rate_bpm,"
    "ecg_raw,ecg_lead_off,temperature_c,"
    "accel_x_ms2,accel_y_ms2,accel_z_ms2,"
    "gyro_x_rads,gyro_y_rads,gyro_z_rads"
  );
}

unsigned long lastMpuRetryMs = 0;

void loop() {
  updateMAX30102();

  // MPU6050 missing at boot (late power, loose wire)? Retry every 2 s.
  if (!mpu6050Ready && i2cBusReady && millis() - lastMpuRetryMs >= 2000) {
    lastMpuRetryMs = millis();
    mpu6050Ready = setupMPU6050();
    if (mpu6050Ready) Serial.println("INFO:MPU6050_OK");
  }

  unsigned long nowUs = micros();
  if ((long)(nowUs - nextSampleUs) < 0) return;
  nextSampleUs += SAMPLE_PERIOD_US;

  // AD8232 ECG
  int ecgRaw = analogRead(ECG_PIN);
  bool ecgLeadOff =
    digitalRead(ECG_LO_PLUS_PIN) || digitalRead(ECG_LO_MINUS_PIN);

  // LM35: 10 mV / degree C, Arduino ADC reference assumed ~5 V.
  int tempRaw = analogRead(TEMP_PIN);
  float tempVoltage = tempRaw * (5.0f / 1023.0f);
  float temperatureC = tempVoltage * 100.0f;

  // MPU6050 acceleration (m/s^2) + gyroscope (rad/s)
  if (mpu6050Ready) readMPU6050();

  Serial.print(millis()); Serial.print(',');
  Serial.print(latestIR); Serial.print(',');
  Serial.print(latestRed); Serial.print(',');
  Serial.print(heartRateBpm, 1); Serial.print(',');
  Serial.print(ecgRaw); Serial.print(',');
  Serial.print(ecgLeadOff ? 1 : 0); Serial.print(',');
  Serial.print(temperatureC, 2); Serial.print(',');
  Serial.print(accelX, 3); Serial.print(',');
  Serial.print(accelY, 3); Serial.print(',');
  Serial.print(accelZ, 3); Serial.print(',');
  Serial.print(gyroX, 4); Serial.print(',');
  Serial.print(gyroY, 4); Serial.print(',');
  Serial.println(gyroZ, 4);
}
