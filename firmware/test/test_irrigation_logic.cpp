/**
 * Host-Side C++ Unit Tests for AgriSense Irrigation Logic
 * Tests threshold switching, origin tracking, and auto-cutoff safety without hardware.
 */

#include <cassert>
#include <cmath>
#include <iostream>
#include "../irrigation_node/irrigation_logic.h"

using namespace agrisense;

void test_filter_adc_sample() {
    std::cout << "[TEST] Running test_filter_adc_sample..." << std::endl;
    float current = 3000.0f;
    float sample = 2000.0f;
    float alpha = 0.25f;

    float filtered = filterAdcSample(current, sample, alpha);
    // 0.25 * 2000 + 0.75 * 3000 = 500 + 2250 = 2750
    assert(std::abs(filtered - 2750.0f) < 0.001f);

    // Alpha bounds
    assert(filterAdcSample(current, sample, 0.0f) == current);
    assert(filterAdcSample(current, sample, 1.0f) == sample);
    std::cout << "  -> PASS\n";
}

void test_moisture_calculation() {
    std::cout << "[TEST] Running test_moisture_calculation..." << std::endl;
    uint32_t dry = 3200;
    uint32_t wet = 1400;

    // Dry boundary
    assert(calculateMoisturePercent(3200.0f, dry, wet) == 0.0f);
    assert(calculateMoisturePercent(3500.0f, dry, wet) == 0.0f);

    // Wet boundary
    assert(calculateMoisturePercent(1400.0f, dry, wet) == 100.0f);
    assert(calculateMoisturePercent(1000.0f, dry, wet) == 100.0f);

    // Midpoint (2300 ADC -> exactly 50% moisture)
    float mid = calculateMoisturePercent(2300.0f, dry, wet);
    assert(std::abs(mid - 50.0f) < 0.1f);
    std::cout << "  -> PASS\n";
}

void test_auto_threshold_and_origin_tracking() {
    std::cout << "[TEST] Running test_auto_threshold_and_origin_tracking..." << std::endl;
    IrrigationConfig cfg;
    IrrigationState state;
    uint32_t now = 1000;

    // Initial state: Auto mode, dry soil (20% moisture < 35% threshold)
    state.moisturePercent = 20.0f;
    updateIrrigationStateMachine(state, cfg, now);

    assert(state.pumpStatus == PUMP_ON);
    assert(state.pumpStartedByAuto == true);
    assert(state.pumpStartTimeMs == now);
    assert(!state.safetyTripped);

    // Moisture increases to 40% (still below wet 65% threshold): pump should stay ON
    now += 2000;
    state.moisturePercent = 40.0f;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_ON);
    assert(state.pumpStartedByAuto == true);

    // Moisture reaches 65% (wet threshold): pump should turn OFF
    now += 2000;
    state.moisturePercent = 65.0f;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_OFF);
    assert(state.pumpStartedByAuto == false);
    assert(state.lastPumpStopTimeMs == now);
    std::cout << "  -> PASS\n";
}

void test_auto_safety_timeout_cutoff() {
    std::cout << "[TEST] Running test_auto_safety_timeout_cutoff..." << std::endl;
    IrrigationConfig cfg;
    cfg.maxAutoRunDurationMs = 15000; // 15 sec
    IrrigationState state;
    uint32_t now = 5000;

    // Turn pump ON in dry conditions
    state.moisturePercent = 15.0f;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_ON);
    assert(state.pumpStartedByAuto == true);

    // Advance 14.9s: should still be running
    now += 14900;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_ON);

    // Advance to 15.1s: pump must be cutoff by auto safety timeout
    now += 200;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_OFF);
    assert(state.safetyTripped == true);
    assert(state.tripReason == TRIP_AUTO_TIMEOUT);
    assert(state.pumpStartedByAuto == false);

    // Next tick with dry soil must NOT restart pump while safety is tripped
    now += 1000;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_OFF);
    std::cout << "  -> PASS\n";
}

void test_cooldown_enforcement() {
    std::cout << "[TEST] Running test_cooldown_enforcement..." << std::endl;
    IrrigationConfig cfg;
    cfg.safetyCooldownMs = 10000; // 10 sec cooldown
    IrrigationState state;
    uint32_t now = 1000;

    // Pump runs and turns off at t = 2000
    state.moisturePercent = 20.0f;
    updateIrrigationStateMachine(state, cfg, now);
    now = 2000;
    state.moisturePercent = 70.0f;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_OFF);
    assert(state.lastPumpStopTimeMs == 2000);

    // Soil immediately dries again at t = 5000 (only 3s elapsed, < 10s cooldown)
    now = 5000;
    state.moisturePercent = 20.0f;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_OFF); // Guarded by cooldown!

    // Advance past cooldown to t = 12001 (10.001s elapsed)
    now = 12001;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_ON); // Permitted after cooldown
    std::cout << "  -> PASS\n";
}

void test_manual_override_and_origin_tracking() {
    std::cout << "[TEST] Running test_manual_override_and_origin_tracking..." << std::endl;
    IrrigationConfig cfg;
    cfg.maxManualRunDurationMs = 30000; // 30s
    IrrigationState state;
    uint32_t now = 1000;

    // Start pump manually
    bool ok = setManualPump(state, cfg, true, now);
    assert(ok == true);
    assert(state.mode == MODE_MANUAL);
    assert(state.pumpStatus == PUMP_ON);
    assert(state.pumpStartedByAuto == false); // Origin tracking!

    // Soil is wet (75% > 65%): state machine must NOT cut off manual pump!
    now += 5000;
    state.moisturePercent = 75.0f;
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_ON);
    assert(state.pumpStartedByAuto == false);

    // Exceed manual safety timeout (30s)
    now += 26000; // Total 31s elapsed
    updateIrrigationStateMachine(state, cfg, now);
    assert(state.pumpStatus == PUMP_OFF);
    assert(state.safetyTripped == true);
    assert(state.tripReason == TRIP_MANUAL_TIMEOUT);

    // Reset safety trip
    resetSafetyTrip(state);
    assert(!state.safetyTripped);
    assert(state.tripReason == TRIP_NONE);
    std::cout << "  -> PASS\n";
}

int main() {
    std::cout << "========================================\n";
    std::cout << "AgriSense Irrigation Logic Test Suite\n";
    std::cout << "========================================\n";

    test_filter_adc_sample();
    test_moisture_calculation();
    test_auto_threshold_and_origin_tracking();
    test_auto_safety_timeout_cutoff();
    test_cooldown_enforcement();
    test_manual_override_and_origin_tracking();

    std::cout << "========================================\n";
    std::cout << "All 6 Irrigation Logic Unit Tests PASSED!\n";
    std::cout << "========================================\n";
    return 0;
}
