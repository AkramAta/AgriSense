# AgriSense Hardware Wiring Schematics & Electrical Interfacing

## 1. ESP32 Irrigation Node Pinout

The ESP32 DevKit-C v4 orchestrates soil moisture sensing, climate monitoring, and 5V relay switching.

| Pin Label | GPIO Channel | Function / Peripheral | Direction | Interfacing Device | Operating Voltage |
|:----------|:-------------|:----------------------|:----------|:-------------------|:------------------|
| **GPIO 4** | GPIO 4 | Single-Bus Bidirectional | In/Out | DHT11 Data Pin (with 4.7kΩ pullup) | 3.3V |
| **GPIO 34**| ADC1_CH6 | Analog Input Only | Input | Capacitive Soil Moisture Sensor (SIG) | 0 - 3.3V |
| **GPIO 26**| GPIO 26 | Digital Output | Output | Solid-State / Optocoupled Relay (IN) | 3.3V Logic |
| **GPIO 2** | GPIO 2 | Digital Output | Output | On-Board Diagnostic Status LED | 3.3V |
| **3V3** | Power | 3.3V LDO Rail | Output | Sensor VCC rails | 3.3V DC (max 500mA) |
| **5V / VIN**| Power | 5V External Input | Input | 5V Power Supply / USB | 5.0V DC (min 2A) |
| **GND** | Ground | Common Digital Ground | Power | System common ground plane | 0V |

> [!IMPORTANT]
> Always connect the analog soil moisture sensor to **ADC1** pins (GPIO 32 - 39). ADC2 cannot be sampled when Wi-Fi is actively transmitting. GPIO 34 is an input-only pin, making it immune to accidental output driver conflicts.

---

## 2. ESP32-CAM AI-Thinker Vision Node Pinout

The ESP32-CAM interfaces with an OmniVision OV2640 2-Megapixel image sensor over DVP (Digital Video Port).

| Pin Function | GPIO Channel | Description | Voltage Level |
|:-------------|:-------------|:------------|:--------------|
| **PWDN** | GPIO 32 | Camera Power-Down Control | 3.3V |
| **RESET** | -1 (Internal) | Hardware Reset Line | 3.3V |
| **XCLK** | GPIO 0 | Master Camera Clock (20 MHz) | 3.3V |
| **SIOD** | GPIO 26 | SCCB / I2C Data Line | 3.3V (Pullup) |
| **SIOC** | GPIO 27 | SCCB / I2C Clock Line | 3.3V (Pullup) |
| **Y9** | GPIO 35 | Video Data Bit 7 (MSB) | 3.3V |
| **Y8** | GPIO 34 | Video Data Bit 6 | 3.3V |
| **Y7** | GPIO 39 | Video Data Bit 5 | 3.3V |
| **Y6** | GPIO 36 | Video Data Bit 4 | 3.3V |
| **Y5** | GPIO 21 | Video Data Bit 3 | 3.3V |
| **Y4** | GPIO 19 | Video Data Bit 2 | 3.3V |
| **Y3** | GPIO 18 | Video Data Bit 1 | 3.3V |
| **Y2** | GPIO 5 | Video Data Bit 0 (LSB) | 3.3V |
| **VSYNC** | GPIO 25 | Vertical Frame Synchronization | 3.3V |
| **HREF** | GPIO 23 | Horizontal Reference Synchronization | 3.3V |
| **PCLK** | GPIO 22 | Pixel Clock | 3.3V |
| **FLASH LED**| GPIO 4 | High-Brightness White Flash LED | 3.3V (Active High) |

---

## 3. Power Distribution & Noise Isolation

```
           +-----------------------------------------------+
           | 5V DC 2.5A Regulated Power Supply Unit (PSU)  |
           +-----------------------+-----------------------+
                                   |
         +-------------------------+-------------------------+
         |                                                   |
         v                                                   v
+------------------+                               +--------------------+
| ESP32 VIN (Pin)  |                               | Relay Module VCC   |
| (Onboard 3.3V    |                               | (Optocoupled Coil) |
|  LDO Regulator)  |                               +---------+----------+
+--------+---------+                                         |
         |                                                   |
         v                                                   v
+------------------+                               +--------------------+
| 3.3V Sensor Rail |                               | 12V Solenoid Pump  |
| - DHT11 (Pin 4)  |                               | External DC Source |
| - Soil (Pin 34)  |                               | (1N4007 Diode across|
+------------------+                               |  inductive coil)   |
                                                   +--------------------+
```

### Inductive Load & Flyback Protection
When driving an inductive solenoid valve or 12V DC water pump:
1. Always use an **optically isolated relay module**.
2. Connect a **1N4007 flyback diode** directly across the solenoid / pump terminals in reverse bias (cathode to +12V, anode to GND) to absorb back-EMF spikes that could reset the ESP32.
3. Keep the 12V pump power circuit physically separated from the 3.3V analog sensor traces.

---

## 4. Capacitive Soil Moisture Sensor Calibration

The capacitive sensor outputs an analog voltage inversely proportional to soil volumetric water content:

$$\text{Moisture} (\%) = \left( \frac{\text{ADC}_{\text{dry}} - \text{ADC}_{\text{sampled}}}{\text{ADC}_{\text{dry}} - \text{ADC}_{\text{wet}}} \right) \times 100\%$$

- **Completely Dry Air ($\text{ADC}_{\text{dry}}$):** ~3,200 (at 12-bit resolution: 0 - 4,095)
- **Saturated Water ($\text{ADC}_{\text{wet}}$):** ~1,400
- **Optimal Tomato Root Zone:** 2,000 - 2,450 ADC (40% - 65% moisture)

