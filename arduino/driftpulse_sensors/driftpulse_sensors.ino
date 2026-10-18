#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// DriftPulse Phase 1
// Hardware: Arduino Uno/Nano + MAX30102 + AD8232 + LM35 + MPU6050
// Serial output: CSV @ ~100 Hz, 230400 baud

const uint8_t ECG_PIN = A0;
const uint8_t TEMP_PIN = A1;
const uint8_t ECG_LO_PLUS_PIN = 8;
const uint8_t ECG_LO_MINUS_PIN = 9;

const unsigned long SAMPLE_PERIOD_US = 10000UL; // 100 Hz
unsigned long nextSampleUs = 0;

MAX30105 max30102;
Adafruit_MPU6050 mpu6050;

uint32_t latestIR = 0;
uint32_t latestRed = 0;
unsigned long lastBeatMs = 0;
float heartRateBpm = 0.0f;
bool max30102Ready = false;
bool mpu6050Ready = false;

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

bool setupMPU6050() {
  if (!mpu6050.begin()) {
    return false;
  }

  mpu6050.setAccelerometerRange(MPU6050_RANGE_4_G);
  mpu6050.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu6050.setFilterBandwidth(MPU6050_BAND_21_HZ);
  return true;
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
  Serial.begin(230400);
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
    Wire.begin();
#if defined(WIRE_HAS_TIMEOUT)
    Wire.setWireTimeout(3000 /* us */, true /* reset bus on timeout */);
#endif
    max30102Ready = i2cDevicePresent(0x57) && setupMAX30102();
    if (!max30102Ready) Serial.println("ERROR:MAX30102_NOT_FOUND");
    mpu6050Ready = i2cDevicePresent(0x68) && setupMPU6050();
    if (!mpu6050Ready) Serial.println("ERROR:MPU6050_NOT_FOUND");
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

void loop() {
  updateMAX30102();

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
  sensors_event_t accelEvent = {};
  sensors_event_t gyroEvent = {};
  sensors_event_t mpuTempEvent = {};
  if (mpu6050Ready) {
    mpu6050.getEvent(&accelEvent, &gyroEvent, &mpuTempEvent);
  }

  Serial.print(millis()); Serial.print(',');
  Serial.print(latestIR); Serial.print(',');
  Serial.print(latestRed); Serial.print(',');
  Serial.print(heartRateBpm, 1); Serial.print(',');
  Serial.print(ecgRaw); Serial.print(',');
  Serial.print(ecgLeadOff ? 1 : 0); Serial.print(',');
  Serial.print(temperatureC, 2); Serial.print(',');
  Serial.print(accelEvent.acceleration.x, 3); Serial.print(',');
  Serial.print(accelEvent.acceleration.y, 3); Serial.print(',');
  Serial.print(accelEvent.acceleration.z, 3); Serial.print(',');
  Serial.print(gyroEvent.gyro.x, 4); Serial.print(',');
  Serial.print(gyroEvent.gyro.y, 4); Serial.print(',');
  Serial.println(gyroEvent.gyro.z, 4);
}
