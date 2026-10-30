# Firmware Subsystem

Contains microcontroller C++ code, headers, and simulation definitions:
- `irrigation_node/`: ESP32 environmental sensing, relay driver, and HTTP REST server.
- `vision_node/`: ESP32-CAM leaf image capture and TFLite Micro edge inference.
- `test/`: Host-side unit test suite for decoupled state-machine and signal math.
- `diagram.json` & `wokwi.toml`: Headless simulation definitions for Wokwi CI.

