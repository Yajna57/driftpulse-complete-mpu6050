import type { HealthStatus } from '../types'

export function StatusCard({ health }: { health: HealthStatus | null }) {
  const status = health?.status ?? 'WAITING'
  return (
    <section className={`status-card status-${status.toLowerCase()}`}>
      <div>
        <span className="eyebrow">Current physiological state</span>
        <h2>{status}</h2>
        <p>{health?.summary ?? 'Waiting for sensor data.'}</p>
      </div>
      <div className="risk-ring">
        <strong>{health?.risk_score ?? 0}</strong><span>/100</span>
      </div>
    </section>
  )
}
