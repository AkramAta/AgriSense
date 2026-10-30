# Firmware Subsystem

Contains microcontroller C++ code, headers, and simulation definitions:
- `irrigation_node/`: Primary field hardware node: ESP32 soil moisture & climate sensing, pump relay driver, safety state machine, and HTTP REST server.
- `vision_node/`: Standalone TFLite Micro edge inference reference implementation.
- `test/`: Host-side native C++ unit test suite for decoupled state-machine and signal math.
- `diagram.json` & `wokwi.toml`: Headless simulation definitions for Wokwi CI.

