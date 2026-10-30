/**
 * AgriSense - ESP32 Smart Irrigation Node
 * Features:
 * - Soil Moisture ADC sampling with single-pole IIR filtering.
 * - DHT11 Ambient Temperature & Relative Humidity sensing.
 * - Solid State Relay pump driver with origin-tracking failsafe auto-cutoff.
 * - Embedded HTTP REST API for Flutter client telemetry and controls.
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>
#include "irrigation_logic.h"

// Hardware Pin Definitions
#define DHTPIN 4
#define DHTTYPE DHT11
#define SOIL_ADC_PIN 34
#define RELAY_PIN 26
#define STATUS_LED_PIN 2

// Relay logic: Active HIGH
#define RELAY_ON HIGH
#define RELAY_OFF LOW

// Wi-Fi Credentials (fallback to AP mode if connection times out)
const char* WIFI_SSID = "AgriSense-Field";
const char* WIFI_PASS = "agrisense2026";

// Sensor instances and logic state
DHT dht(DHTPIN, DHTTYPE);
WebServer server(80);
agrisense::IrrigationConfig g_config;
agrisense::IrrigationState g_state;

unsigned long g_lastSampleMs = 0;
const unsigned long SAMPLE_INTERVAL_MS = 500;

void setRelayHardware(bool active) {
    digitalWrite(RELAY_PIN, active ? RELAY_ON : RELAY_OFF);
    digitalWrite(STATUS_LED_PIN, active ? HIGH : LOW);
}

void applyCorsHeaders() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleOptions() {
    applyCorsHeaders();
    server.send(204);
}

void handleGetSensors() {
    applyCorsHeaders();
    char buffer[256];
    snprintf(
        buffer, sizeof(buffer),
        "{\"moisture_percent\":%.2f,\"temperature_c\":%.2f,\"humidity_percent\":%.2f,"
        "\"raw_adc\":%.1f,\"filtered_adc\":%.1f,\"timestamp_ms\":%lu}",
        g_state.moisturePercent,
        g_state.temperatureC,
        g_state.humidityPercent,
        g_state.rawAdc,
        g_state.filteredAdc,
        millis()
    );
    server.send(200, "application/json", buffer);
}

void handleGetStatus() {
    applyCorsHeaders();
    char buffer[384];
    snprintf(
        buffer, sizeof(buffer),
        "{\"mode\":\"%s\",\"pump_status\":\"%s\",\"pump_started_by_auto\":%s,"
        "\"safety_tripped\":%s,\"trip_reason\":%u,\"uptime_seconds\":%lu,"
        "\"moisture_percent\":%.2f,\"temperature_c\":%.2f,\"humidity_percent\":%.2f}",
        g_state.mode == agrisense::MODE_AUTO ? "AUTO" : "MANUAL",
        g_state.pumpStatus == agrisense::PUMP_ON ? "ON" : "OFF",
        g_state.pumpStartedByAuto ? "true" : "false",
        g_state.safetyTripped ? "true" : "false",
        static_cast<unsigned int>(g_state.tripReason),
        millis() / 1000,
        g_state.moisturePercent,
        g_state.temperatureC,
        g_state.humidityPercent
    );
    server.send(200, "application/json", buffer);
}

void handlePostPumpAuto() {
    applyCorsHeaders();
    bool enable = true;
    if (server.hasArg("enabled")) {
        String val = server.arg("enabled");
        enable = (val == "true" || val == "1");
    } else if (server.hasArg("plain")) {
        String body = server.arg("plain");
        if (body.indexOf("\"enabled\":false") >= 0 || body.indexOf("\"enabled\": false") >= 0) {
            enable = false;
        }
    }

    agrisense::setAutoMode(g_state, enable);
    server.send(200, "application/json", enable ? "{\"status\":\"success\",\"mode\":\"AUTO\"}" : "{\"status\":\"success\",\"mode\":\"MANUAL\"}");
}

void handlePostPumpManual() {
    applyCorsHeaders();
    bool turnOn = false;
    if (server.hasArg("state")) {
        String s = server.arg("state");
        turnOn = (s == "on" || s == "1" || s == "start");
    } else if (server.hasArg("action")) {
        String a = server.arg("action");
        turnOn = (a == "start" || a == "on");
    } else if (server.hasArg("plain")) {
        String body = server.arg("plain");
        if (body.indexOf("\"action\":\"start\"") >= 0 || body.indexOf("\"action\": \"start\"") >= 0 ||
            body.indexOf("\"state\":\"on\"") >= 0 || body.indexOf("\"state\": \"on\"") >= 0) {
            turnOn = true;
        }
    }

    bool success = agrisense::setManualPump(g_state, g_config, turnOn, millis());
    setRelayHardware(g_state.pumpStatus == agrisense::PUMP_ON);

    char buffer[128];
    snprintf(
        buffer, sizeof(buffer),
        "{\"status\":\"%s\",\"pump_status\":\"%s\",\"safety_tripped\":%s}",
        success ? "success" : "rejected_cooldown",
        g_state.pumpStatus == agrisense::PUMP_ON ? "ON" : "OFF",
        g_state.safetyTripped ? "true" : "false"
    );
    server.send(success ? 200 : 429, "application/json", buffer);
}

void handlePostResetSafety() {
    applyCorsHeaders();
    agrisense::resetSafetyTrip(g_state);
    server.send(200, "application/json", "{\"status\":\"success\",\"safety_tripped\":false}");
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n[AGRISENSE] Booting ESP32 Irrigation Node...");

    // Setup GPIO
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(STATUS_LED_PIN, OUTPUT);
    setRelayHardware(false); // Failsafe pump off

    // Setup DHT
    dht.begin();

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
        Serial.print("[AGRISENSE] IP Address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[AGRISENSE] Wi-Fi connection timed out. Starting fallback Access Point...");
        WiFi.mode(WIFI_AP);
        WiFi.softAP("AgriSense-Node-AP", "12345678");
        Serial.print("[AGRISENSE] AP IP Address: ");
        Serial.println(WiFi.softAPIP());
    }

    // Configure HTTP endpoints
    server.on("/sensors", HTTP_GET, handleGetSensors);
    server.on("/sensors", HTTP_OPTIONS, handleOptions);
    server.on("/status", HTTP_GET, handleGetStatus);
    server.on("/status", HTTP_OPTIONS, handleOptions);
    server.on("/status/reset", HTTP_POST, handlePostResetSafety);
    server.on("/status/reset", HTTP_OPTIONS, handleOptions);
    server.on("/pump/auto", HTTP_POST, handlePostPumpAuto);
    server.on("/pump/auto", HTTP_OPTIONS, handleOptions);
    server.on("/pump/manual", HTTP_POST, handlePostPumpManual);
    server.on("/pump/manual", HTTP_OPTIONS, handleOptions);

    server.begin();
    Serial.println("[AGRISENSE] HTTP Server listening on port 80");
    Serial.println("[AGRISENSE] Irrigation Node Ready");
}

void loop() {
    server.handleClient();

    unsigned long now = millis();
    if (now - g_lastSampleMs >= SAMPLE_INTERVAL_MS) {
        g_lastSampleMs = now;

        // 1. Read Soil Moisture ADC
        int raw = analogRead(SOIL_ADC_PIN);
        g_state.rawAdc = static_cast<float>(raw);
        g_state.filteredAdc = agrisense::filterAdcSample(g_state.filteredAdc, g_state.rawAdc, g_config.emaAlpha);
        g_state.moisturePercent = agrisense::calculateMoisturePercent(
            g_state.filteredAdc, g_config.dryCalibrationAdc, g_config.wetCalibrationAdc
        );

        // 2. Read DHT11
        float t = dht.readTemperature();
        float h = dht.readHumidity();
        if (!isnan(t)) g_state.temperatureC = t;
        if (!isnan(h)) g_state.humidityPercent = h;

        // 3. Evaluate State Machine
        agrisense::updateIrrigationStateMachine(g_state, g_config, now);

        // 4. Update Hardware Relay State
        setRelayHardware(g_state.pumpStatus == agrisense::PUMP_ON);
    }
}

