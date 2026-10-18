import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, DEFAULT_USER_ID } from './api'
import { DevicePanel } from './components/DevicePanel'
import { EcgChart } from './components/EcgChart'
import { MetricCard } from './components/MetricCard'
import { StatusCard } from './components/StatusCard'
import { TrendChart } from './components/TrendChart'
import type { AlertItem, BaselineResponse, HealthStatus, LiveState, Reading, UserItem } from './types'
import './styles.css'

const fmt = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toFixed(digits)

function initialUserId() {
  try {
    return localStorage.getItem('driftpulse.userId') || DEFAULT_USER_ID
  } catch {
    return DEFAULT_USER_ID
  }
}

function App() {
  const [userId, setUserId] = useState(initialUserId)
  const [users, setUsers] = useState<UserItem[]>([])
  const [live, setLive] = useState<LiveState | null>(null)
  const [latest, setLatest] = useState<Reading | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [history, setHistory] = useState<Reading[]>([])
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([
      api.latest(userId), api.health(userId), api.history(userId), api.baseline(userId), api.alerts(userId), api.users(),
    ])
    if (results[0].status === 'fulfilled') setLatest(results[0].value)
    if (results[1].status === 'fulfilled') setHealth(results[1].value)
    if (results[2].status === 'fulfilled') setHistory(results[2].value)
    if (results[3].status === 'fulfilled') setBaseline(results[3].value)
    if (results[4].status === 'fulfilled') setAlerts(results[4].value)
    if (results[5].status === 'fulfilled') setUsers(results[5].value)
    if (results[5].status === 'rejected') {
      setError('Cannot reach the backend API. Is uvicorn running on port 8000?')
    } else if (results[0].status === 'rejected') {
      setError(`No readings stored for ${userId} yet. Start the collector with --user ${userId}, or pick another user.`)
    } else {
      setError(null)
    }
  }, [userId])

  const refreshLive = useCallback(async () => {
    try {
      setLive(await api.live(userId))
    } catch {
      setLive(null)
    }
  }, [userId])

  useEffect(() => {
    setLatest(null); setHealth(null); setHistory([]); setBaseline(null); setAlerts([]); setLive(null)
    try { localStorage.setItem('driftpulse.userId', userId) } catch { /* storage unavailable */ }
    void refresh()
    void refreshLive()
    const slow = window.setInterval(() => void refresh(), 2000)
    const fast = window.setInterval(() => void refreshLive(), 1000)
    return () => { window.clearInterval(slow); window.clearInterval(fast) }
  }, [userId, refresh, refreshLive])

  const userOptions = useMemo(() => {
    const ids = users.map((u) => u.user_id)
    return ids.includes(userId) ? ids : [userId, ...ids]
  }, [users, userId])

  const baselineProgress = useMemo(() => {
    const values = Object.values(baseline?.metrics ?? {})
    if (!values.length) return 0
    const target = Math.max(baseline?.required_samples ?? 60, 1)
    return Math.round(values.reduce((s, r) => s + Math.min(r.sample_count / target, 1), 0) / values.length * 100)
  }, [baseline])

  async function resetBaseline() {
    if (!window.confirm('Reset the learned baseline and drift state? Raw reading history is kept.')) return
    await api.resetBaseline(userId)
    await refresh()
  }

  return (
    <main className="page-shell">
      <header className="app-header">
        <div><span className="eyebrow">College Project · Phase 1</span><h1>DriftPulse</h1><p>AD8232 + MAX30102 + LM35 + MPU6050</p></div>
        <div className="header-actions">
          <label className="user-select">
            <span>User</span>
            <select value={userId} onChange={(e) => setUserId(e.target.value)}>
              {userOptions.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
          </label>
          <button className="secondary-button" onClick={resetBaseline}>Reset baseline</button>
        </div>
      </header>

      {error ? <div className="notice">{error}</div> : null}
      <DevicePanel live={live} latest={latest} />
      <StatusCard health={health} />

      {!health?.baseline_ready ? (
        <section className="baseline-progress">
          <div><strong>Personalized baseline calibration</strong><span>{baselineProgress}%</span></div>
          <div className="progress-track"><div className="progress-fill" style={{ width: `${baselineProgress}%` }} /></div>
          <p>Remain reasonably still while initial HR/HRV/temperature values are collected.</p>
        </section>
      ) : null}

      <section className="metrics-grid">
        <MetricCard label="Heart rate (ECG / PPG)" value={`${fmt(latest?.heart_rate_bpm)} bpm`} helper="ECG-derived when HRV is available" />
        <MetricCard label="RMSSD (ECG HRV)" value={`${fmt(latest?.rmssd_ms)} ms`} />
        <MetricCard label="SDNN (ECG HRV)" value={`${fmt(latest?.sdnn_ms)} ms`} />
        <MetricCard label="Body temperature (LM35)" value={`${fmt(latest?.temperature_c, 2)} °C`} />
        <MetricCard label="Movement (MPU6050)" value={latest?.activity ?? '—'} helper="Accelerometer + gyroscope context" />
        <MetricCard label="ECG electrodes (AD8232)" value={latest ? (latest.ecg_lead_off ? 'OFF / CHECK' : 'CONNECTED') : '—'} />
      </section>

      <EcgChart live={live} />

      <section className="charts-grid">
        <TrendChart title="Heart rate (ECG / PPG)" data={history} dataKey="heart_rate_bpm" unit="bpm" />
        <TrendChart title="RMSSD (ECG HRV)" data={history} dataKey="rmssd_ms" unit="ms" />
        <TrendChart title="SDNN (ECG HRV)" data={history} dataKey="sdnn_ms" unit="ms" />
        <TrendChart title="Body temperature (LM35)" data={history} dataKey="temperature_c" unit="°C" />
      </section>

      <div className="section-heading"><h2>MAX30102 optical signal</h2><span>1-second trend</span></div>
      <section className="charts-grid">
        <TrendChart title="Infrared signal (MAX30102)" data={history} dataKey="ppg_ir" unit="ADC counts" />
        <TrendChart title="Red signal (MAX30102)" data={history} dataKey="ppg_red" unit="ADC counts" />
      </section>

      <div className="section-heading"><h2>MPU6050 motion data</h2><span>6 axes</span></div>
      <section className="charts-grid">
        <TrendChart title="Acceleration X (MPU6050)" data={history} dataKey="accel_x_ms2" unit="m/s²" />
        <TrendChart title="Acceleration Y (MPU6050)" data={history} dataKey="accel_y_ms2" unit="m/s²" />
        <TrendChart title="Acceleration Z (MPU6050)" data={history} dataKey="accel_z_ms2" unit="m/s²" />
        <TrendChart title="Gyroscope X (MPU6050)" data={history} dataKey="gyro_x_rads" unit="rad/s" />
        <TrendChart title="Gyroscope Y (MPU6050)" data={history} dataKey="gyro_y_rads" unit="rad/s" />
        <TrendChart title="Gyroscope Z (MPU6050)" data={history} dataKey="gyro_z_rads" unit="rad/s" />
      </section>

      <section className="details-grid">
        <article className="panel">
          <div className="section-heading"><h3>Current observations</h3></div>
          <ul className="observations">{(health?.observations ?? ['Waiting for analysis.']).map((o) => <li key={o}>{o}</li>)}</ul>
        </article>
        <article className="panel">
          <div className="section-heading"><h3>Personalized baseline</h3></div>
          <div className="baseline-table">{Object.entries(baseline?.metrics ?? {}).map(([name, m]) => (
            <div className="baseline-row" key={name}><span>{name.replaceAll('_', ' ')}</span><strong>{m.mean.toFixed(2)} ± {m.std.toFixed(2)}</strong><small>{m.sample_count} samples</small></div>
          ))}</div>
        </article>
        <article className="panel panel-wide">
          <div className="section-heading"><h3>Recent alerts</h3><span>{alerts.length}</span></div>
          {alerts.length === 0 ? <p className="muted">No alerts recorded.</p> : <div className="alert-list">{alerts.slice(0, 8).map((a) => (
            <div className="alert-row" key={a.id}><strong>{a.severity}</strong><span>{a.message}</span><time>{new Date(a.created_at).toLocaleString()}</time></div>
          ))}</div>}
        </article>
      </section>

      <footer>Educational prototype only. DriftPulse detects changes from a personalized sensor baseline and does not diagnose disease.</footer>
    </main>
  )
}

export default App
