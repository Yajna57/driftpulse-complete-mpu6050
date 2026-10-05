# Hardware and Pin Connections

This replacement project uses exactly these four sensors:

- MAX30102 — optical PPG / pulse
- AD8232 — ECG, used for RR intervals and HRV
- LM35 — temperature trend
- MPU6050 — accelerometer + gyroscope, used as movement context

There is **no GSR sensor** in this version.

## Arduino Uno / classic Nano pins

| Sensor | Pin | Arduino |
|---|---|---|
| MAX30102 | SDA | A4 / SDA |
| MAX30102 | SCL | A5 / SCL |
| MAX30102 | VCC/VIN | Follow exact breakout rating; 3.3 V is safest for non-5V-safe boards |
| MAX30102 | GND | GND |
| MPU6050 (common GY-521) | SDA | A4 / SDA |
| MPU6050 (common GY-521) | SCL | A5 / SCL |
| MPU6050 (common GY-521) | VCC | 5 V is common for GY-521; verify your board |
| MPU6050 | GND | GND |
| MPU6050 | AD0 | GND (normally address 0x68) |
| MPU6050 | INT | Not used |
| AD8232 | OUTPUT | A0 |
| AD8232 | LO+ | D8 |
| AD8232 | LO- | D9 |
| AD8232 | 3.3V | 3.3 V |
| AD8232 | GND | GND |
| LM35 | VCC | 5 V |
| LM35 | OUT | A1 |
| LM35 | GND | GND |

## Shared I2C

```text
Arduino A4/SDA ----+---- MAX30102 SDA
                   +---- MPU6050 SDA

Arduino A5/SCL ----+---- MAX30102 SCL
                   +---- MPU6050 SCL
```

MAX30102 and MPU6050 can share I2C because they use different addresses.

## Important voltage warning

The bare MAX30102 is not a 5 V logic device. Breakout boards vary. If your MAX30102 module is not explicitly Arduino/5V-I2C compatible, use a proper bidirectional I2C level shifter rather than exposing its SDA/SCL to 5 V pull-ups. Always check the exact module markings/specification.

## AD8232 safety

The ECG module is body-connected. For a college prototype, use a battery-powered laptop while electrodes are attached, disconnect the charger from mains, and preferably use appropriate USB isolation. Do not use this setup for medical diagnosis.

## Arduino IDE libraries

Install with Library Manager:

- SparkFun MAX3010x Pulse and Proximity Sensor Library
- Adafruit MPU6050
- Adafruit Unified Sensor

`Wire` is built into Arduino.
