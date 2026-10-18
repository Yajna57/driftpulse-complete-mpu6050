# Simulation (no hardware needed)

`python/scripts/simulate_data.py` sends realistic collector-style data to the backend, so the
whole system (backend, risk engine, dashboard) can be tested and demonstrated without the Arduino.
The case definitions live in `python/scripts/scenarios.py`.

## Run

Backend and frontend must be running (see SETUP.md steps 4 and 6). Then, in a venv terminal:

```powershell
cd python
.\.venv\Scripts\Activate.ps1

python -m scripts.simulate_data --list          # show all cases
python -m scripts.simulate_data --case 1        # run case 1 for USER001 and USER002 together
```

Open `http://localhost:5173` and pick **USER001** or **USER002** in the **User** dropdown.
The device panel shows `SIM-CASE<n>` as the device, so you can see which case is running.

| Command | Case |
|---|---|
| `python -m scripts.simulate_data --case 1` | Normal healthy user |
| `python -m scripts.simulate_data --case 2` | Temperature problem (fever) |
| `python -m scripts.simulate_data --case 3` | All vitals abnormal |
| `python -m scripts.simulate_data --case 4` | Each sensor reading wrong, one at a time |
| `python -m scripts.simulate_data --case 5` | Running |
| `python -m scripts.simulate_data --case 6` | Sleeping |
| `python -m scripts.simulate_data --case 7` | Heart attack pattern |
| `python -m scripts.simulate_data --case 8` | Head spin / dizziness |

### Options

| Option | Default | Meaning |
|---|---|---|
| `--case N` | required | Case number 1-8. |
| `--users A,B` | `USER001,USER002` | Users to simulate, in parallel. Any other ID reuses one of the two profiles. |
| `--speed X` | `1` | `1` = real time (1 reading per second). `5` runs five times faster. |
| `--no-reset` | off | Keep the learned baseline. If it is already complete, calibration is skipped. |
| `--no-save` | off | Do not write the CSV file. |
| `--api URL` | `http://127.0.0.1:8000` | Backend address. |

Examples:

```powershell
python -m scripts.simulate_data --case 7 --speed 3              # faster demo
python -m scripts.simulate_data --case 5 --users USER002        # one user only
python -m scripts.simulate_data --case 2 --no-reset             # reuse the baseline from the last run
```

Stop any run with **Ctrl+C**.

## How a run works

1. **Reset.** By default each run resets the user's baseline, drift state, analyses and alerts
   (`POST /reset-baseline`). Stored readings are kept, so older runs still appear in the history charts.
2. **Calibration (70 readings).** Normal values for that user. The status shows `CALIBRATING` until
   60 valid readings of heart rate, RMSSD, SDNN and temperature are collected.
3. **Scenario phases.** Values move smoothly (ramp) from one phase to the next. The terminal prints a
   line per reading and a `--- phase: ... ---` header when the phase changes.

Each reading includes everything the real collector sends: heart rate, HRV, temperature, PPG,
6-axis MPU6050 values, activity (computed with the same `core/activity.py` as the real collector),
1 second of synthetic ECG waveform (100 samples) and the per-sensor status.

## The two users

Values in each case are relative to the user's own baseline, so the same case gives the same
pattern for both users at different absolute numbers.

| User | Profile | Resting HR | RMSSD | SDNN | Temperature |
|---|---|---|---|---|---|
| USER001 | Young active adult | 64 bpm | 55 ms | 60 ms | 36.50 C |
| USER002 | Middle-aged adult | 76 bpm | 32 ms | 40 ms | 36.70 C |

## Cases

Durations are at `--speed 1` and include the 70 s calibration. "Result" is what the current risk
engine produced when each case was run.

### 1. Normal healthy user (220 s)
Seated at rest, all sensors OK, values stay near baseline.
**Result:** CALIBRATING, then NORMAL for the whole run (risk 0-10).

### 2. Temperature problem / fever (250 s)
Normal 30 s, then temperature rises +1.9 C over 90 s and stays high for 60 s. Heart rate rises with it
(+22 %, about 10 bpm per C) and HRV drops slightly, as in a real fever.
**Result:** NORMAL, then OBSERVATION and ELEVATED while the fever rises, ALERT on the plateau.
Alerts are recorded.

### 3. All vitals abnormal (190 s)
Over 40 s: heart rate +40 %, RMSSD -55 %, SDNN -45 %, temperature +1.3 C, at rest.
**Result:** climbs to ALERT (risk 100). Alerts are recorded.

### 4. Each sensor reading wrong (205 s)
Vitals stay normal. Each sensor fails for 25 s, one at a time:

| Phase | What the dashboard shows |
|---|---|
| AD8232 leads off | AD8232 chip "Leads off", ECG waveform says electrodes disconnected, RMSSD/SDNN missing; heart rate falls back to the MAX30102 value |
| MAX30102 no finger | MAX30102 chip "No finger" (IR about 14000) |
| LM35 bad reading | LM35 chip "Bad reading" (reads about 163 C, the same fault seen on the real hardware); temperature missing |
| MPU6050 not detected | MPU6050 chip "Not detected", Movement UNKNOWN, motion charts gap |

**Result:** status stays NORMAL. Missing values are skipped, not scored as abnormal.

### 5. Running (250 s)
Rest 20 s, warm-up walk 30 s, running 90 s (heart rate about 2x, HRV very low, temperature +0.7 C,
ECG with motion noise), cool-down walk 40 s.
**Result:** Movement MODERATE (walk) and HIGH (run). The engine subtracts 20 points for HIGH activity,
but the deviation is so large that status still reaches ALERT and stays there through cool-down.

### 6. Sleeping (250 s)
Lying still (MPU6050 shows gravity on the X axis). Falls asleep over 40 s: heart rate -18 %, RMSSD +40 %,
SDNN +30 %, skin temperature -0.3 C.
**Result:** Movement RESTING. Status OBSERVATION (risk about 28) during sleep. Low heart rate scores only
a little, but drift detection is two-sided, so the sustained drop is still reported.

### 7. Heart attack pattern (210 s)
Resting 30 s, then a sudden event at rest: heart rate +65 % with irregular beats, RMSSD -70 %,
SDNN -55 %. The live ECG waveform shows **ST-segment elevation** and occasional wide premature beats.
No movement explains the change.
**Result:** ALERT within about 15 s of onset (risk 85-100). Alerts are recorded.
This is a teaching pattern only; DriftPulse cannot diagnose a heart attack.

### 8. Head spin / dizziness (225 s)
Steady 20 s, head spinning 45 s (gyroscope Z about 4.5 rad/s), dizzy swaying 60 s, recovery 30 s.
Heart rate +25 % and HRV -30 % during the episode, ECG with motion noise while spinning.
**Result:** gyroscope charts spike. While spinning, Movement is HIGH and the activity discount keeps the
status at ELEVATED. Swaying is only MODERATE, so status reaches ALERT; it returns to NORMAL after recovery.

## Saved data

Each run writes one CSV per user to `python/local_logs/simulated/`, named
`case<N>_<name>_<USER>_<date>_<time>.csv`, for example `case7_heart-attack_USER001_2026-10-18_18-05-00.csv`.

Columns: `captured_at, elapsed_s, phase, heart_rate_bpm, rmssd_ms, sdnn_ms, temperature_c, activity,
ecg_lead_off, ppg_ir, accel_z_ms2, gyro_z_rads, status, risk_score`.

The same readings are also stored in PostgreSQL like real Arduino data.

## Adding a case

Add an entry to `CASES` in `python/scripts/scenarios.py`: a list of `Phase(...)` objects. Phase values
are multipliers of the user's baseline (`hr`, `rmssd`, `sdnn`), a temperature offset (`temp`), a `ramp`
in seconds, a `motion` type (`sit`, `lying`, `walk`, `run`, `spin`, `sway`), an `ecg` style
(`normal`, `noisy`, `infarct`) and optional sensor `faults`.
