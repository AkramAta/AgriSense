#ifndef IRRIGATION_LOGIC_H_
#define IRRIGATION_LOGIC_H_

#include <cstdint>
#include <algorithm>

namespace agrisense {

enum IrrigationMode : uint8_t {
    MODE_AUTO = 0,
    MODE_MANUAL = 1
};

enum PumpStatus : uint8_t {
    PUMP_OFF = 0,
    PUMP_ON = 1
};

enum TripReason : uint8_t {
    TRIP_NONE = 0,
    TRIP_AUTO_TIMEOUT = 1,
    TRIP_MANUAL_TIMEOUT = 2,
    TRIP_SENSOR_FAULT = 3
};

struct IrrigationConfig {
    float dryThresholdPercent = 35.0f;       // Below this triggers auto irrigation
    float wetThresholdPercent = 65.0f;       // Above this stops auto irrigation
    uint32_t dryCalibrationAdc = 3200;       // Air / Completely dry soil ADC (12-bit)
    uint32_t wetCalibrationAdc = 1400;       // Saturated water ADC (12-bit)
    uint32_t maxAutoRunDurationMs = 15000;   // 15 seconds max continuous auto run
    uint32_t maxManualRunDurationMs = 30000; // 30 seconds max continuous manual run
    uint32_t safetyCooldownMs = 10000;       // 10 seconds mandatory cooldown between cycles
    float emaAlpha = 0.25f;                  // Exponential moving average filter factor
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
    float temperatureC = 24.0f;
    float humidityPercent = 50.0f;

    bool safetyTripped = false;
    TripReason tripReason = TRIP_NONE;
};

/**
 * Single-pole IIR Exponential Moving Average (EMA) filter.
 * Output = alpha * rawSample + (1 - alpha) * currentFiltered
 */
inline float filterAdcSample(float currentFiltered, float rawSample, float alpha) {
    if (alpha <= 0.0f) return currentFiltered;
    if (alpha >= 1.0f) return rawSample;
    return (alpha * rawSample) + ((1.0f - alpha) * currentFiltered);
}

/**
 * Inverse linear interpolation mapping ADC value to calibrated volumetric moisture percentage.
 * Higher ADC represents drier soil; lower ADC represents saturated soil.
 */
inline float calculateMoisturePercent(float adcValue, uint32_t dryAdc, uint32_t wetAdc) {
    if (dryAdc <= wetAdc) {
        return 0.0f; // Invalid calibration guard
    }
    if (adcValue >= static_cast<float>(dryAdc)) {
        return 0.0f;
    }
    if (adcValue <= static_cast<float>(wetAdc)) {
        return 100.0f;
    }
    float span = static_cast<float>(dryAdc - wetAdc);
    float offset = static_cast<float>(dryAdc) - adcValue;
    return (offset / span) * 100.0f;
}

/**
 * Validates whether the pump is permitted to activate under current safety constraints.
 */
inline bool canStartPump(const IrrigationState& state, const IrrigationConfig& config, uint32_t currentMs) {
    if (state.safetyTripped) {
        return false;
    }
    // Check mandatory cooldown window if pump has run previously
    if (state.lastPumpStopTimeMs > 0 && (currentMs - state.lastPumpStopTimeMs) < config.safetyCooldownMs) {
        return false;
    }
    return true;
}

/**
 * Pure state machine update step called every sensor sampling interval.
 */
inline void updateIrrigationStateMachine(IrrigationState& state, const IrrigationConfig& config, uint32_t currentMs) {
    // 1. Safety check for running pump timeouts
    if (state.pumpStatus == PUMP_ON) {
        uint32_t elapsedMs = currentMs - state.pumpStartTimeMs;
        if (state.pumpStartedByAuto && elapsedMs >= config.maxAutoRunDurationMs) {
            state.pumpStatus = PUMP_OFF;
            state.pumpStartedByAuto = false;
            state.lastPumpStopTimeMs = currentMs;
            state.safetyTripped = true;
            state.tripReason = TRIP_AUTO_TIMEOUT;
            return;
        } else if (!state.pumpStartedByAuto && elapsedMs >= config.maxManualRunDurationMs) {
            state.pumpStatus = PUMP_OFF;
            state.pumpStartedByAuto = false;
            state.lastPumpStopTimeMs = currentMs;
            state.safetyTripped = true;
            state.tripReason = TRIP_MANUAL_TIMEOUT;
            return;
        }
    }

    // 2. Automated threshold hysteresis
    if (state.mode == MODE_AUTO) {
        if (state.pumpStatus == PUMP_OFF) {
            if (state.moisturePercent < config.dryThresholdPercent) {
                if (canStartPump(state, config, currentMs)) {
                    state.pumpStatus = PUMP_ON;
                    state.pumpStartedByAuto = true;
                    state.pumpStartTimeMs = currentMs;
                }
            }
        } else if (state.pumpStatus == PUMP_ON && state.pumpStartedByAuto) {
            if (state.moisturePercent >= config.wetThresholdPercent) {
                state.pumpStatus = PUMP_OFF;
                state.pumpStartedByAuto = false;
                state.lastPumpStopTimeMs = currentMs;
            }
        }
    }
}

/**
 * User-initiated manual pump toggle.
 */
inline bool setManualPump(IrrigationState& state, const IrrigationConfig& config, bool turnOn, uint32_t currentMs) {
    if (turnOn) {
        // Clear previous safety trip on explicit manual override if cooldown allows
        if (state.lastPumpStopTimeMs > 0 && (currentMs - state.lastPumpStopTimeMs) < config.safetyCooldownMs) {
            return false; // Cooldown not yet satisfied
        }
        state.mode = MODE_MANUAL;
        state.safetyTripped = false;
        state.tripReason = TRIP_NONE;
        state.pumpStatus = PUMP_ON;
        state.pumpStartedByAuto = false;
        state.pumpStartTimeMs = currentMs;
        return true;
    } else {
        if (state.pumpStatus == PUMP_ON) {
            state.pumpStatus = PUMP_OFF;
            state.pumpStartedByAuto = false;
            state.lastPumpStopTimeMs = currentMs;
        }
        return true;
    }
}

/**
 * Toggle between automatic threshold-based control and manual override.
 */
inline void setAutoMode(IrrigationState& state, bool enable) {
    if (enable) {
        state.mode = MODE_AUTO;
    } else {
        state.mode = MODE_MANUAL;
    }
}

/**
 * Resets safety trip condition after manual audit.
 */
inline void resetSafetyTrip(IrrigationState& state) {
    state.safetyTripped = false;
    state.tripReason = TRIP_NONE;
}

} // namespace agrisense

#endif // IRRIGATION_LOGIC_H_

