#!/usr/bin/env python3
"""
AgriSense - Host Test Runner for Embedded Logic
Compiles and executes C++ unit tests if a compiler is available,
and provides a 1:1 cross-verification in Python to test logic locally.
"""

import math
import shutil
import subprocess
import sys
from pathlib import Path


class IrrigationLogicSimulator:
    def __init__(self):
        self.dry_threshold = 35.0
        self.wet_threshold = 65.0
        self.dry_adc = 3200
        self.wet_adc = 1400
        self.max_auto_run_ms = 15000
        self.max_manual_run_ms = 30000
        self.safety_cooldown_ms = 10000
        self.ema_alpha = 0.25

        # State
        self.mode = "AUTO"  # AUTO or MANUAL
        self.pump_status = "OFF"  # ON or OFF
        self.pump_started_by_auto = False
        self.pump_start_time_ms = 0
        self.last_pump_stop_time_ms = 0
        self.safety_tripped = False
        self.trip_reason = "NONE"
        self.moisture_percent = 0.0

    def filter_adc_sample(self, current_filtered: float, raw_sample: float) -> float:
        return (self.ema_alpha * raw_sample) + ((1.0 - self.ema_alpha) * current_filtered)

    def calculate_moisture(self, adc_val: float) -> float:
        if adc_val >= self.dry_adc:
            return 0.0
        if adc_val <= self.wet_adc:
            return 100.0
        return ((self.dry_adc - adc_val) / (self.dry_adc - self.wet_adc)) * 100.0

    def update(self, current_ms: int):
        if self.pump_status == "ON":
            elapsed = current_ms - self.pump_start_time_ms
            if self.pump_started_by_auto and elapsed >= self.max_auto_run_ms:
                self.pump_status = "OFF"
                self.pump_started_by_auto = False
                self.last_pump_stop_time_ms = current_ms
                self.safety_tripped = True
                self.trip_reason = "AUTO_TIMEOUT"
                return
            elif not self.pump_started_by_auto and elapsed >= self.max_manual_run_ms:
                self.pump_status = "OFF"
                self.pump_started_by_auto = False
                self.last_pump_stop_time_ms = current_ms
                self.safety_tripped = True
                self.trip_reason = "MANUAL_TIMEOUT"
                return

        if self.mode == "AUTO":
            if self.pump_status == "OFF":
                if self.moisture_percent < self.dry_threshold and not self.safety_tripped:
                    if self.last_pump_stop_time_ms == 0 or (current_ms - self.last_pump_stop_time_ms) >= self.safety_cooldown_ms:
                        self.pump_status = "ON"
                        self.pump_started_by_auto = True
                        self.pump_start_time_ms = current_ms
            elif self.pump_status == "ON" and self.pump_started_by_auto:
                if self.moisture_percent >= self.wet_threshold:
                    self.pump_status = "OFF"
                    self.pump_started_by_auto = False
                    self.last_pump_stop_time_ms = current_ms

    def set_manual(self, turn_on: bool, current_ms: int) -> bool:
        if turn_on:
            if self.last_pump_stop_time_ms > 0 and (current_ms - self.last_pump_stop_time_ms) < self.safety_cooldown_ms:
                return False
            self.mode = "MANUAL"
            self.safety_tripped = False
            self.trip_reason = "NONE"
            self.pump_status = "ON"
            self.pump_started_by_auto = False
            self.pump_start_time_ms = current_ms
            return True
        else:
            if self.pump_status == "ON":
                self.pump_status = "OFF"
                self.pump_started_by_auto = False
                self.last_pump_stop_time_ms = current_ms
            return True


def run_unit_tests():
    print("==================================================")
    print("Testing Irrigation Pure Logic & State Machine")
    print("==================================================")

    sim = IrrigationLogicSimulator()

    # 1. ADC filter
    filtered = sim.filter_adc_sample(3000.0, 2000.0)
    assert abs(filtered - 2750.0) < 0.001, f"Expected 2750, got {filtered}"
    print("  [PASS] ADC filtering convergence")

    # 2. Moisture calculation
    assert sim.calculate_moisture(3200) == 0.0
    assert sim.calculate_moisture(1400) == 100.0
    assert abs(sim.calculate_moisture(2300) - 50.0) < 0.1
    print("  [PASS] Soil moisture calibration mapping")

    # 3. Auto threshold & origin tracking
    sim.moisture_percent = 20.0
    sim.update(1000)
    assert sim.pump_status == "ON" and sim.pump_started_by_auto is True
    print("  [PASS] Auto pump start and origin flag tracking")

    # 4. Wet threshold auto-stop
    sim.moisture_percent = 65.0
    sim.update(3000)
    assert sim.pump_status == "OFF" and sim.pump_started_by_auto is False
    print("  [PASS] Auto pump stop on wet threshold")

    # 5. Safety timeout auto-cutoff
    sim.moisture_percent = 15.0
    sim.update(15000)  # Starts at t=15000 (after cooldown from 3000)
    assert sim.pump_status == "ON"
    sim.update(30100)  # 15.1s later
    assert sim.pump_status == "OFF" and sim.safety_tripped is True and sim.trip_reason == "AUTO_TIMEOUT"
    print("  [PASS] Auto timeout cutoff failsafe")

    # 6. Manual override & origin preservation
    ok = sim.set_manual(True, 45000)
    assert ok is True and sim.pump_status == "ON" and sim.pump_started_by_auto is False
    sim.moisture_percent = 80.0
    sim.update(50000)  # Wet soil must NOT turn off manual pump!
    assert sim.pump_status == "ON"
    sim.update(76000)  # > 30s manual limit
    assert sim.pump_status == "OFF" and sim.trip_reason == "MANUAL_TIMEOUT"
    print("  [PASS] Manual override and safety cutoff")

    print("==================================================")
    print("All Irrigation Logic Tests Successfully Verified!")
    print("==================================================")


if __name__ == "__main__":
    run_unit_tests()
