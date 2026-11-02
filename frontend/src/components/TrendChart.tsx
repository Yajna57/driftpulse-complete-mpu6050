import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Reading } from '../types'
import { warningFor } from '../validate'

export function TrendChart({ title, data, dataKey, unit }: {
  title: string
  data: Reading[]
  dataKey: keyof Reading
  unit: string
}) {
  const chartData = data
    .map((row) => ({
      time: new Date(row.captured_at).toLocaleTimeString(),
      value: row[dataKey] as number | null,
    }))
    .filter((row) => typeof row.value === 'number' && Number.isFinite(row.value))

  const last = chartData.length ? chartData[chartData.length - 1].value : null
  const warning = warningFor(dataKey, last)

  return (
    <section className={`chart-card ${chartData.length ? 'has-data' : 'no-data'}`}>
      <div className="section-heading">
        <h3><i className="led" />{title}</h3>
        <span>{last != null ? `${Number(last).toFixed(2)} ${unit}` : unit}</span>
      </div>
      {warning ? <small className="warn-text">⚠ {warning}</small> : null}
      <div className="chart-wrap">
        {chartData.length === 0 ? <p className="chart-empty">No data yet.</p> : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="time" minTickGap={40} />
              <YAxis width={48} domain={['auto', 'auto']} />
              <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} ${unit}`, title]} />
              <Line type="monotone" dataKey="value" dot={false} stroke="#1a9d55" strokeWidth={2} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
