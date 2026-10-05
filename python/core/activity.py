from __future__ import annotations

import math
from collections import deque


class ActivityEstimator:
    """Use MPU6050 acceleration + gyroscope as motion context."""

    def __init__(self, sample_window: int = 200):
        self._accel_dynamic = deque(maxlen=sample_window)
        self._gyro_magnitude = deque(maxlen=sample_window)

    def update(
        self,
        ax: float,
        ay: float,
        az: float,
        gx: float,
        gy: float,
        gz: float,
    ) -> str:
        accel_magnitude = math.sqrt(ax * ax + ay * ay + az * az)
        dynamic_accel = abs(accel_magnitude - 9.80665)
        gyro_magnitude = math.sqrt(gx * gx + gy * gy + gz * gz)

        self._accel_dynamic.append(dynamic_accel)
        self._gyro_magnitude.append(gyro_magnitude)

        mean_accel = sum(self._accel_dynamic) / len(self._accel_dynamic)
        mean_gyro = sum(self._gyro_magnitude) / len(self._gyro_magnitude)

        if mean_accel > 1.8 or mean_gyro > 1.2:
            return "HIGH"
        if mean_accel > 0.45 or mean_gyro > 0.35:
            return "MODERATE"
        return "RESTING"
