import type { Reading } from './types'

// Plausibility checks. They never hide data: the value is always shown,
// a returned string is only a small warning under it.
export type Warning = string | null

const num = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v)

export function heartRateWarning(v: number | null | undefined): Warning {
  if (!num(v)) return null
  if (v === 0) return 'No pulse detected'
  return v < 30 || v > 220 ? `Unusual (${v.toFixed(0)} bpm)` : null
}

export function temperatureWarning(v: number | null | undefined): Warning {
  if (!num(v)) return null
  return v < 20 || v > 45 ? `Check LM35 wiring (${v.toFixed(1)} °C)` : null
}

export function ppgWarning(v: number | null | undefined): Warning {
  if (!num(v)) return null
  if (v === 0) return 'No signal; check MAX30102'
  return v < 50000 ? 'Weak signal; place finger' : null
}

export function motionWarning(r: Reading | null): Warning {
  if (!r) return null
  const axes = [r.accel_x_ms2, r.accel_y_ms2, r.accel_z_ms2, r.gyro_x_rads, r.gyro_y_rads, r.gyro_z_rads]
  return axes.every((a) => a === 0) ? 'All axes 0; check MPU6050' : null
}

export function ecgWarning(r: Reading | null): Warning {
  return r?.ecg_lead_off ? 'Leads off; check electrodes' : null
}

export function warningFor(key: keyof Reading, v: number | null | undefined): Warning {
  switch (key) {
    case 'heart_rate_bpm': return heartRateWarning(v)
    case 'temperature_c': return temperatureWarning(v)
    case 'ppg_ir':
    case 'ppg_red': return ppgWarning(v)
    case 'accel_x_ms2': case 'accel_y_ms2': case 'accel_z_ms2':
    case 'gyro_x_rads': case 'gyro_y_rads': case 'gyro_z_rads':
      return num(v) && v === 0 ? 'Reads 0; check sensor' : null
    default: return null
  }
}
