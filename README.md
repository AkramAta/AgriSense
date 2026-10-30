# AgriSense: Smart Agriculture System with Plant Disease Detection

AgriSense is an end-to-end intelligent precision agriculture platform combining edge IoT microcontrollers, on-device machine learning inference, cloud-native serverless pipelines, and a cross-platform Flutter application.

---

## System Architecture Overview

```
+-------------------------------+       +-----------------------------------+       +---------------------------+
| ESP32 (Irrigation Node)       |<=====>|  Flutter Mobile Application       |<=====>| AWS Serverless Backend    |
| - DHT11 (Temp/Humidity)       |       |  - Live Soil & Climate Telemetry  |       | - API Gateway (HTTP REST) |
| - Capacitive Soil Moisture    |       |  - Manual & Auto Pump Controls    |       | - S3 (Plant Image Store)  |
| - Relay & Solenoid / Pump     |       |  - Mobile Camera Photo Capture    |       | - SQS (Async Inference)   |
| - FSM & Auto-Cutoff Safety    |       |  - Photo Gallery Leaf Upload      |       | - DynamoDB (Audit Log)    |
| - Local HTTP REST API (Port 80|       |  - AI Plant Pathology & Rx        |       | - Gemini Cloud AI Q&A     |
+-------------------------------+       +-----------------------------------+       +---------------------------+
```

---

## Repository Structure

```
├── .github/workflows/          # CI/CD Workflows (Firmware, Backend, Flutter, Wokwi)
├── firmware/
│   ├── irrigation_node/        # ESP32 Soil & Climate Sensing, Relay Controller, WebServer
│   ├── vision_node/            # ESP32-CAM Leaf Image Capture, TFLite Micro Inference
│   ├── test/                   # Native C++ host-side test suite for pure logic headers
│   ├── diagram.json            # Wokwi simulation circuit diagram
│   └── wokwi.toml              # Wokwi simulation runner configuration
├── ml/
│   ├── scripts/                # Dataset downloader, training, quantization & C array export
│   └── models/                 # Model checkpoints, quantized TFLite, and metadata
├── backend/
│   ├── template.yaml           # AWS SAM Infrastructure as Code
│   ├── common_layer/           # Shared Python helper modules & response formatters
│   ├── handlers/               # AWS Lambda handlers (upload, inference, results, chat)
│   └── tests/                  # Offline moto/pytest integration test harness
├── mobile_app/                 # Flutter cross-platform client (Android, iOS, Web)
│   ├── lib/                    # Screens, services, state management, SQLite models
│   ├── test/                   # Unit and widget test suite
│   └── tool/                   # Mock ESP32 local server for development
└── docs/                       # Architectural blueprints, schematics, and validation guides
```

---

## Key Capabilities

1. **Edge Intelligence & Quantization:**
   - 4-block compact CNN architecture (~61K parameters) trained on 8 tomato disease classes.
   - Post-training INT8 full integer quantization with representative calibration dataset (~70 KB footprint).
   - Zero-dynamic-allocation inference on ESP32-CAM using a dedicated PSRAM tensor arena.

2. **Failsafe Irrigation State Machine:**
   - Origin-tracking pump activation (`pumpStartedByAuto` flag).
   - Enforced maximum run duration auto-shutoff safety timer prevents water overflow.
   - Decoupled threshold math (`irrigation_logic.h`) thoroughly validated via host-side unit tests.

3. **Cloud & Edge Dual Inference:**
   - Local on-device diagnosis runs in sub-second offline environments.
   - Cloud pipeline powered by AWS SAM (API Gateway, S3, SQS, DynamoDB, Lambda) with Gemini Vision multimodal fallback.

4. **Multi-Platform Mobile Application:**
   - Live telemetry dashboard and irrigation controls.
   - Dual-mode disease scanner (ESP32-CAM fetch or device camera/gallery).
   - Agronomic advice chatbot powered by Google Gemini.
   - Cross-platform persistence (SQLite on mobile, IndexedDB on web).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

