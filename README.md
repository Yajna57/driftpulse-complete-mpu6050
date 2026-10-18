# DriftPulse — Complete Replacement Project

This is the full Phase-1 replacement for the actual hardware you have:

- Arduino Uno / classic Nano
- MAX30102
- AD8232
- LM35
- MPU6050

**GSR and ADXL345 have been completely removed.**

## Architecture

```text
MAX30102 + AD8232 + LM35 + MPU6050
                |
                v
          Arduino Uno
                |
        USB Serial @ 100 Hz
                |
                v
       Python collector (local)
       + raw CSV logging
       + ECG/HRV processing
       + MPU6050 activity context
                |
          1 summary/sec
                v
         FastAPI (local)
                |
     Baseline + Z + EWMA + CUSUM
                |
                v
        PostgreSQL (Docker only)
                |
                v
       React frontend (local)
```

## Quick start on Windows / Python 3.14

```powershell
# project root
docker compose up -d

cd python
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
Copy-Item .env.example .env
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal, test software first:

```powershell
cd python
.\.venv\Scripts\Activate.ps1
python -m scripts.simulate_data --list      # 10 cases: 3 normal (1, 9, 10), fever, all abnormal,
python -m scripts.simulate_data --case 1    # sensor faults, running, sleeping, heart attack, head spin
```

Each case runs for USER001 and USER002 at the same time. See `docs/SIMULATION.md`.

Frontend:

First time only

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

On third terminal Run frontend usally
```
cd frontend
npm run dev
```

Real Arduino collector:

```powershell
cd python
.\.venv\Scripts\Activate.ps1
python -m serial.tools.list_ports
python -m collector.serial_collector --port COM3 --user USER001
```

Then open `http://localhost:5173` and choose the same user (e.g. `USER001`) in the **User** dropdown.
The top panel shows whether data is arriving and the status of each sensor; below it is the live
ECG waveform. If a sensor shows a problem, see `docs/SETUP.md` section 7c.

See:

- `docs/HARDWARE.md` — wiring/pins and safety
- `docs/SETUP.md` — detailed Python 3.14/Docker/frontend setup
- `docs/ALGORITHMS.md` — HRV, baseline, EWMA/CUSUM and motion context
- `docs/API.md` — backend endpoints
- `docs/SIMULATION.md` — the 10 simulated test cases

## Important

The output is a personalized physiological-deviation/risk score for an educational prototype. It is not a disease probability and is not a medical diagnosis.
