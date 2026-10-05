import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, USER_ID } from './api'
import { MetricCard } from './components/MetricCard'
import { StatusCard } from './components/StatusCard'
import { TrendChart } from './components/TrendChart'
import type { AlertItem, BaselineResponse, HealthStatus, Reading } from './types'
import './styles.css'

const fmt = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toFixed(digits)

function App() {
  const [latest, setLatest] = useState<Reading | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [history, setHistory] = useState<Reading[]>([])
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([
      api.latest(), api.health(), api.history(), api.baseline(), api.alerts(),
    ])
    if (results[0].status === 'fulfilled') setLatest(results[0].value)
    if (results[1].status === 'fulfilled') setHealth(results[1].value)
    if (results[2].status === 'fulfilled') setHistory(results[2].value)
    if (results[3].status === 'fulfilled') setBaseline(results[3].value)
    if (results[4].status === 'fulfilled') setAlerts(results[4].value)
    setError(results.some((r) => r.status === 'rejected') ? 'Waiting for some backend/sensor data.' : null)
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const baselineProgress = useMemo(() => {
    const values = Object.values(baseline?.metrics ?? {})
    if (!values.length) return 0
    const target = Math.max(baseline?.required_samples ?? 60, 1)
    return Math.round(values.reduce((s, r) => s + Math.min(r.sample_count / target, 1), 0) / values.length * 100)
  }, [baseline])

  async function resetBaseline() {
    if (!window.confirm('Reset the learned baseline and drift state? Raw reading history is kept.')) return
    await api.resetBaseline()
    await refresh()
  }

  return (
    <main className="page-shell">
      <header className="app-header">
        <div><span className="eyebrow">College Project · Phase 1</span><h1>DriftPulse</h1><p>AD8232 + MAX30102 + LM35 + MPU6050 · User {USER_ID}</p></div>
        <button className="secondary-button" onClick={resetBaseline}>Reset baseline</button>
      </header>

      {error ? <div className="notice">{error}</div> : null}
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

      <section className="charts-grid">
        <TrendChart title="Heart rate (ECG / PPG)" data={history} dataKey="heart_rate_bpm" unit="bpm" />
        <TrendChart title="RMSSD (ECG HRV)" data={history} dataKey="rmssd_ms" unit="ms" />
        <TrendChart title="SDNN (ECG HRV)" data={history} dataKey="sdnn_ms" unit="ms" />
        <TrendChart title="Body temperature (LM35)" data={history} dataKey="temperature_c" unit="°C" />
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
