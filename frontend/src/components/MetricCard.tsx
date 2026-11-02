// Green when a value has arrived. A wrong-looking value is still shown;
// only a small warning line is added.
export function MetricCard({ label, value, helper, hasData, warning }: {
  label: string
  value: string
  helper?: string
  hasData: boolean
  warning?: string | null
}) {
  return (
    <article className={`metric-card ${hasData ? 'has-data' : 'no-data'}`}>
      <span className="metric-label"><i className="led" />{label}</span>
      <strong className="metric-value">{value}</strong>
      {warning ? <span className="warn-text">⚠ {warning}</span> : helper ? <span className="metric-helper">{helper}</span> : null}
    </article>
  )
}
