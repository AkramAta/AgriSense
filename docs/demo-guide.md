# AgriSense Demo Guide — No Physical Hardware Required

This is a real, run-it-yourself demonstration procedure for the **AgriSense** Smart Agriculture & Plant Disease Detection System. Every step below has been executed and verified against the actual repository codebase — nothing here is aspirational or a mockup.

This guide deliberately avoids requiring physical ESP32 boards, physical soil probes, or live crop fields, since full verification can be conducted entirely in your local development environment using high-fidelity simulations, native mobile hardware, and serverless test harnesses (see [`docs/hardware-validation-checklist.md`](hardware-validation-checklist.md) and [`docs/architecture.md`](architecture.md)).

---

## What's Real vs. Simulated in This Demo

Stated clearly up front so the architecture is completely transparent during reviews, pitch meetings, and evaluation:

| Subsystem / Component | Implementation Status | Technical Details |
|---|---|---|
| **Mobile Camera Leaf Capture** | **Real** | Executed directly via smartphone camera (`Take Photo`) or image gallery picker (`Upload Photo`) inside the Flutter application. No external ESP32-CAM is required. |
| **ML Inference (INT8 TFLite Model)** | **Real** | Quantized INT8 tomato pathology CNN (~64.8 KB, 61K parameters) executing inference on 8 disease classes in real time. |
| **Multimodal AI Agronomist Chat** | **Real** | Conversational plant-care engine powered by Google Gemini Vision with an offline rule-based agronomy expert fallback. |
| **Flutter Cross-Platform App** | **Real** | Fully compiled and interactive application running in modern web browsers, Android, and iOS with 6 dedicated functional tabs. |
| **Local Diagnostic History Storage** | **Real** | Offline-first persistence via SQLite on mobile and IndexedDB on web browsers. |
| **AWS Serverless Backend** | **Real / Fully Emulated** | AWS SAM architecture (API Gateway, S3, SQS inference decoupling, DynamoDB audit table, Lambda handlers) verified with `boto3` and `moto`. |
| **Irrigation Node Firmware Logic** | **Simulated** | Production C++ state machine, origin-tracking pump safety timers, and IIR filtering running in Wokwi virtual ESP32 or the native Dart hardware simulator. |
| **Soil Moisture / Climate Sensors** | **Simulated** | Virtual potentiometer (capacitive soil probe) and DHT11 (ambient temperature & humidity) in Wokwi, or dynamic math generators in the Dart simulator. |
| **Water Pump & Relay Actuator** | **Simulated** | Virtual optocoupled relay module and blue LED indicator in Wokwi, or real-time state flags in the local REST simulator. |

---

## Architecture Highlight: Mobile Camera vs. ESP32-CAM

In traditional IoT hobby setups, an ESP32-CAM is often wired into the field. AgriSense deliberately supersedes this architecture:

1. **Resolution & Optical Quality:** Smartphone cameras provide optical autofocus, flash illumination, macro clarity, and high megapixel resolution, yielding drastically superior feature extraction for plant pathology compared to fixed-focus, low-RAM OV2640 modules.
2. **Mobility Across the Field:** A farmer carries one smartphone and can inspect hundreds of individual leaves, crops, and greenhouse rows without mounting dozens of weatherproof outdoor camera rigs.
3. **Dual Execution Options:** The Flutter app runs quantized INT8 TFLite models on-device for instant offline diagnosis, while also supporting cloud upload to AWS SAM for audit logging and secondary Gemini multimodal analysis.

---

## Prerequisites (One-Time Setup)

```bash
# 1. Clone repository and navigate to root
git clone https://github.com/AkramAta/AgriSense.git
cd AgriSense

# 2. Python backend test dependencies
pip install -r backend/requirements-test.txt

# 3. Flutter SDK (verify installation)
flutter --version
```

- **For Wokwi Simulation:** A modern browser at [wokwi.com/esp32](https://wokwi.com/esp32) (no account or token required for browser IDE testing).
- **For Local Hardware Simulation:** The Dart SDK bundled inside Flutter (`dart mobile_app/tool/esp32_simulator.dart`).

---

## 5-Minute Demo (Quick Pitch & Overview)

Designed for pitch meetings, progress evaluations, and rapid end-to-end verification.

### 1. Show the Flutter App Running in a Browser (90 seconds)

Run the real compiled Flutter web application:

```bash
cd mobile_app
flutter run -d chrome
```

*(Alternatively, build and serve statically: `flutter build web && cd build/web && python -m http.server 8123` and navigate to `http://127.0.0.1:8123`).*

Click through the 6 bottom navigation tabs:
1. **Sensors Dashboard:** Real-time radial gauges for soil moisture, ambient temperature, relative humidity, and raw ADC calibration.
2. **Irrigation Control:** Manual pump start/stop switches, AUTO mode toggle, and the 15-second safety timer display.
3. **Disease Scanner:** Leaf photo capture and upload interface with instant diagnostic card rendering.
4. **Diagnosis History:** Chronological audit trail of past leaf scans with timestamps and severity tags.
5. **AI Agronomist Chat:** Context-aware interactive Q&A assistant for crop treatment.
6. **Device Benchmark:** Connectivity diagnostics, ping latency test, and REST endpoint probe.

---

### 2. Demonstrate Leaf Disease Detection with Mobile Camera / Upload (90 seconds)

1. In the Flutter app, switch to the **Disease Scanner** tab.
2. Click **Upload Photo** (or **Take Photo** if on a mobile device or webcam).
3. Select any tomato leaf image (e.g., from `ml/dataset/` or a sample tomato image).
4. **Watch the live output render immediately:**
   - **Class Prediction:** e.g., `Tomato___Tomato_Yellow_Leaf_Curl_Virus` or `Tomato___Early_blight`.
   - **Confidence Score:** e.g., `98.4%`.
   - **Severity Level:** Visual colored badge (`Critical`, `High`, or `Medium`).
   - **Prescription Details:**
     - *Symptoms:* Concentric rings, leaf curling, or chlorotic halos.
     - *Immediate Chemical Control:* Specific recommended fungicide/bactericide (e.g., Chlorothalonil or Mancozeb).
     - *Organic / Bio-control:* Neem oil, Bacillus subtilis, or copper octanoate.
     - *Cultural Practices:* Drip irrigation instructions and canopy spacing.
5. Click **Consult AI Agronomist on this issue** at the bottom of the diagnosis card:
   - The app transitions straight to the **Chat** screen with the detected disease and treatment context automatically preloaded for conversation.

---

### 3. Launch Local Hardware Simulator & Watch Live Telemetry (60 seconds)

In a separate terminal, launch AgriSense's protocol-accurate dual-node hardware simulator:

```bash
dart mobile_app/tool/esp32_simulator.dart
```

Expected terminal output:
```
====================================================
Starting AgriSense Dual-Node Hardware Simulator...
====================================================
Irrigation Node listening at: http://127.0.0.1:8080
Vision Node listening at:     http://127.0.0.1:8081
Press Ctrl+C to terminate simulator.
```

- In the Flutter app's **Sensors** tab, change the ESP32 IP to `127.0.0.1:8080`.
- The gauges immediately come to life with live streaming moisture, temperature, and humidity telemetry!
- Switch to **Irrigation Control** and click **Start Pump**.
- Watch the pump status transition to `ON`, the active timer tick, and the 15-second auto-cutoff countdown ensure water safety.

---

### 4. Show the Serverless Pipeline Passing All Verification Tests (60 seconds)

Execute the backend serverless test suite:

```bash
pytest backend/tests/ -v
```

Expected output:
```
backend/tests/test_lambda_handlers_local.py::test_upload_handler_creates_presigned_url_and_sqs_message PASSED
backend/tests/test_lambda_handlers_local.py::test_inference_handler_runs_tflite_and_updates_dynamodb PASSED
backend/tests/test_lambda_handlers_local.py::test_results_handler_success_and_404 PASSED
backend/tests/test_lambda_handlers_local.py::test_chat_handler_expert_fallback PASSED
backend/tests/test_lambda_handlers_local.py::test_end_to_end_serverless_pipeline PASSED
========================= 5 passed in 4.24s =========================
```

**What to explain:** Every component of the AWS SAM architecture (S3 presigned URLs, SQS async queueing, TFLite inference processing, DynamoDB audit storage, and Gemini conversational fallback) is validated end-to-end without incurring cloud infrastructure bills or requiring live AWS credentials.

---

## 10-Minute Detailed Technical Demo

Includes everything in the 5-minute demo, plus deep-dive interactive hardware simulation and AI agronomy consultation:

### 5. Interactive Wokwi ESP32 Circuit Simulation (3 minutes)

This visual circuit simulation allows the audience to watch virtual sensors trigger microcontroller logic in real time:

1. Open [wokwi.com/esp32](https://wokwi.com/esp32) in your browser.
2. Click the `diagram.json` tab, delete the default contents, and paste the contents of [`firmware/diagram.json`](../firmware/diagram.json).
3. Click the `sketch.ino` tab and paste the contents of [`firmware/wokwi_sketch.ino`](../firmware/wokwi_sketch.ino).
4. Click the `libraries.txt` tab and paste:
   ```
   DHT sensor library
   Adafruit Unified Sensor
   ```
5. Click **▶ Play / Run Simulation**.

**Expected behavior:**
- The ESP32 DevKit, DHT11 sensor, potentiometer, and relay module render on canvas.
- The virtual Serial Monitor prints:
  ```
  [AGRISENSE] Booting ESP32 Irrigation Node...
  [AGRISENSE] Firmware: v1.2.0 | Node ID: AGRISENSE-IRR-01
  [AGRISENSE] Connecting to Wi-Fi: Wokwi-GUEST
  [AGRISENSE] Wi-Fi Connected! IP Address: 10.0.1.2
  [AGRISENSE] REST WebServer initialized on port 80.
  [AGRISENSE] Irrigation Node Ready.
  WOKWI_IRRIGATION_READY
  ```
- **Interactive Test A (Dry Soil Trigger):** Click and drag the potentiometer counter-clockwise (representing drying soil). When moisture drops below 35%, the ESP32 state machine transitions to `PUMP_ON`, triggering the relay and illuminating the blue LED.
- **Interactive Test B (Wet Soil Cutoff):** Drag the potentiometer clockwise above 65%. The relay clicks `OFF` and the LED extinguishes.
- **Interactive Test C (Safety Timeout):** Leave the potentiometer at dry (< 35%) for 15 continuous seconds. Observe the serial monitor: `[AGRISENSE-SAFETY] AUTO PUMP TIMEOUT TRIPPED! Maximum run duration exceeded.` The relay cuts power immediately to prevent root flooding.

---

### 6. Test the Conversational AI Agronomist (2 minutes)

In the Flutter app, open the **Chat** tab:

1. **Ask about disease management:**
   > *"What is the difference between Early Blight and Late Blight on tomatoes?"*
2. **Observe the structured response:**
   - Highlights concentric target spots for *Alternaria solani* (Early Blight) vs. dark water-soaked oily lesions with white sporulation for *Phytophthora infestans* (Late Blight).
   - Recommends drip irrigation management to prevent water splash onto lower foliage.
3. **Ask about irrigation safety:**
   > *"Why does the pump shut off after 15 seconds?"*
4. **Observe the safety explanation:**
   - Explains root hypoxia prevention, soil saturation limits, and flyback thermal protection for submersible pump solenoids.

---

### 7. Run Complete Unit & Integration Test Suites (2 minutes)

Execute both subsystems to show code coverage and robust error handling:

```bash
# 1. Backend serverless & TFLite tests
pytest backend/tests/ -v

# 2. Mobile app & service tests
cd mobile_app
flutter test
```

Point out critical test cases:
- `test_end_to_end_serverless_pipeline`: Exercises image payload handling, INT8 TFLite model inference, and DynamoDB record serialization.
- `getStatus parses full irrigation status and safety fields`: Proves that corrupted or malformed JSON payloads from unstable IoT Wi-Fi networks will never crash the mobile UI.

---

## Generating a Throwaway Test Image for Scripted Testing

If testing API endpoints headlessly without opening the Flutter UI:

```python
import base64
import io
import json
from PIL import Image

# Generate a synthetic 96x96 green tomato leaf patch
img = Image.new('RGB', (96, 96), color=(46, 139, 87))
buf = io.BytesIO()
img.save(buf, format='JPEG')
b64_data = base64.b64encode(buf.getvalue()).decode('utf-8')

payload = {
    "filename": "demo_leaf.jpg",
    "content_type": "image/jpeg",
    "image_base64": b64_data
}

with open("payload.json", "w") as f:
    json.dump(payload, f)

print("Created payload.json for automated testing.")
```

---

## Presentation Checklist & Screenshots to Prepare Ahead of Time

In case of live venue network restrictions or projector latency, keep these visual proofs saved on your presentation machine:

1. **Disease Scanner Screen:** Active diagnosis showing `Tomato___Tomato_Yellow_Leaf_Curl_Virus`, 98.4% confidence score, and color-coded prescription cards.
2. **Sensors Dashboard Screen:** Live animated radial gauges for soil moisture, temperature, and humidity.
3. **Irrigation Control Screen:** Relay ON state with active 15s auto-cutoff countdown.
4. **Wokwi Simulation Canvas:** Visual circuit showing ESP32 DevKit, DHT11, potentiometer, and illuminated blue pump LED.
5. **Wokwi Serial Log:** Boot sequence displaying `WOKWI_IRRIGATION_READY` and safety timeout events.
6. **Backend Pytest Terminal:** Clean 5/5 passed test run summary.
7. **Flutter Test Terminal:** Test suite passing with zero failures.

---

## Fallback Procedures If Services Are Temporarily Unavailable

- **If no internet or AWS connection is available:**
  - The Flutter application performs on-device TFLite inference completely offline using its bundled `model_quant_int8.tflite` asset.
  - The Gemini Chat screen automatically activates its built-in rule-based expert agronomy engine (`agrisense_common.py`), delivering instant agronomic prescriptions without external network access.
- **If physical ESP32 Wi-Fi is unreachable:**
  - The local Dart simulator (`dart mobile_app/tool/esp32_simulator.dart`) runs entirely on `localhost:8080`, providing identical HTTP REST responses and CORS headers for full web app interoperability.

