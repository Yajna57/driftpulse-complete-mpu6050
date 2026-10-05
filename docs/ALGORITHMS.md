# Phase-1 Algorithms

```text
AD8232 ECG -> filtering -> QRS peaks -> RR intervals -> RMSSD/SDNN/pNN50
                                                        |
MAX30102 PPG -> pulse / HR fallback --------------------+
LM35 -> temperature ------------------------------------+--> personalized baseline
MPU6050 -> motion/activity context ---------------------+       -> Z-score
                                                                -> EWMA + CUSUM
                                                                -> risk classification
```

Baseline metrics in this hardware version are only:

- heart rate
- RMSSD
- SDNN
- temperature

MPU6050 is used to reduce movement-related false alerts. It is not treated as a medical risk measurement.

There is no GSR in the baseline, database request model, collector, or risk engine.
