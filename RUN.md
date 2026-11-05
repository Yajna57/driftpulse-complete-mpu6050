# RUN.md

Run every command from the project root (`driftpulse-complete-mpu6050/`), in PowerShell.
Each command works two ways: `scripts\name` or `npm run name`.

---

## A. First time only

```powershell
scripts\setup
```

Wait for `Setup done`. Docker Desktop must be running.

---

## B. Get data from the real sensor (Arduino)

1. Plug in the Arduino. In Arduino IDE, close **Serial Monitor** and **Serial Plotter** (the COM port can be used by one program only).
2. Start everything:

```powershell
scripts\start
```

3. Collect sensor data:

```powershell
scripts\data -Mode sensor
```

4. Answer the prompts: COM port (auto-detected, press Enter to accept) and user ID (e.g. `USER001`).
5. Open `http://localhost:5173`. In the **User** dropdown (top right) pick the same user ID.
6. Stop collecting with `Ctrl+C`.

One line, no prompts:

```powershell
scripts\data -Mode sensor -User USER001 -Port COM3
```

---

## C. Get simulation data (no hardware)

1. Start everything (skip if already running):

```powershell
scripts\start
```

2. Run a simulation:

```powershell
scripts\data -Mode sim
```

3. Answer the prompts: case number (1-10, or `all`) and users (default `USER001,USER002`).
4. Open `http://localhost:5173`. Pick one of those users in the **User** dropdown.
5. Run `scripts\data -Mode sim` again as many times as you want. Each run can use a different case.

One line, no prompts:

```powershell
scripts\data -Mode sim -Case 7 -Users USER001,USER002
```

List the 10 cases:

```powershell
scripts\data -Mode sim -List
```

---

## D. Stop / restart

```powershell
scripts\stop      # closes the backend + frontend tabs (Docker keeps running, data kept)
scripts\start     # restart fresh: closes old tabs, opens new ones
```

---

## E. Cheat sheet

| Goal | Command |
|---|---|
| Install everything (once) | `scripts\setup` |
| Start Docker + backend + frontend | `scripts\start` |
| Sensor data | `scripts\data -Mode sensor` |
| Simulation data | `scripts\data -Mode sim` |
| Menu (asks sensor or sim) | `scripts\data` |
| Stop backend + frontend tabs | `scripts\stop` |

npm equivalents: `npm run setup`, `npm start`, `npm run data`, `npm run sim`, `npm run sensor`, `npm stop`.
Extra options go after `--`, e.g. `npm run sim -- -Case 3`.

---

# How the scripts work

## Files

```
package.json          npm shortcuts (setup, start, stop, data, sim, sensor)
scripts/
  setup.cmd           wrapper -> setup.ps1
  start.cmd           wrapper -> start-all.ps1
  stop.cmd            wrapper -> stop-all.ps1
  data.cmd            wrapper -> run-data.ps1
  setup.ps1           one-time install
  start-all.ps1       Docker + backend + frontend
  stop-all.ps1        close backend + frontend tabs
  run-data.ps1        sensor or simulation data
  _common.ps1         shared helpers (paths, backend check, kill helpers)
  .pids               shell PIDs saved by start (auto-created, git-ignored)
```

### The `.cmd` wrappers
Each one runs `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script>.ps1 %*`. This avoids the PowerShell execution-policy block. All arguments you type are passed on to the `.ps1` file.

The scripts never start `uvicorn.exe` or other pip-made `.exe` launchers. Windows Application Control blocks those. They run `python -m uvicorn` from the project venv instead.

### `_common.ps1`
Shared by all scripts. It sets the paths (`python/`, `frontend/`, `python/.venv`), the API address (`http://127.0.0.1:8000`) and these helpers:
- `Test-Backend`: asks `http://127.0.0.1:8000/docs`, true if it answers.
- `Assert-Venv`: stops with a clear message if `python\.venv` is missing (run `setup`).
- `Stop-Tree`: kills a process and its children with `taskkill /T /F` (needed because `uvicorn --reload` spawns a child).
- `Stop-Port`: kills whatever listens on a TCP port.

### `setup.ps1`
1. Checks `docker`, `node`, `npm`, `py` and `py -3.14`.
2. Creates `python/.venv` if missing.
3. Runs `python -m pip install` for `python/requirements.txt`.
4. Copies `.env.example` to `.env` in `python/` and `frontend/`. An existing `.env` is never overwritten.
5. Runs `npm install` in `frontend/` if `node_modules` is missing.

Safe to run again. Finished steps are skipped.

### `start-all.ps1`
1. Runs `stop-all.ps1` to close old tabs from a previous run.
2. Runs `docker compose up -d` and waits until the `driftpulse-postgres` container is healthy. The database volume is kept, so data stays.
3. Opens a **Backend** tab in a Windows Terminal window named `driftpulse` (separate window if `wt` is missing): `python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000` in `python/`.
4. Opens a **Frontend** tab: `npm run dev` in `frontend/`.
5. Each tab saves its shell PID in `scripts/.pids`.
6. Waits up to 60 s for the backend, then prints the URLs.

Options: `-NoFrontend` (skip the dashboard), `-NoDocker` (skip Docker).

### `stop-all.ps1`
Reads `scripts/.pids`, kills only the processes those shells started (uvicorn, npm). Each shell then exits and its tab closes by itself. Then it frees ports 8000 and 5173 in case anything was left. Docker is not touched.

### `run-data.ps1`
First it checks that the backend answers. If not, it stops and tells you to run `start`. It asks for anything you did not pass as an option.

**Sensor mode**
1. Lists COM ports with `python -m serial.tools.list_ports`.
2. One port: uses it. Several: you choose, and the default is the one named Arduino/CH340/USB Serial. None: stops with an error.
3. Asks for the user ID (default `USER001`).
3b. Tests that the COM port is free. If it is busy it stops an old collector by itself and offers to stop `serial-monitor` (Arduino IDE) or PuTTY. If the port is still busy it stops with an error.
4. Opens a **new tab** that runs `python -m collector.serial_collector --port <COM> --user <USER> --api http://127.0.0.1:8000`. The current terminal prints which user to pick in the dashboard.

**Simulation mode**
1. Shows the case list, then asks for the case (1-10 or `all`) and the users.
2. Runs `python -m scripts.simulate_data --case <N> --users <list> --speed <S> --api http://127.0.0.1:8000`.
3. `all` runs cases 1 to 10 one after another.
4. Opens the run in a **new tab** that stays open after the run ends, so you can read the output. Repeat as often as you like, each run gets its own tab.

Options:

| Option | Meaning |
|---|---|
| `-Mode sensor` / `-Mode sim` | choose the data source |
| `-Case 7` / `-Case all` | simulation case |
| `-Users USER001,USER002` | simulation users |
| `-User USER004` | sensor user |
| `-Port COM3` | skip COM port detection |
| `-Speed 5` | simulation runs 5x faster |
| `-NoReset` | keep the old data of the users |
| `-NoSave` | do not write the per-run CSV |
| `-List` | list the simulation cases and exit |
| `-Here` | run in this terminal instead of a new tab |

The questions are asked in the terminal where you typed the command. The run itself then opens in a new tab.

Simulation CSVs are saved in `python/local_logs/simulated/`. Sensor CSVs are saved in `python/local_logs/`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Backend not reachable` | Run `scripts\start` first. Check the Backend tab for errors. |
| `python\.venv not found` | Run `scripts\setup`. |
| `docker compose failed` | Start Docker Desktop and run `scripts\start` again. |
| `No COM port found` | Plug in the Arduino, close Serial Monitor, run again. Or pass `-Port COM3`. |
| `could not open port COM3 ... Access is denied` | Another program holds the port, almost always Arduino IDE **Serial Monitor** (or Serial Plotter). Close it, or answer `y` when `data` offers to stop it. Also stop any older sensor tab (Ctrl+C). If still busy, unplug and replug the USB cable. |
| Dashboard shows no data | Pick the same user in the **User** dropdown as the one you run. |
| `uvicorn.exe` blocked | Do not run it directly. Use `scripts\start`. |
