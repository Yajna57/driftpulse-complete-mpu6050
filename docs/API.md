# API

Swagger: `http://127.0.0.1:8000/docs`

Main endpoints:

```text
POST /api/v1/readings
GET  /api/v1/users
GET  /api/v1/users/{user_id}/latest
GET  /api/v1/users/{user_id}/live
GET  /api/v1/users/{user_id}/history?minutes=30&limit=300
GET  /api/v1/users/{user_id}/health-status
GET  /api/v1/users/{user_id}/baseline
GET  /api/v1/users/{user_id}/alerts
POST /api/v1/users/{user_id}/reset-baseline
```

The reading payload contains acceleration and gyroscope values and does not contain GSR.

## Live data (display only)

`POST /api/v1/readings` also accepts these optional fields. They are kept **in memory only**
(not written to PostgreSQL) and are lost when the backend restarts:

| Field | Meaning |
|---|---|
| `ecg_samples` | Raw AD8232 values received since the previous summary (~100 per second). `null` = leads off at that sample. |
| `sample_rate_hz` | Sample rate of `ecg_samples` (default 100). |
| `sensor_status` | Per-sensor state, e.g. `{"LM35": {"state": "OUT_OF_RANGE", "detail": "reads 163.7 C; ..."}}` |
| `arduino_messages` | `ERROR:`/`WARN:` lines printed by the sketch at boot. |

Sensor states: `OK`, `NO_CONTACT` (MAX30102 IR below finger threshold), `NOT_DETECTED`
(I2C sensor sends zeros / reported missing), `LEADS_OFF` (AD8232), `OUT_OF_RANGE` (LM35 outside 0–60 °C).

`GET /api/v1/users/{user_id}/live` returns the last 10 s of ECG samples, the latest sensor status,
`connected` (true if data arrived in the last 5 s) and `seconds_since_last`.

`GET /api/v1/users` lists every user that has stored readings, newest first. The dashboard uses it
for the user selector.
