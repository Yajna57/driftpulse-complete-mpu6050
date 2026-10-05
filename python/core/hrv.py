from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks


@dataclass(slots=True)
class HRVMetrics:
    mean_rr_ms: float
    rmssd_ms: float
    sdnn_ms: float
    pnn50_percent: float
    ecg_heart_rate_bpm: float
    peak_count: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "mean_rr_ms": round(self.mean_rr_ms, 2),
            "rmssd_ms": round(self.rmssd_ms, 2),
            "sdnn_ms": round(self.sdnn_ms, 2),
            "pnn50_percent": round(self.pnn50_percent, 2),
            "ecg_heart_rate_bpm": round(self.ecg_heart_rate_bpm, 2),
            "peak_count": self.peak_count,
        }


def _bandpass(signal: np.ndarray, sample_rate_hz: float) -> np.ndarray:
    nyquist = sample_rate_hz / 2.0
    low = 5.0 / nyquist
    high = min(20.0 / nyquist, 0.95)
    if low >= high:
        return signal - np.mean(signal)
    b, a = butter(2, [low, high], btype="band")
    return filtfilt(b, a, signal)


def calculate_hrv(
    ecg_samples: list[float] | np.ndarray,
    sample_rate_hz: float = 100.0,
) -> HRVMetrics | None:
    """Educational ECG -> RR -> time-domain HRV estimator."""
    values = np.asarray(ecg_samples, dtype=float)

    if values.size < int(sample_rate_hz * 15):
        return None
    if float(np.std(values)) < 1.0:
        return None

    centered = values - np.median(values)
    try:
        filtered = _bandpass(centered, sample_rate_hz)
    except ValueError:
        return None

    energy = filtered * filtered
    baseline = float(np.percentile(energy, 70))
    upper = float(np.percentile(energy, 98))
    prominence = max((upper - baseline) * 0.20, 1e-6)
    min_peak_distance = max(int(sample_rate_hz * 0.30), 1)

    peaks, _ = find_peaks(
        energy,
        distance=min_peak_distance,
        prominence=prominence,
        height=baseline,
    )

    if peaks.size < 5:
        return None

    rr_ms = np.diff(peaks) / sample_rate_hz * 1000.0
    rr_ms = rr_ms[(rr_ms >= 300.0) & (rr_ms <= 2000.0)]
    if rr_ms.size < 4:
        return None

    rr_diff = np.diff(rr_ms)
    mean_rr = float(np.mean(rr_ms))
    rmssd = float(np.sqrt(np.mean(rr_diff * rr_diff))) if rr_diff.size else 0.0
    sdnn = float(np.std(rr_ms, ddof=1)) if rr_ms.size > 1 else 0.0
    pnn50 = float(np.mean(np.abs(rr_diff) > 50.0) * 100.0) if rr_diff.size else 0.0
    bpm = 60000.0 / mean_rr if mean_rr > 0 else 0.0

    if not 30.0 <= bpm <= 220.0:
        return None

    return HRVMetrics(
        mean_rr_ms=mean_rr,
        rmssd_ms=rmssd,
        sdnn_ms=sdnn,
        pnn50_percent=pnn50,
        ecg_heart_rate_bpm=bpm,
        peak_count=int(peaks.size),
    )
