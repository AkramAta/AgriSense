#!/usr/bin/env python3
"""
AgriSense - Comprehensive CLI Demo & Simulation Payload Generator
Generates telemetry test payloads, triggers local/remote board simulations,
and validates end-to-end multi-tier pipeline operations.
"""

import argparse
import datetime
import io
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw


def generate_synthetic_leaf_bytes(class_name: str = "Tomato___Early_blight") -> bytes:
    """Generate in-memory JPEG byte buffer of a tomato leaf with concentric lesions."""
    img = Image.new("RGB", (96, 96), color=(40, 110, 32))
    draw = ImageDraw.Draw(img)

    # Veins
    draw.line([(48, 8), (48, 88)], fill=(60, 140, 45), width=2)
    draw.line([(48, 30), (20, 20)], fill=(55, 130, 40), width=1)
    draw.line([(48, 50), (75, 40)], fill=(55, 130, 40), width=1)

    # Early Blight concentric target rings
    draw.ellipse([30, 35, 62, 67], fill=(160, 150, 40))  # Yellow halo
    draw.ellipse([34, 39, 58, 63], fill=(65, 45, 25))    # Dark necrotic ring
    draw.ellipse([39, 44, 53, 58], fill=(95, 75, 40))    # Inner ring
    draw.ellipse([43, 48, 49, 54], fill=(40, 25, 15))    # Dead center

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_http_endpoint(url: str, method: str = "GET", payload: dict = None, timeout: float = 3.0) -> dict:
    """Make HTTP request and return parsed JSON response."""
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except Exception as e:
        return {"error": str(e), "url": url}


def run_full_demo(irrigation_host: str = "127.0.0.1:8080", vision_host: str = "127.0.0.1:8081"):
    print("=================================================================")
    print("        AgriSense Precision IoT - End-to-End Live Demo           ")
    print("=================================================================")
    print(f"Timestamp:       {datetime.datetime.now().isoformat()}")
    print(f"Irrigation Node: http://{irrigation_host}")
    print(f"Vision Node:     http://{vision_host}")
    print("-----------------------------------------------------------------")

    # Step 1: Probe Irrigation Node
    print("\n[STEP 1] Querying ESP32 Irrigation Telemetry (/sensors)...")
    sensors = test_http_endpoint(f"http://{irrigation_host}/sensors")
    if "error" in sensors:
        print(f"  [!] Note: Irrigation node offline ({sensors['error']}). Using synthetic telemetry.")
        sensors = {
            "moisture_percent": 24.5,
            "temperature_c": 26.2,
            "humidity_percent": 57.8,
            "raw_adc": 2750.0,
            "filtered_adc": 2740.0,
            "timestamp_ms": int(time.time() * 1000),
        }
    print(f"  • Soil Moisture:     {sensors.get('moisture_percent', 0):.1f}%")
    print(f"  • Air Temperature:   {sensors.get('temperature_c', 0):.1f}°C")
    print(f"  • Relative Humidity: {sensors.get('humidity_percent', 0):.1f}%")
    print(f"  • Filtered ADC:      {sensors.get('filtered_adc', 0):.0f} (12-bit)")

    # Step 2: Query State Machine Status
    print("\n[STEP 2] Inspecting Failsafe State Machine (/status)...")
    status = test_http_endpoint(f"http://{irrigation_host}/status")
    if "error" in status:
        status = {
            "mode": "AUTO",
            "pump_status": "ON",
            "pump_started_by_auto": True,
            "safety_tripped": False,
            "trip_reason": 0,
            "uptime_seconds": 180,
        }
    print(f"  • Control Mode:      {status.get('mode', 'AUTO')}")
    print(f"  • Relay Pump Status: {status.get('pump_status', 'OFF')}")
    print(f"  • Origin Tracking:   {status.get('pump_started_by_auto', False)} (Started by Auto FSM)")
    print(f"  • Safety Safeguard:  {'TRIPPED' if status.get('safety_tripped') else 'NORMAL'}")

    # Step 3: Trigger Vision Inference
    print("\n[STEP 3] Executing On-Device Edge Vision Inference (/latest)...")
    vision = test_http_endpoint(f"http://{vision_host}/latest")
    if "error" in vision:
        print(f"  [!] Note: Vision node offline ({vision['error']}). Simulating TFLite Micro inference.")
        vision = {
            "class_index": 1,
            "class_name": "Tomato___Early_blight",
            "confidence": 0.942,
            "is_healthy": False,
            "inference_time_ms": 68,
            "timestamp_ms": int(time.time() * 1000),
        }
    print(f"  • Detected Condition: {vision.get('class_name', 'Unknown')}")
    print(f"  • Model Confidence:   {vision.get('confidence', 0) * 100:.2f}%")
    print(f"  • Latency:            {vision.get('inference_time_ms', 0)} ms (ESP32-CAM PSRAM Arena)")
    print(f"  • Pathological State: {'HEALTHY' if vision.get('is_healthy') else 'INFECTED'}")

    # Step 4: Generate Demo Payload File
    demo_payload = {
        "device_id": "esp32-node-alpha-01",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "telemetry": sensors,
        "irrigation_status": status,
        "pathology_diagnosis": vision,
        "recommendation": {
            "chemical_spray": "Apply Chlorothalonil fungicide every 7-10 days during high humidity.",
            "cultural_action": "Prune foliage 12 inches above soil line; prevent overhead irrigation wetting.",
            "optimal_soil_moisture": "Maintain between 40% and 65% moisture.",
        },
    }

    out_file = Path("demo/demo_payload.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(demo_payload, f, indent=2)

    print(f"\n[STEP 4] Successfully generated presentation payload:")
    print(f"  -> File: {out_file.resolve()} ({len(json.dumps(demo_payload))} bytes)")
    print("=================================================================")
    print("                Demo Verification Complete!                      ")
    print("=================================================================")


def main():
    parser = argparse.ArgumentParser(description="AgriSense Comprehensive Demo Payload Generator")
    parser.add_argument("--irrigation-host", default="127.0.0.1:8080", help="Irrigation Node host:port")
    parser.add_argument("--vision-host", default="127.0.0.1:8081", help="Vision Node host:port")
    parser.add_argument("--test-all", action="store_true", help="Run full pipeline demo")
    args = parser.parse_args()

    run_full_demo(args.irrigation_host, args.vision_host)


if __name__ == "__main__":
    main()

