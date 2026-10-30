# AgriSense Hardware & Firmware Validation Checklist

Use this formal bench validation procedure prior to commissioning hardware nodes in the field.

---

## Phase 1: Cold (Unpowered) Electrical Inspection

- [ ] **Short Circuit Check:** Measure resistance between `5V` and `GND` with a digital multimeter in resistance mode ($>10\text{ k}\Omega$ expected).
- [ ] **LDO Rail Isolation:** Measure resistance between `3V3` and `GND` ($>5\text{ k}\Omega$ expected).
- [ ] **Polarity Verification:** Verify reverse polarity protection on the 12V pump power connector.
- [ ] **Flyback Diode Orientation:** Ensure the 1N4007 diode cathode (striped end) is connected to +12V and anode to GND across the pump / solenoid terminals.
- [ ] **Ground Plane Integrity:** Confirm that ESP32 GND, relay GND, and sensor GND share a common reference point.

---

## Phase 2: Power-Up & Rail Verification

- [ ] **5V Rail Tolerance:** Power on external supply. Measure voltage on 5V rail ($4.85\text{ V} - 5.25\text{ V}$).
- [ ] **3.3V LDO Output:** Measure ESP32 3V3 output pin ($3.25\text{ V} - 3.35\text{ V}$).
- [ ] **Quiescent Current Draw:** Confirm standby current of the ESP32 node is under $120\text{ mA}$ during Wi-Fi transmission.

---

## Phase 3: Sensor Calibration & Signal Integrity

- [ ] **Capacitive Sensor in Dry Air:**
  - Expose capacitive probe to open air.
  - Query `GET /sensors`.
  - Verify `raw_adc` reads between `3,050` and `3,300` (Moisture: $0.0\%$).
- [ ] **Capacitive Sensor in Tap Water:**
  - Submerge probe up to the marked maximum depth line in tap water.
  - Query `GET /sensors`.
  - Verify `raw_adc` drops to between `1,300` and `1,500` (Moisture: $100.0\%$).
- [ ] **IIR Filter Smoothing:**
  - Verify `filtered_adc` transitions smoothly without erratic single-sample spikes.
- [ ] **DHT11 Ambient Climate:**
  - Inspect `temperature_c` ($15^\circ\text{C} - 40^\circ\text{C}$ expected in ambient room).
  - Inspect `humidity_percent` ($30\% - 90\%$ expected).

---

## Phase 4: Relay Driver & Safety Auto-Shutoff Validation

- [ ] **Manual Relay Control:**
  - Issue `POST /pump/manual` with `{"action": "start"}`.
  - Verify relay clicks ON, LED illuminates, and `pumpStatus == "ON"`.
  - Issue `POST /pump/manual` with `{"action": "stop"}`.
  - Verify relay clicks OFF.
- [ ] **Auto Threshold Activation:**
  - Switch to AUTO mode (`POST /pump/auto` `{"enabled": true}`).
  - Remove sensor from water (Moisture $< 35\%$).
  - Verify pump automatically turns ON with `pump_started_by_auto == true`.
- [ ] **Wet Threshold Auto-Stop:**
  - Submerge sensor in water (Moisture $\ge 65\%$).
  - Verify pump automatically shuts OFF.
- [ ] **Maximum Runtime Auto-Cutoff (Failsafe Test):**
  - Keep sensor dry (Moisture $< 35\%$).
  - Allow pump to run continuously.
  - **Pass Criteria:** At exactly $15\text{ seconds}$, the firmware must force the relay OFF, set `safety_tripped = true`, and set `trip_reason = 1 (AUTO_TIMEOUT)`.
  - Confirm pump refuses to restart until explicitly reset via `POST /status/reset`.
- [ ] **Mandatory 10-Second Cooldown:**
  - Stop pump. Attempt immediate restart within 3 seconds.
  - **Pass Criteria:** Firmware must return HTTP 429 and reject pump restart until cooldown expires.

---

## Phase 5: ESP32-CAM Vision Node Validation

- [ ] **PSRAM Allocation:**
  - Inspect serial output at boot.
  - Verify message: `[AGRISENSE] PSRAM Detected! Total: 4194304 bytes`.
  - Verify tensor arena allocation: `Allocated 250 KB Tensor Arena`.
- [ ] **Camera Frame Grab:**
  - Point camera at target leaf.
  - Query `GET /latest`.
  - Verify HTTP 200 response with `class_name`, `confidence` $> 0.0$, and `inference_time_ms` $< 150\text{ ms}$.
- [ ] **End-to-End Mobile App Sync:**
  - Launch mobile application.
  - Connect to nodes via Wi-Fi.
  - Confirm live gauge updates every 2 seconds.

