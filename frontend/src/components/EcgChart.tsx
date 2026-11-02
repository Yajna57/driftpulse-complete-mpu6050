import { Line, LineChart, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { LiveState } from '../types'

export function EcgChart({ live }: { live: LiveState | null }) {
  const rate = live?.sample_rate_hz || 100
  const samples = live?.connected ? live.ecg_samples : []
  const data = samples.map((value, i) => ({ t: (i - samples.length) / rate, value }))
  const leadsOff = live?.sensor_status?.AD8232?.state === 'LEADS_OFF'

  return (
    <section className={`chart-card ecg-card ${samples.length ? 'has-data' : 'no-data'}`}>
      <div className="section-heading">
        <h3><i className="led" />Live ECG waveform (AD8232)</h3>
        <span>last {Math.round(samples.length / rate)} s · raw ADC</span>
      </div>
      {leadsOff ? <small className="warn-text">⚠ Leads off; check electrodes (raw signal still shown)</small> : null}
      <div className="chart-wrap">
        {samples.length === 0 ? (
          <p className="chart-empty">Waiting for live ECG samples from the collector.</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <XAxis dataKey="t" type="number" domain={['dataMin', 0]} tickFormatter={(v) => `${Number(v).toFixed(0)}s`} />
              <YAxis width={48} domain={['auto', 'auto']} />
              <Line type="linear" dataKey="value" dot={false} stroke="#1a9d55" strokeWidth={1.5} isAnimationActive={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
