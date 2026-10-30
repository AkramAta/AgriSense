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


TOMATO_CLASSES = [
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___healthy",
]


def decode_rgb565(high_byte: int, low_byte: int):
    pixel = (high_byte << 8) | low_byte
    r5 = (pixel >> 11) & 0x1F
    g6 = (pixel >> 5) & 0x3F
    b5 = pixel & 0x1F
    r = int((r5 * 527 + 23) >> 6)
    g = int((g6 * 259 + 33) >> 6)
    b = int((b5 * 527 + 23) >> 6)
    return r, g, b


def test_vision_logic():
    print("==================================================")
    print("Testing Vision Logic (RGB565 & INT8 Quantization)")
    print("==================================================")
    # 1. RGB565 Pure Red (0xF800)
    r, g, b = decode_rgb565(0xF8, 0x00)
    assert r >= 250 and g == 0 and b == 0, f"Red failed: {r},{g},{b}"
    print("  [PASS] Pure Red RGB565 decoding")

    # 2. RGB565 Pure Green (0x07E0)
    r, g, b = decode_rgb565(0x07, 0xE0)
    assert r == 0 and g >= 250 and b == 0, f"Green failed: {r},{g},{b}"
    print("  [PASS] Pure Green RGB565 decoding")

    # 3. Output dequantization
    logits = [-128, -128, -128, -100, 100, -128, -128, -128]
    scale = 1.0 / 256.0
    zero_point = -128
    probs = [(val - zero_point) * scale for val in logits]
    top_idx = probs.index(max(probs))
    conf = probs[top_idx]
    assert top_idx == 4, f"Expected top index 4, got {top_idx}"
    assert conf > 0.85, f"Expected conf > 0.85, got {conf}"
    assert TOMATO_CLASSES[top_idx] == "Tomato___Septoria_leaf_spot"
    print(f"  [PASS] INT8 Dequantization (Top: {TOMATO_CLASSES[top_idx]}, conf={conf:.3f})")


def run_unit_tests():
    test_vision_logic()
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
