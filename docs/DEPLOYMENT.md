# AgriSense Production Deployment Guide

This guide provides end-to-end instructions for deploying all subsystems of the AgriSense platform: microcontrollers, AWS Serverless cloud backend, and cross-platform Flutter application.

---

## 1. Prerequisites & Tooling

Ensure the following tools are installed on your workstation:
- **Git** (>= 2.40)
- **Python** (3.12 or 3.14) with `pip`
- **Arduino CLI** (>= 0.35) or **PlatformIO Core**
- **AWS CLI** (v2) and **AWS SAM CLI** (>= 1.100)
- **Flutter SDK** (>= 3.24) with Dart 3.x

---

## 2. Firmware Flashing

### Step 2.1: Flash Irrigation Node (ESP32)

1. Connect your ESP32 DevKit to your workstation via micro-USB.
2. Determine your serial port (e.g. `COM3` on Windows or `/dev/ttyUSB0` on Linux).
3. Using `arduino-cli`:
   ```bash
   # Compile sketch
   arduino-cli compile --fqbn esp32:esp32:esp32 firmware/irrigation_node

   # Upload to ESP32
   arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 firmware/irrigation_node
   ```
4. Verify boot output at 115,200 baud in your serial monitor:
   ```
   [AGRISENSE] Booting ESP32 Irrigation Node...
   [AGRISENSE] Wi-Fi Connected! IP Address: 192.168.1.100
   [AGRISENSE] Irrigation Node Ready
   ```

> [!NOTE]
> Plant leaf pathology inspection is performed directly via the user's mobile device camera or photo gallery in the Flutter application. An external ESP32-CAM board is no longer required in the field. (The `firmware/vision_node/` codebase remains available as a standalone reference design for embedded edge vision experiments).

---

## 3. AWS Serverless Backend Deployment (SAM)

1. Configure your AWS credentials:
   ```bash
   aws configure
   ```
2. Build the SAM template and shared Lambda layer:
   ```bash
   cd backend
   sam build
   ```
3. Deploy to your AWS account:
   ```bash
   sam deploy --guided \
     --stack-name agrisense-backend \
     --parameter-overrides GeminiApiKey="YOUR_GEMINI_API_KEY"
   ```
4. Note the output values:
   - `ApiEndpoint`: REST API Gateway base URL
   - `BucketName`: S3 image upload bucket
   - `QueueUrl`: SQS inference queue
   - `TableName`: DynamoDB audit table

---

## 4. Mobile & Web Application Deployment

### Local Development with Mock Simulator
If hardware boards are not physically connected, launch the local simulator:
```bash
dart run mobile_app/tool/esp32_simulator.dart
```

### Build & Run Flutter App

```bash
cd mobile_app
flutter pub get

# Run on Chrome (Web)
flutter run -d chrome

# Build Release APK for Android
flutter build apk --release

# Build Web Distribution
flutter build web --release
```

---

## 5. Security & Network Hardening

- **Microcontroller Isolation:** Place IoT nodes on an isolated 2.4 GHz VLAN / IoT SSID.
- **IAM Least Privilege:** Lambda execution roles are strictly locked to single S3 buckets, SQS queues, and DynamoDB tables.
- **S3 Presigned URLs:** Raw image uploads use presigned PUT URLs with a 15-minute maximum expiration window, preventing unauthenticated uploads.

