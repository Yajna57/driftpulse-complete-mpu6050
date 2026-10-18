export interface Reading {
  id: number
  user_id: string
  device_id: string
  captured_at: string
  heart_rate_bpm: number | null
  temperature_c: number | null
  ecg_raw: number | null
  ecg_lead_off: boolean
  ppg_ir: number | null
  ppg_red: number | null
  accel_x_ms2: number | null
  accel_y_ms2: number | null
  accel_z_ms2: number | null
  gyro_x_rads: number | null
  gyro_y_rads: number | null
  gyro_z_rads: number | null
  activity: string
  mean_rr_ms: number | null
  rmssd_ms: number | null
  sdnn_ms: number | null
  pnn50_percent: number | null
  ecg_heart_rate_bpm: number | null
}

export interface HealthStatus {
  status: string
  risk_score: number
  summary: string
  observations: string[]
  z_scores: Record<string, number | null>
  drift: Record<string, unknown>
  baseline_ready: boolean
  updated_at: string | null
  reading_id: number | null
}

export interface BaselineMetric {
  mean: number
  std: number
  sample_count: number
  ready: boolean
}

export interface BaselineResponse {
  user_id: string
  required_samples: number
  metrics: Record<string, BaselineMetric>
}

export interface AlertItem {
  id: number
  severity: string
  type: string
  message: string
  created_at: string
  resolved: boolean
}

export interface SensorState {
  state: string
  detail: string
}

export interface LiveState {
  user_id: string
  connected: boolean
  device_id: string | null
  last_seen: string | null
  seconds_since_last: number | null
  sample_rate_hz: number
  ecg_samples: (number | null)[]
  sensor_status: Record<string, SensorState>
  arduino_messages: string[]
}

export interface UserItem {
  user_id: string
  last_reading: string
}
