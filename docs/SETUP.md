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
python -m scripts.simulate_data --user USER001 --seconds 180 --drift-after 100
```

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

## 8. Replacing an older database schema

If your old local database was created using the earlier GSR/ADXL345 schema and you do not need its test data, easiest is:

```powershell
docker compose down -v
docker compose up -d
```

`down -v` permanently deletes the existing PostgreSQL volume. Do not run it if you need to preserve old data; use a database migration instead.
