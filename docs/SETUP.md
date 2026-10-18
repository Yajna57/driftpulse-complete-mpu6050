# Complete Windows Setup — Python 3.14

This version is prepared for **Python 3.14**. Only PostgreSQL is run in Docker.

## 1. Verify Python 3.14

```powershell
py -3.14 --version
```

## 2. Start PostgreSQL

From project root:

```powershell
docker compose up -d
docker compose ps
```

## 3. Create Python 3.14 venv

```powershell
cd python
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip setuptools wheel
Copy-Item .env.example .env
python -m pip install -r requirements.txt
```

The requirements use Python-3.14-capable Pydantic/Psycopg/NumPy/SciPy releases to avoid the earlier `pydantic-core` Rust source-build and old psycopg wheel problem.

## 4. Run backend

From `python/` with venv active:

```powershell
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/docs`.

## 5. Test without hardware

In another venv terminal:

```powershell
cd python
.\.venv\Scripts\Activate.ps1
python -m scripts.simulate_data --list      # 10 cases: 3 normal (1, 9, 10), fever, all abnormal,
python -m scripts.simulate_data --case 1    # sensor faults, running, sleeping, heart attack, head spin
```

Each case runs for USER001 and USER002 at the same time. See `docs/SIMULATION.md`.

## 6. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`.

## 7. Arduino

Upload `arduino/driftpulse_sensors/driftpulse_sensors.ino` after installing the required Arduino libraries. Serial speed is 230400 baud.

Find the port:

```powershell
cd python
.\.venv\Scripts\Activate.ps1
python -m serial.tools.list_ports
```

Then run, for example:

```powershell
python -m collector.serial_collector --port COM3 --user USER001
```

Do not leave Arduino Serial Monitor open while Python uses the COM port.

## 7b. Seeing Arduino data in the dashboard

Data flow: Arduino (100 Hz CSV over USB) -> `collector.serial_collector` (HRV, activity, raw CSV in
`python/local_logs/`) -> `POST /api/v1/readings` once per second -> PostgreSQL -> React dashboard
(polls every 1-2 s).

You need three things running: the backend (step 4), the frontend (step 6) and the collector.

1. Start the collector with a user ID, e.g. `--user USER004`.
2. In the dashboard, pick the **same user** in the **User** dropdown (top right). The dropdown lists
   every user that has readings. The choice is remembered in the browser; `VITE_USER_ID` in
   `frontend/.env` is only the first-visit default.
3. The **device panel** at the top shows:
   - green dot "Receiving data": the collector is posting right now; grey/orange: nothing new.
   - one chip per sensor (AD8232, MAX30102, LM35, MPU6050) with `OK` or the problem and a wiring hint.
4. The **Live ECG waveform** shows the last 10 s of raw AD8232 samples.

The collector terminal also prints `CHECK <sensor>:<state>` at the end of each line when a sensor is not OK.

## 7c. Hardware troubleshooting (what the raw CSV tells you)

Open the newest file in `python/local_logs/`:

| Symptom in CSV | Dashboard chip | Likely cause |
|---|---|---|
| Collector shows `Arduino: ERROR:I2C_BUS_STUCK_LOW` | MAX30102 + MPU6050 Not detected | SDA/SCL are held at 0 V. Usually a module on the I2C bus has **no power** (an unpowered MPU6050/MAX30102 clamps SDA/SCL low), e.g. the 5V rail is not connected or the breadboard rail is split in the middle. Otherwise SDA/SCL are in a GND row. Check the GY-521 power LED is lit and the 5V rail reads ~5 V. Upload `arduino/i2c_scanner` to test: it should print `SDA(A4)=HIGH SCL(A5)=HIGH` and `FOUND 0x57` / `FOUND 0x68`. |
| `ecg_raw` and `temperature_c` raw values track each other (e.g. ECG 335 and temp 163 C) | LM35 Bad reading | A1 is floating and copies the A0 voltage. LM35 has no power or Vout is not on A1. |
| CSV has only the header row | "No data yet" | Wrong COM port, Serial Monitor still open, sketch not uploaded, or wrong baud. The sketch now prints `INFO:DRIFTPULSE_BOOT` at start-up; if the collector never shows it, nothing is arriving from the Arduino. |
| `max30102_ir` and `max30102_red` always 0 | MAX30102 Not detected | MAX30102 not found on I2C: check SDA->A4, SCL->A5, VIN, GND, and the level-shifting warning in HARDWARE.md. |
| IR > 0 but < 50000 | MAX30102 No finger | Sensor works; place your fingertip on it and keep still. |
| all `accel_*`/`gyro_*` exactly 0 | MPU6050 Not detected | MPU6050 not found on I2C: same SDA/SCL wiring, VCC, GND, AD0->GND. |
| `ecg_lead_off` always 1 | AD8232 Leads off | Electrodes not attached / dry, or LO+->D8, LO-->D9 miswired. HRV (RMSSD/SDNN) cannot be computed, so the baseline will stay in CALIBRATING. |
| `temperature_c` > 60 (e.g. 160-190) or jumping | LM35 Bad reading | A1 is floating or LM35 pins reversed: flat side facing you, pins left-to-right are VCC(5 V), OUT->A1, GND. |

The sketch checks that SDA/SCL are HIGH before using I2C and sets an I2C timeout, so a badly wired
I2C bus no longer freezes the Arduino (which previously produced a CSV with only the header). ECG and
temperature keep streaming and the I2C sensors are reported as not detected.

Baseline note: status leaves `CALIBRATING` only after all four baseline metrics (HR, RMSSD, SDNN,
temperature) have 60 valid samples, so a working AD8232 and LM35 are required.

## 8. Replacing an older database schema

If your old local database was created using the earlier GSR/ADXL345 schema and you do not need its test data, easiest is:

```powershell
docker compose down -v
docker compose up -d
```

`down -v` permanently deletes the existing PostgreSQL volume. Do not run it if you need to preserve old data; use a database migration instead.
