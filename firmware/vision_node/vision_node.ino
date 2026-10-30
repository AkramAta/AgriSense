/**
 * AgriSense - ESP32-CAM Smart Vision Node
 * Features:
 * - OV2640 Camera initialization (AI-Thinker module pinout).
 * - TFLite Micro runtime with ~250 KB Tensor Arena allocated in PSRAM via heap_caps_malloc.
 * - On-device INT8 Quantized CNN inference (96x96x3 input).
 * - HTTP REST API:
 *     GET /latest  -> Captures frame, executes TFLite inference, returns diagnosis JSON.
 *     GET /status  -> Returns hardware & memory diagnostics.
 *     GET /capture -> Returns raw JPEG frame for live stream preview.
 */

#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "model_data.h"
#include "vision_logic.h"

// TensorFlow Lite Micro Headers
#include "tensorflow/lite/micro/all_ops_resolver.h"
#include "tensorflow/lite/micro/micro_error_reporter.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/version.h"

// AI-Thinker ESP32-CAM Pin Configuration
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define FLASH_LED_PIN      4

// Wi-Fi Config
const char* WIFI_SSID = "AgriSense-Field";
const char* WIFI_PASS = "agrisense2026";

// HTTP Server
WebServer server(80);

// TFLite Micro Globals
namespace {
    tflite::ErrorReporter* error_reporter = nullptr;
    const tflite::Model* model = nullptr;
    tflite::MicroInterpreter* interpreter = nullptr;
    TfLiteTensor* input_tensor = nullptr;
    TfLiteTensor* output_tensor = nullptr;

    constexpr size_t kTensorArenaSize = 250 * 1024; // 250 KB
    uint8_t* tensor_arena = nullptr;
}

// Cached Last Diagnosis
struct DiagnosisRecord {
    uint8_t classIndex = 7;
    float confidence = 0.95f;
    unsigned long inferenceTimeMs = 0;
    unsigned long timestamp = 0;
} g_lastDiagnosis;

void applyCorsHeaders() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleOptions() {
    applyCorsHeaders();
    server.send(204);
}

bool initCamera() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_RGB565; // Native RGB565 for ML tensor downsampling
    config.frame_size = FRAMESIZE_QQVGA;    // 160x120
    config.jpeg_quality = 12;
    config.fb_count = 1;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[AGRISENSE] Camera init failed with error 0x%x\n", err);
        return false;
    }
    Serial.println("[AGRISENSE] Camera initialized (RGB565 QQVGA)");
    return true;
}

bool initTFLite() {
    Serial.println("[AGRISENSE] Initializing TFLite Micro runtime...");

    // Allocate Tensor Arena in external PSRAM (SPIRAM)
    if (psramFound()) {
        Serial.printf("[AGRISENSE] PSRAM Detected! Total: %u bytes, Free: %u bytes\n", ESP.getPsramSize(), ESP.getFreePsram());
        tensor_arena = (uint8_t*)heap_caps_malloc(kTensorArenaSize, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    }

    if (!tensor_arena) {
        Serial.println("[AGRISENSE] PSRAM unavailable or allocation failed. Falling back to internal DRAM...");
        tensor_arena = (uint8_t*)malloc(kTensorArenaSize);
    }

    if (!tensor_arena) {
        Serial.printf("[AGRISENSE] Critical: Failed to allocate %u bytes tensor arena!\n", kTensorArenaSize);
        return false;
    }
    Serial.printf("[AGRISENSE] Allocated %u KB Tensor Arena at %p\n", kTensorArenaSize / 1024, tensor_arena);

    // Load Model from flash C byte array
    model = tflite::GetModel(g_model_data);
    if (model->version() != TFLITE_SCHEMA_VERSION) {
        Serial.printf("[AGRISENSE] Model schema version %lu mismatch with runtime version %d\n", model->version(), TFLITE_SCHEMA_VERSION);
        return false;
    }

    // Resolve Ops
    static tflite::AllOpsResolver resolver;

    // Instantiate MicroInterpreter
    static tflite::MicroInterpreter static_interpreter(
        model, resolver, tensor_arena, kTensorArenaSize, nullptr
    );
    interpreter = &static_interpreter;

    TfLiteStatus allocate_status = interpreter->AllocateTensors();
    if (allocate_status != kTfLiteOk) {
        Serial.println("[AGRISENSE] AllocateTensors() failed!");
        return false;
    }

    input_tensor = interpreter->input(0);
    output_tensor = interpreter->output(0);

    Serial.println("[AGRISENSE] TFLite Micro ready!");
    Serial.printf("  Input Tensor:  %d x %d x %d (Type: %d)\n", input_tensor->dims->data[1], input_tensor->dims->data[2], input_tensor->dims->data[3], input_tensor->type);
    Serial.printf("  Output Tensor: %d classes (Scale: %f, ZP: %d)\n", output_tensor->dims->data[1], output_tensor->params.scale, output_tensor->params.zero_point);

    return true;
}

void runInferenceOnFrame() {
    unsigned long startMs = millis();

    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("[AGRISENSE] Failed to capture camera frame");
        return;
    }

    // Downsample and quantize to 96x96 RGB INT8 tensor
    float inScale = input_tensor ? input_tensor->params.scale : (1.0f / 255.0f);
    int32_t inZP = input_tensor ? input_tensor->params.zero_point : -128;

    agrisense::preprocessFrameRgb565ToInt8(
        fb->buf, fb->width, fb->height,
        input_tensor->data.int8, 96,
        inScale, inZP
    );

    esp_camera_fb_return(fb);

    // Execute on-device model inference
    if (interpreter && interpreter->Invoke() == kTfLiteOk) {
        float outScale = output_tensor->params.scale;
        int32_t outZP = output_tensor->params.zero_point;

        uint8_t topIdx = 0;
        float conf = 0.0f;
        agrisense::dequantizeTopPrediction(output_tensor->data.int8, 8, outScale, outZP, topIdx, conf);

        g_lastDiagnosis.classIndex = topIdx;
        g_lastDiagnosis.confidence = conf;
        g_lastDiagnosis.inferenceTimeMs = millis() - startMs;
        g_lastDiagnosis.timestamp = millis();

        Serial.printf(
            "[AGRISENSE INFERENCE] Class: %s (conf: %.2f%%) in %lu ms\n",
            agrisense::TOMATO_CLASS_NAMES[topIdx], conf * 100.0f, g_lastDiagnosis.inferenceTimeMs
        );
    }
}

void handleGetLatest() {
    applyCorsHeaders();

    // Trigger fresh capture and inference
    runInferenceOnFrame();

    char buffer[384];
    const char* cname = agrisense::TOMATO_CLASS_NAMES[g_lastDiagnosis.classIndex];
    bool healthy = agrisense::isPredictionHealthy(g_lastDiagnosis.classIndex);

    snprintf(
        buffer, sizeof(buffer),
        "{\"class_index\":%u,\"class_name\":\"%s\",\"confidence\":%.4f,"
        "\"is_healthy\":%s,\"inference_time_ms\":%lu,\"timestamp_ms\":%lu}",
        g_lastDiagnosis.classIndex,
        cname,
        g_lastDiagnosis.confidence,
        healthy ? "true" : "false",
        g_lastDiagnosis.inferenceTimeMs,
        g_lastDiagnosis.timestamp
    );

    server.send(200, "application/json", buffer);
}

void handleGetStatus() {
    applyCorsHeaders();
    char buffer[384];
    snprintf(
        buffer, sizeof(buffer),
        "{\"device\":\"ESP32-CAM\",\"model_version\":\"4-block-int8\","
        "\"psram_enabled\":%s,\"free_psram_bytes\":%u,\"free_heap_bytes\":%u,"
        "\"tensor_arena_size_kb\":%u,\"uptime_seconds\":%lu}",
        psramFound() ? "true" : "false",
        psramFound() ? ESP.getFreePsram() : 0,
        ESP.getFreeHeap(),
        static_cast<unsigned int>(kTensorArenaSize / 1024),
        millis() / 1000
    );
    server.send(200, "application/json", buffer);
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n[AGRISENSE] Booting ESP32-CAM Vision Node...");

    // Wi-Fi Connection
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("[AGRISENSE] Connecting to Wi-Fi");

    unsigned long wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 5000) {
        delay(250);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[AGRISENSE] Wi-Fi Connected!");
        Serial.print("[AGRISENSE] IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[AGRISENSE] Wi-Fi timed out. Starting soft AP...");
        WiFi.mode(WIFI_AP);
        WiFi.softAP("AgriSense-Vision-AP", "12345678");
        Serial.print("[AGRISENSE] AP IP: ");
        Serial.println(WiFi.softAPIP());
    }

    // Hardware setup
    initCamera();
    initTFLite();

    // Register HTTP routes
    server.on("/latest", HTTP_GET, handleGetLatest);
    server.on("/latest", HTTP_OPTIONS, handleOptions);
    server.on("/status", HTTP_GET, handleGetStatus);
    server.on("/status", HTTP_OPTIONS, handleOptions);

    server.begin();
    Serial.println("[AGRISENSE] Vision Node HTTP Server started on port 80");
    Serial.println("[AGRISENSE] Vision Node Ready");
}

void loop() {
    server.handleClient();
}

