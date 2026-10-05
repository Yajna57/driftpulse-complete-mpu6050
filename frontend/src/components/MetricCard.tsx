export function MetricCard({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <article className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {helper ? <span className="metric-helper">{helper}</span> : null}
    </article>
  )
}
