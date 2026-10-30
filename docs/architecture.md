# AgriSense System Architecture Blueprint

## 1. System Topology Overview

AgriSense is an enterprise-grade IoT precision agriculture and plant pathology platform designed to operate across disconnected edge environments, local Wi-Fi meshes, and cloud serverless infrastructures.

```
+-----------------------------------------------------------------------------------+
|                                 EDGE HARDWARE TIER                                |
|                                                                                   |
|  +---------------------------+                    +----------------------------+  |
|  | ESP32 Irrigation Node     |                    | ESP32-CAM Vision Node      |  |
|  | - DHT11 (Temp / Humidity) |                    | - OV2640 Image Sensor      |  |
|  | - Analog Soil Moisture    |                    | - 250 KB PSRAM Tensor Arena|  |
|  | - Relay & Solenoid Pump   |                    | - TFLite Micro INT8 Engine |  |
|  | - Failsafe State Machine  |                    | - Embedded WebServer       |  |
|  | - Embedded WebServer      |                    |   (Port 80: /latest)       |  |
|  |   (Port 80: /sensors)     |                    |                            |  |
|  +-------------+-------------+                    +-------------+--------------+  |
+----------------|------------------------------------------------|-----------------+
                 |                                                |
                 | Local Wi-Fi (HTTP REST / JSON)                 |
                 +-----------------------+------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                            CROSS-PLATFORM CLIENT TIER                             |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Flutter Multi-Platform Application (Android / iOS / Web)                     |  |
|  | - Telemetry Dashboard & Live Moisture Gauges                                |  |
|  | - Manual Relay Control & Origin-Tracking Auto-Cutoff Display                |  |
|  | - Mobile Camera Capture & Photo Gallery Leaf Disease Scanner                |  |
|  | - Cross-Platform History Storage (SQLite / Web IndexedDB)                   |  |
|  | - Conversational AI Agronomist Chatbot                                      |  |
|  | - Network Diagnostics & Latency Benchmark Engine                            |  |
|  +-------------------------------------+---------------------------------------+  |
+----------------------------------------|------------------------------------------+
                                         |
                                         | HTTPS (TLS 1.3 / SigV4 / REST)
                                         v
+-----------------------------------------------------------------------------------+
|                           AWS SERVERLESS CLOUD BACKEND                            |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Amazon API Gateway (Regional REST API with CORS)                            |  |
|  +--------------------+---------------------+--------------------+-------------+  |
|                       |                     |                    |                |
|                       v                     v                    v                |
|             +-------------------+  +-------------------+  +-------------------+   |
|             | Upload Lambda     |  | Results Lambda    |  | Gemini Chat Lambda|   |
|             +---------+---------+  +---------+---------+  +---------+---------+   |
|                       |                      |                      |             |
|          +------------+------------+         |                      |             |
|          |                         |         |                      |             |
|          v                         v         |                      |             |
|   +---------------+       +----------------+ |                      |             |
|   | S3 Raw Bucket |       | SQS Inference  | |                      |             |
|   | (Plant Images)|       | Decoupling Q   | |                      |             |
|   +---------------+       +--------+-------+ |                      |             |
|                                    |         |                      |             |
|                                    v         |                      |             |
|                           +----------------+ |                      |             |
|                           | Inference      | |                      |             |
|                           | Lambda         | |                      |             |
|                           | (ai-edge-      | |                      |             |
|                           |  litert INT8)  | |                      |             |
|                           +--------+-------+ |                      |             |
|                                    |         |                      |             |
|                                    +----+----+                      |             |
|                                         |                           |             |
|                                         v                           v             |
|                           +--------------------+           +------------------+   |
|                           | Amazon DynamoDB    |           | Google Gemini    |   |
|                           | (Audit Records &   |           | Multimodal API   |   |
|                           |  Diagnoses)        |           +------------------+   |
|                           +--------------------+                                  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Microcontroller State Machine & Origin Tracking

The ESP32 Irrigation Node enforces a deterministic finite state machine with strict run-duration auto-shutoff safeguards to prevent physical crop overwatering or pump motor overheating.

### State Transition Diagram

```
                 +-----------------------------------------+
                 |               BOOT / INIT               |
                 | - Relay: OFF, Mode: AUTO                |
                 | - safetyTripped: false                  |
                 +--------------------+--------------------+
                                      |
                                      v
                             +-----------------+
              +------------->|    PUMP_OFF     |<------------+
              |              |  (Mode: AUTO)   |             |
              |              +--------+--------+             |
              |                       |                      |
              | Moisture >= 65%       | Moisture < 35%       |
              | (Wet Threshold)       | && Cooldown Elapsed  |
              |                       |                      |
              |                       v                      |
              |              +-----------------+             |
              |              |     PUMP_ON     |             |
              +--------------| (Auto-Started)  |             |
                             | pumpAuto = true |             |
                             +--------+--------+             |
                                      |                      |
                                      | Runtime >= 15s       | Manual Reset
                                      | (Safety Cutoff)      | / Audit
                                      v                      |
                             +-----------------+             |
                             |  SAFETY TRIPPED |             |
                             |  pumpStatus: OFF|-------------+
                             |  tripReason:    |
                             |  AUTO_TIMEOUT   |
                             +-----------------+
```

### Origin Tracking Rules (`pumpStartedByAuto`)
1. **Auto Activation:** When moisture falls below `dryThresholdPercent` (35%), `pumpStartedByAuto` is set to `true`. When moisture recovers past `wetThresholdPercent` (65%), the pump cuts off automatically.
2. **Manual Override:** When the user commands pump activation via the mobile app, `pumpStartedByAuto` is set to `false`. Rising moisture does **not** interrupt the manual run. However, the system still enforces a strict 30-second ceiling (`maxManualRunDurationMs`), transitioning to `SAFETY_TRIPPED` if left unattended.

---

## 3. On-Device TFLite Micro PSRAM Architecture

The ESP32-CAM runs an INT8 quantized 4-block CNN (~61K parameters) on raw 96x96 RGB frames.

### Memory Layout
- **Model Storage:** The ~64 KB model FlatBuffer resides in SPI Flash memory (`alignas(16) const unsigned char g_model_data[]`), mapped directly into address space with zero RAM footprint.
- **Tensor Arena Allocation:** The tensor arena requires ~250 KB of working memory for activations, scratchpad buffers, and operator tensors. Because internal ESP32 DRAM is constrained (~160 KB free for user heap), the arena is allocated dynamically in external pseudo-static RAM (PSRAM) via:
  ```cpp
  tensor_arena = (uint8_t*)heap_caps_malloc(kTensorArenaSize, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  ```
- **Zero Allocation Inference:** Once `AllocateTensors()` completes, no dynamic heap allocations occur during inference, eliminating fragmentation and memory leaks during continuous field operation.

