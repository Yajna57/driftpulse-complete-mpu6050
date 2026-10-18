import type { LiveState, Reading } from '../types'

const SENSORS: { key: string; role: string }[] = [
  { key: 'AD8232', role: 'ECG / HRV' },
  { key: 'MAX30102', role: 'PPG pulse' },
  { key: 'LM35', role: 'Temperature' },
  { key: 'MPU6050', role: 'Motion' },
]

const LABELS: Record<string, string> = {
  OK: 'OK',
  NO_CONTACT: 'No finger',
  NOT_DETECTED: 'Not detected',
  LEADS_OFF: 'Leads off',
  OUT_OF_RANGE: 'Bad reading',
}

function ageText(seconds: number | null) {
  if (seconds == null) return 'never'
  if (seconds < 60) return `${seconds.toFixed(0)} s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  return `${Math.round(seconds / 3600)} h ago`
}

export function DevicePanel({ live, latest }: { live: LiveState | null; latest: Reading | null }) {
  // The live endpoint is in-memory and resets when the backend restarts;
  // fall back to the last stored reading so we can still say when data last arrived.
  const lastSeconds = live?.seconds_since_last
    ?? (latest ? (Date.now() - new Date(latest.captured_at).getTime()) / 1000 : null)
  const connection = live?.connected ? 'live' : lastSeconds == null ? 'none' : 'stale'
  const connectionText = { live: 'Receiving data', stale: 'No new data', none: 'No data yet' }[connection]

  return (
    <section className="device-panel">
      <div className="device-connection">
        <span className={`dot dot-${connection}`} />
        <div>
          <strong>{connectionText}</strong>
          <small>
            {live?.device_id ?? latest?.device_id ?? 'No device'} · last update {ageText(lastSeconds)}
          </small>
        </div>
      </div>
      <div className="sensor-chips">
        {SENSORS.map(({ key, role }) => {
          const s = live?.sensor_status?.[key]
          const state = connection === 'live' && s ? s.state : 'UNKNOWN'
          return (
            <div className={`sensor-chip sensor-${state === 'OK' ? 'ok' : state === 'UNKNOWN' ? 'unknown' : 'bad'}`} key={key} title={s?.detail}>
              <div><strong>{key}</strong><span>{role}</span></div>
              <em>{LABELS[state] ?? '—'}</em>
              {s && state !== 'OK' && state !== 'UNKNOWN' ? <small>{s.detail}</small> : null}
            </div>
          )
        })}
      </div>
      {connection === 'live' && live?.arduino_messages.length ? (
        <div className="arduino-messages">Arduino: {live.arduino_messages.join(' · ')}</div>
      ) : null}
    </section>
  )
}
