/**
 * AgriSense - ESP32 Smart Irrigation Node (Wokwi Simulation)
 * ==========================================================
 * Paste this entire code into the "sketch.ino" tab in Wokwi (https://wokwi.com/esp32)
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>
#include <cstdint>
#include <algorithm>

// Pin Definitions
#define DHTPIN 4
#define DHTTYPE DHT22
#define SOIL_ADC_PIN 34
#define RELAY_PIN 26
#define STATUS_LED_PIN 2

#define RELAY_ON HIGH
#define RELAY_OFF LOW

// Wokwi Virtual WiFi
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

enum IrrigationMode : uint8_t { MODE_AUTO = 0, MODE_MANUAL = 1 };
enum PumpStatus : uint8_t { PUMP_OFF = 0, PUMP_ON = 1 };
enum TripReason : uint8_t {
    TRIP_NONE = 0,
    TRIP_AUTO_TIMEOUT = 1,
    TRIP_MANUAL_TIMEOUT = 2,
    TRIP_SENSOR_FAULT = 3
};

struct IrrigationConfig {
    float dryThresholdPercent = 35.0f;       // Below this triggers auto irrigation
    float wetThresholdPercent = 65.0f;       // Above this stops auto irrigation
    uint32_t dryCalibrationAdc = 3200;       // Dry soil ADC (12-bit)
    uint32_t wetCalibrationAdc = 1400;       // Wet soil ADC (12-bit)
    uint32_t maxAutoRunDurationMs = 15000;   // 15 seconds max continuous auto run
    uint32_t maxManualRunDurationMs = 30000; // 30 seconds max manual run
    uint32_t safetyCooldownMs = 10000;       // 10 seconds cooldown between cycles
    float emaAlpha = 0.25f;                  // EMA filter factor
};

struct IrrigationState {
    IrrigationMode mode = MODE_AUTO;
    PumpStatus pumpStatus = PUMP_OFF;
    bool pumpStartedByAuto = false;
    uint32_t pumpStartTimeMs = 0;
    uint32_t lastPumpStopTimeMs = 0;

    float rawAdc = 3200.0f;
    float filteredAdc = 3200.0f;
    float moisturePercent = 0.0f;
    float temperatureC = 24.5f;
    float humidityPercent = 58.0f;

    bool safetyTripped = false;
    TripReason tripReason = TRIP_NONE;
};

inline float filterAdcSample(float currentFiltered, float rawSample, float alpha) {
    if (alpha <= 0.0f) return currentFiltered;
    if (alpha >= 1.0f) return rawSample;
    return (alpha * rawSample) + ((1.0f - alpha) * currentFiltered);
}

inline float calculateMoisturePercent(float adcValue, uint32_t dryAdc, uint32_t wetAdc) {
    if (dryAdc <= wetAdc) return 0.0f;
    if (adcValue >= static_cast<float>(dryAdc)) return 0.0f;
    if (adcValue <= static_cast<float>(wetAdc)) return 100.0f;
    float span = static_cast<float>(dryAdc - wetAdc);
    float offset = static_cast<float>(dryAdc) - adcValue;
    return (offset / span) * 100.0f;
}

inline bool canStartPump(const IrrigationState& state, const IrrigationConfig& config, uint32_t currentMs) {
    if (state.safetyTripped) return false;
    if (state.lastPumpStopTimeMs > 0 && (currentMs - state.lastPumpStopTimeMs) < config.safetyCooldownMs) {
        return false;
    }
    return true;
}

inline void updateIrrigationStateMachine(IrrigationState& state, const IrrigationConfig& config, uint32_t currentMs) {
    if (state.pumpStatus == PUMP_ON) {
        uint32_t runDuration = currentMs - state.pumpStartTimeMs;
        if (state.pumpStartedByAuto && runDuration >= config.maxAutoRunDurationMs) {
            state.pumpStatus = PUMP_OFF;
            state.pumpStartedByAuto = false;
            state.lastPumpStopTimeMs = currentMs;
            state.safetyTripped = true;
            state.tripReason = TRIP_AUTO_TIMEOUT;
            Serial.println("[SAFETY ALERT] Auto pump run exceeded 15s limit! Safety cut-off tripped.");
            return;
        } else if (!state.pumpStartedByAuto && runDuration >= config.maxManualRunDurationMs) {
            state.pumpStatus = PUMP_OFF;
            state.pumpStartedByAuto = false;
            state.lastPumpStopTimeMs = currentMs;
            state.safetyTripped = true;
            state.tripReason = TRIP_MANUAL_TIMEOUT;
            Serial.println("[SAFETY ALERT] Manual pump run exceeded 30s limit! Safety cut-off tripped.");
            return;
        }
    }

    if (state.mode == MODE_AUTO) {
        if (state.pumpStatus == PUMP_OFF) {
            if (state.moisturePercent < config.dryThresholdPercent && canStartPump(state, config, currentMs)) {
                state.pumpStatus = PUMP_ON;
                state.pumpStartedByAuto = true;
                state.pumpStartTimeMs = currentMs;
                Serial.printf("[AUTOMATION] Moisture (%.1f%%) < 35%% -> PUMP STARTED\n", state.moisturePercent);
            }
        } else if (state.pumpStatus == PUMP_ON && state.pumpStartedByAuto) {
            if (state.moisturePercent >= config.wetThresholdPercent) {
                state.pumpStatus = PUMP_OFF;
                state.pumpStartedByAuto = false;
                state.lastPumpStopTimeMs = currentMs;
                Serial.printf("[AUTOMATION] Moisture (%.1f%%) >= 65%% -> PUMP STOPPED\n", state.moisturePercent);
            }
        }
    }
}

DHT dht(DHTPIN, DHTTYPE);
WebServer server(80);
IrrigationConfig g_config;
IrrigationState g_state;

unsigned long g_lastSampleMs = 0;
unsigned long g_lastLogMs = 0;
const unsigned long SAMPLE_INTERVAL_MS = 250;

void setRelayHardware(bool active) {
    digitalWrite(RELAY_PIN, active ? RELAY_ON : RELAY_OFF);
    digitalWrite(STATUS_LED_PIN, active ? HIGH : LOW);
}

void applyCorsHeaders() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleGetSensors() {
    applyCorsHeaders();
    char buffer[256];
    snprintf(buffer, sizeof(buffer),
        "{\"moisture_percent\":%.2f,\"temperature_c\":%.2f,\"humidity_percent\":%.2f,"
        "\"raw_adc\":%.1f,\"filtered_adc\":%.1f,\"timestamp_ms\":%lu}",
        g_state.moisturePercent, g_state.temperatureC, g_state.humidityPercent,
        g_state.rawAdc, g_state.filteredAdc, millis());
    server.send(200, "application/json", buffer);
}

void handleGetStatus() {
    applyCorsHeaders();
    char buffer[384];
    snprintf(buffer, sizeof(buffer),
        "{\"mode\":\"%s\",\"pump_status\":\"%s\",\"pump_started_by_auto\":%s,"
        "\"safety_tripped\":%s,\"trip_reason\":%u,\"uptime_seconds\":%lu,"
        "\"moisture_percent\":%.2f,\"temperature_c\":%.2f,\"humidity_percent\":%.2f}",
        g_state.mode == MODE_AUTO ? "AUTO" : "MANUAL",
        g_state.pumpStatus == PUMP_ON ? "ON" : "OFF",
        g_state.pumpStartedByAuto ? "true" : "false",
        g_state.safetyTripped ? "true" : "false",
        static_cast<unsigned int>(g_state.tripReason),
        millis() / 1000,
        g_state.moisturePercent, g_state.temperatureC, g_state.humidityPercent);
    server.send(200, "application/json", buffer);
}

void handlePostPumpAuto() {
    applyCorsHeaders();
    g_state.mode = MODE_AUTO;
    Serial.println("[REST API] Mode set to AUTO");
    server.send(200, "application/json", "{\"status\":\"success\",\"mode\":\"AUTO\"}");
}

void handlePostPumpManual() {
    applyCorsHeaders();
    bool turnOn = true;
    if (server.hasArg("action")) {
        turnOn = (server.arg("action") == "start" || server.arg("action") == "on");
    }
    uint32_t now = millis();
    g_state.mode = MODE_MANUAL;
    if (turnOn) {
        g_state.pumpStatus = PUMP_ON;
        g_state.pumpStartedByAuto = false;
        g_state.pumpStartTimeMs = now;
        g_state.safetyTripped = false;
        Serial.println("[REST API] Manual PUMP ON");
    } else {
        g_state.pumpStatus = PUMP_OFF;
        g_state.pumpStartedByAuto = false;
        g_state.lastPumpStopTimeMs = now;
        Serial.println("[REST API] Manual PUMP OFF");
    }
    server.send(200, "application/json", "{\"status\":\"success\",\"mode\":\"MANUAL\"}");
}

void handlePostResetSafety() {
    applyCorsHeaders();
    g_state.safetyTripped = false;
    g_state.tripReason = TRIP_NONE;
    Serial.println("[REST API] Safety Reset");
    server.send(200, "application/json", "{\"status\":\"success\",\"safety_tripped\":false}");
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n==============================================");
    Serial.println("🌿 AgriSense ESP32 Smart Irrigation Node (Wokwi)");
    Serial.println("==============================================");

    pinMode(RELAY_PIN, OUTPUT);
    pinMode(STATUS_LED_PIN, OUTPUT);
    setRelayHardware(false);

    dht.begin();

    // WiFi
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("[WIFI] Connecting to Wokwi-GUEST");

    unsigned long wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 8000) {
        delay(300);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected! IP: " + WiFi.localIP().toString());
    } else {
        Serial.println("\n[WIFI] Soft-AP Mode. IP: 192.168.4.1");
        WiFi.mode(WIFI_AP);
        WiFi.softAP("AgriSense-Node-AP", "12345678");
    }

    server.on("/sensors", HTTP_GET, handleGetSensors);
    server.on("/status", HTTP_GET, handleGetStatus);
    server.on("/pump/auto", HTTP_POST, handlePostPumpAuto);
    server.on("/pump/manual", HTTP_POST, handlePostPumpManual);
    server.on("/status/reset", HTTP_POST, handlePostResetSafety);
    server.begin();

    Serial.println("[HTTP] Server ready on port 80");
    Serial.println("[STATUS] State machine active. Telemetry running...\n");
}

void loop() {
    server.handleClient();

    unsigned long now = millis();
    if (now - g_lastSampleMs >= SAMPLE_INTERVAL_MS) {
        g_lastSampleMs = now;

        // 1. Soil Moisture (ADC Pin 34)
        int raw = analogRead(SOIL_ADC_PIN);
        g_state.rawAdc = static_cast<float>(raw);
        g_state.filteredAdc = filterAdcSample(g_state.filteredAdc, g_state.rawAdc, g_config.emaAlpha);
        g_state.moisturePercent = calculateMoisturePercent(
            g_state.filteredAdc, g_config.dryCalibrationAdc, g_config.wetCalibrationAdc
        );

        // 2. DHT11
        float t = dht.readTemperature();
        float h = dht.readHumidity();
        if (!isnan(t)) g_state.temperatureC = t;
        if (!isnan(h)) g_state.humidityPercent = h;

        // 3. State machine & relay
        updateIrrigationStateMachine(g_state, g_config, now);
        setRelayHardware(g_state.pumpStatus == PUMP_ON);
    }

    // Serial Monitor log every 2 seconds
    if (now - g_lastLogMs >= 2000) {
        g_lastLogMs = now;
        Serial.printf("[TELEMETRY] Moisture: %5.1f%% (ADC:%4.0f) | Temp: %4.1fC | Hum: %4.1f%% | Pump: %s | Safety: %s\n",
            g_state.moisturePercent,
            g_state.filteredAdc,
            g_state.temperatureC,
            g_state.humidityPercent,
            g_state.pumpStatus == PUMP_ON ? "ON [ACTIVE]" : "OFF",
            g_state.safetyTripped ? "TRIPPED!" : "NORMAL"
        );
    }
}

