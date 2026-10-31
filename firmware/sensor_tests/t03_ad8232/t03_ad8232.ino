// TEST 3: AD8232 ECG. No library.
// Wiring: OUTPUT=A0, LO+=D8, LO-=D9, 3.3V, GND. Serial Monitor: 115200 baud.
// SAFETY: use battery laptop, unplug charger, when electrodes are on body.
// Pass: leads-off flag toggles when you attach/detach electrodes; with electrodes on, A0 varies (QRS spikes).
// Tip: Serial Plotter (Tools > Serial Plotter) shows ECG waveform; set PLOT_MODE 1 for plotter-only output.
#define PLOT_MODE 0

const uint8_t PIN_ECG = A0;
const uint8_t PIN_LO_P = 8;
const uint8_t PIN_LO_N = 9;

int minV = 1023, maxV = 0;
uint32_t windowStart = 0;
uint16_t samples = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  pinMode(PIN_LO_P, INPUT);
  pinMode(PIN_LO_N, INPUT);
  Serial.println(F("[T03] AD8232 test start"));
  Serial.println(F("[T03] columns: raw | LO+ | LO- | status"));
  windowStart = millis();
}

void loop() {
  bool loP = digitalRead(PIN_LO_P);
  bool loN = digitalRead(PIN_LO_N);
  int raw = analogRead(PIN_ECG);

  if (!(loP || loN)) {  // only track range when leads attached
    if (raw < minV) minV = raw;
    if (raw > maxV) maxV = raw;
  }
  samples++;

#if PLOT_MODE
  Serial.println((loP || loN) ? 0 : raw);
#else
  static uint32_t lastPrint = 0;
  if (millis() - lastPrint >= 50) {
    lastPrint = millis();
    Serial.print(F("[T03] "));
    Serial.print(raw); Serial.print(F(" | "));
    Serial.print(loP); Serial.print(F(" | "));
    Serial.print(loN); Serial.print(F(" | "));
    if (loP || loN) Serial.println(F("LEADS OFF"));
    else Serial.println(F("LEADS ON"));
  }
#endif

  if (millis() - windowStart >= 5000) {
#if !PLOT_MODE
    Serial.print(F("[T03] SUMMARY 5s: samples="));
    Serial.print(samples);
    if (minV <= maxV) {
      Serial.print(F(" min=")); Serial.print(minV);
      Serial.print(F(" max=")); Serial.print(maxV);
      Serial.print(F(" span=")); Serial.print(maxV - minV);
      if (maxV - minV > 100) Serial.println(F(" -> PASS (signal varies)"));
      else Serial.println(F(" -> FLAT: check electrodes/skin contact/wiring"));
    } else {
      Serial.println(F(" -> leads off the whole window (attach electrodes to test signal)"));
    }
#endif
    minV = 1023; maxV = 0; samples = 0;
    windowStart = millis();
  }
  delay(4);  // ~250 Hz
}
