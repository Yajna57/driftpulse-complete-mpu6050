import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Reading } from '../types'

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

  return (
    <section className="chart-card">
      <div className="section-heading"><h3>{title}</h3><span>{unit}</span></div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" minTickGap={40} />
            <YAxis width={48} domain={['auto', 'auto']} />
            <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} ${unit}`, title]} />
            <Line type="monotone" dataKey="value" dot={false} stroke="currentColor" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
