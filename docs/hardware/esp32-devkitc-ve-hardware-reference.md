# ESP32-DevKitC-VE Development Board
## Hardware Reference Document

---

## CORE PROCESSOR

### CPU
- **Architecture:** Dual-core Xtensa LX6 32-bit
- **Clock Frequency:** 80 MHz to 240 MHz (configurable)
- **Cores:** Can run simultaneously or power down one for efficiency

### Ultra-Low-Power (ULP) Coprocessor
- **ULP-FSM:** Finite State Machine coprocessor
- Runs while main CPU is in deep sleep
- Access to RTC memory, RTC GPIO, and RTC peripherals during sleep
- Can monitor peripherals and wake main CPU on threshold crossings

---

## MEMORY

### Flash Storage: 8MB (64 Mbit)
- SPI interface, up to 80 MHz clock
- Stores program code and persistent data
- Non-volatile - retains data across power cycles
- Wear leveling recommended for write-heavy applications (~100K write cycles per sector)

### PSRAM: 8MB SPI
- External RAM via SPI interface
- Volatile - data lost on power down
- Slower than internal SRAM but vastly larger
- Connected via GPIO16 and GPIO17 (these pins unavailable for other use)

### Internal SRAM: 520KB
- 448KB ROM for boot and core functions
- Fastest memory available

### RTC Memory
- **RTC FAST:** 8KB - accessible during deep sleep, fast access, used by main CPU during RTC boot
- **RTC SLOW:** 8KB - accessible during deep sleep, ULP coprocessor storage
- Retains data during all sleep modes
- Use `RTC_DATA_ATTR` to store variables that persist through deep sleep

---

## GPIO SPECIFICATIONS

### Pin Count
- **Physical GPIO:** 34 pins (GPIO0-GPIO39, with gaps)
- **Actually Usable:** ~25 pins (after reserved pins excluded)

### Reserved Pins - DO NOT USE
| GPIO Range | Reason |
|------------|--------|
| GPIO6-GPIO11 | Internal SPI flash (directly connected) |
| GPIO16-GPIO17 | PSRAM on WROVER-E modules |

### Input-Only Pins
These pins can ONLY be used as inputs (no internal pull-up/down):

| GPIO | Notes |
|------|-------|
| GPIO34 | Input only, ADC1_CH6 |
| GPIO35 | Input only, ADC1_CH7 |
| GPIO36 (VP) | Input only, ADC1_CH0, Hall sensor |
| GPIO39 (VN) | Input only, ADC1_CH3, Hall sensor |

### Strapping Pins
Control boot behavior - usable after boot but affect startup:

| Pin | Function | Default State |
|-----|----------|---------------|
| GPIO0 | Boot mode selection | Internal pull-up |
| GPIO2 | Must be LOW or floating for download boot | Internal pull-down |
| GPIO5 | SDIO timing | Internal pull-up |
| GPIO12 (MTDI) | VDD_SDIO voltage selection | Internal pull-down |
| GPIO15 (MTDO) | JTAG/ROM message printing | Internal pull-up |

**Critical:** GPIO12 must be LOW at boot on WROVER-E modules (3.3V flash). External pull-down may be needed if peripheral pulls it high.

### Electrical Characteristics (per pin)
| Parameter | Value |
|-----------|-------|
| Maximum current (absolute) | 40 mA |
| Recommended current | 12 mA |
| Input voltage range | 0 - 3.3V |
| Output voltage | 0 - 3.3V |
| Internal pull-up/down | ~45kΩ typical |
| **NOT 5V TOLERANT** | Do not exceed 3.6V |

---

## PERIPHERAL INTERFACES

### SPI
- **Controllers:** 4 total (SPI0, SPI1, SPI2/HSPI, SPI3/VSPI)
- **Available for use:** SPI2 and SPI3 (SPI0/1 reserved for flash/PSRAM)
- **Modes:** Master or Slave
- **Clock:** Up to 80 MHz
- **Line modes:** Standard, Dual, Quad
- **Pin assignment:** Any available GPIO via GPIO Matrix

### I2C
- **Controllers:** 2 hardware I2C interfaces
- **Modes:** Master or Slave
- **Clock:** Up to 5 MHz (Fast Mode Plus on some revisions)
- **Standard:** 100 kHz, 400 kHz typical
- **Pin assignment:** Any GPIO can be SDA/SCL
- **Features:** Hardware FIFO buffers

### UART
- **Controllers:** 3 (UART0, UART1, UART2)
- **UART0:** Default USB/Serial for programming and debug (GPIO1 TX, GPIO3 RX)
- **UART1:** Default pins conflict with flash - reassign before use
- **UART2:** Fully available for external devices
- **Baud rate:** Up to 5 Mbps
- **Protocols:** RS232, RS485, IrDA
- **Features:** Hardware flow control (RTS/CTS), DMA support

### I2S
- **Controllers:** 2 independent
- **Modes:** Master or Slave
- **Formats:** Standard I2S, PCM, TDM
- **Features:** DMA support for audio streaming
- **Use cases:** Audio input/output, PDM microphones

### ADC (Analog-to-Digital Converter)
- **Channels:** 18 total (ADC1: 8 channels, ADC2: 10 channels)
- **Resolution:** 12-bit (0-4095)
- **Voltage range:** 0-1.1V default, up to 3.3V with attenuation
- **ADC1 Pins:** GPIO32-GPIO39 (always available)
- **ADC2 Pins:** GPIO0, 2, 4, 12-15, 25-27 (NOT available when WiFi active)

**Attenuation Settings:**
| Setting | Measurable Range |
|---------|------------------|
| 0 dB | 0 - 1.1V |
| 2.5 dB | 0 - 1.5V |
| 6 dB | 0 - 2.2V |
| 11 dB | 0 - 3.3V |

**Important:** ADC readings can be noisy. Use calibration and averaging for accurate measurements.

### DAC (Digital-to-Analog Converter)
- **Channels:** 2 independent 8-bit DACs
- **DAC1:** GPIO25
- **DAC2:** GPIO26
- **Resolution:** 8-bit (0-255 values)
- **Output range:** 0V to VDD (~3.3V)
- **Features:** 
  - Direct voltage output
  - DMA for continuous waveforms
  - Built-in cosine wave generator

**Note:** This is a key difference from ESP32-S3 which has NO DAC.

### PWM (LED PWM Controller - LEDC)
- **Channels:** 16 independent (8 high-speed, 8 low-speed)
- **Resolution:** Up to 16-bit
- **Frequency:** Few Hz to 40 MHz
- **Features:** Hardware fade, pulse generation
- **Pin support:** All output-capable GPIOs

### Touch Sensor
- **Channels:** 10 capacitive touch GPIOs
- **Pins:** GPIO0, 2, 4, 12, 13, 14, 15, 27, 32, 33
- **Features:**
  - Proximity and touch detection
  - Configurable sensitivity
  - Can wake from deep sleep

### Hall Effect Sensor
- **Built-in** magnetic field sensor
- Uses ADC1 channels 0 and 3 (GPIO36 and GPIO39)
- **Do not connect anything else to GPIO36/39 when using Hall sensor**
- Low sensitivity - best for presence detection, not precision

### Timers
- **General purpose:** 4x 64-bit timers with 16-bit prescaler
- **RTC timer:** For deep sleep wake
- **Watchdog:** Main system + RTC watchdog
- **Behavior:** Timers pause in light sleep by default

### Additional Peripherals
| Peripheral | Description |
|------------|-------------|
| SD/MMC Host | 1-bit, 4-bit, 8-bit SD/MMC interface |
| SDIO Slave | Act as SDIO slave device |
| Ethernet MAC | Requires external PHY (MII/RMII) |
| Remote Control (RMT) | Infrared TX/RX, LED strips (WS2812) |
| Pulse Counter (PCNT) | Hardware pulse counting/decoding |
| MCPWM | 2 modules for motor control |
| TWAI® | CAN 2.0 compatible (ISO 11898-1) |

---

## WIRELESS

### WiFi
| Parameter | Specification |
|-----------|---------------|
| Standard | 802.11 b/g/n |
| Frequency | 2.4 GHz only |
| Modes | Station, SoftAP, Station+SoftAP |
| Data rate | Up to 150 Mbps (802.11n HT40) |
| TX power | Up to +20 dBm (configurable) |
| RX sensitivity | -98 dBm (11b), -76 dBm (11n MCS7) |
| Security | WPA/WPA2/WPA3, WEP, WPS |
| Channels | 1-14 (region dependent) |

### Bluetooth
| Parameter | Specification |
|-----------|---------------|
| Version | Bluetooth 4.2 (BR/EDR + BLE) |
| **Classic Bluetooth** | **YES - Supported** |
| **BLE** | **YES - Supported** |
| TX power | Up to +12 dBm |
| Features | A2DP, AVRCP, SPP, HFP, GATT |

**Key difference from ESP32-S3:** This board supports BOTH Classic Bluetooth AND BLE. ESP32-S3 only supports BLE.

### Antenna
- **PCB antenna:** Integrated on ESP32-WROVER-E module
- Keep antenna area clear of metal/ground planes
- Minimum 15mm clearance recommended around antenna

---

## POWER

### Supply Voltage
| Rail | Range | Nominal |
|------|-------|---------|
| VDD (main) | 2.3V - 3.6V | 3.3V |
| USB input | 5V | Via Micro-USB |
| VIN pin | 5V - 12V | Through on-board regulator |

### Current Consumption

#### Active Mode
| State | Current |
|-------|---------|
| WiFi TX @ 20 dBm | ~240 mA peak |
| WiFi TX @ 13 dBm | ~140 mA |
| WiFi RX | ~95-100 mA |
| BT/BLE TX | ~130 mA |
| BT/BLE RX | ~95-100 mA |
| CPU only @ 240 MHz | 30-50 mA |
| CPU only @ 80 MHz | 20-25 mA |

#### Sleep Modes
| Mode | Current | Wake Time |
|------|---------|-----------|
| Modem Sleep (CPU 240MHz) | 30-50 mA | Instant |
| Modem Sleep (CPU 80MHz) | 20-25 mA | Instant |
| Light Sleep | 0.8-1 mA | 2-3 ms |
| Deep Sleep (RTC + ULP on) | ~150 µA | ~150 ms |
| Deep Sleep (RTC timer only) | ~10 µA | ~150 ms |
| Deep Sleep (minimum) | ~5 µA | ~150 ms |
| Hibernation (RTC off) | ~2.5 µA | Full reboot |

### Power Modes
- **Active:** Full operation, all peripherals available
- **Modem Sleep:** CPU active, WiFi/BT radio off between beacons (automatic in STA mode)
- **Light Sleep:** CPU suspended, WiFi connection maintained, quick wake
- **Deep Sleep:** Only RTC domain active, ULP can run, all RAM lost except RTC memory
- **Hibernation:** Minimum power, only RTC timer or external pins for wake

### Deep Sleep Wake Sources
- Timer (RTC)
- External wake (EXT0: single GPIO, EXT1: multiple GPIO)
- Touch pad
- ULP coprocessor

---

## OPERATING CONDITIONS

### Temperature
| Condition | Range |
|-----------|-------|
| Operating | -40°C to +85°C |
| Junction temperature | < 125°C |
| Storage | -40°C to +125°C |

**Note:** High ambient temperatures combined with WiFi TX can cause thermal throttling. Consider heat dissipation for continuous high-power applications.

### Humidity
| Condition | Range |
|-----------|-------|
| Operating | 10% - 90% RH (non-condensing) |
| Storage | 5% - 95% RH (non-condensing) |

### ESD Protection
| Model | Rating |
|-------|--------|
| HBM (Human Body Model) | 2000V |
| CDM (Charged Device Model) | 500V |

---

## TIMING

### Clock Sources
| Source | Frequency | Notes |
|--------|-----------|-------|
| External crystal | 40 MHz | Primary, accurate |
| Internal RC | 8 MHz | Less accurate, calibratable |
| RTC clock (internal) | 150 kHz | Low-power domain |
| External 32.768 kHz | Optional | Precision RTC |

### Boot/Wake Timing
| Event | Duration |
|-------|----------|
| Cold boot | 150-300 ms |
| Deep sleep wake | ~150 ms |
| Light sleep wake | 2-3 ms |

---

## DEVKITC-VE BOARD FEATURES

### Board Components
- **Module:** ESP32-WROVER-E (PCB antenna version)
- **USB-UART Bridge:** CP2102 or similar
- **USB Connector:** Micro-USB Type B
- **Buttons:** EN (Reset), BOOT (GPIO0)
- **LED:** Power LED, optional user LED
- **Regulator:** AMS1117-3.3 or equivalent
- **Headers:** 2x19 pins, 2.54mm (0.1") pitch

### Pin Header Layout
Standard DevKitC-VE has 38 pins broken out (19 per side).

### Programming
- Automatic boot mode via USB-UART DTR/RTS
- Hold BOOT button + press EN for manual download mode
- UART0 (GPIO1/GPIO3) for serial communication

---

## HARD LIMITATIONS

### What This Board CANNOT Do
- Operate above 3.6V input (NOT 5V tolerant)
- Use GPIO6-11 for external devices (flash)
- Use GPIO16-17 for external devices (PSRAM)
- Run 5 GHz WiFi (2.4 GHz only)
- Use ADC2 while WiFi is active
- Exceed 40 mA per GPIO (12 mA recommended)
- Operate reliably above 85°C ambient
- Provide precise analog readings without calibration

### Critical Restrictions
- 8 GPIOs unavailable due to flash/PSRAM
- 4 GPIOs are input-only (34, 35, 36, 39)
- Strapping pins affect boot behavior
- ADC readings are nonlinear without calibration
- GPIO36/39 have glitches when certain peripherals power up
- Flash has write endurance limits (~100K cycles per sector)
- WiFi and ADC2 cannot be used simultaneously

---

## KEY DIFFERENCES: ESP32 vs ESP32-S3

| Feature | ESP32 (This Board) | ESP32-S3 |
|---------|-------------------|----------|
| CPU | Dual LX6 @ 240 MHz | Dual LX7 @ 240 MHz |
| DAC | **YES** (2 channels, 8-bit) | **NO** |
| Hall Sensor | **YES** | **NO** |
| Classic Bluetooth | **YES** (BR/EDR + BLE) | **NO** (BLE only) |
| USB Native | **NO** | **YES** (USB OTG) |
| GPIOs | 34 | 45 |
| Touch Channels | 10 | 14 |
| ADC Channels | 18 | 20 |
| ULP Type | FSM only | FSM + RISC-V |
| Vector Instructions | No | Yes |

---

## SOFTWARE COMPATIBILITY

### Frameworks
- ESP-IDF (Espressif native, recommended)
- Arduino IDE (ESP32 board package)
- MicroPython
- PlatformIO
- CircuitPython
- Lua RTOS

### Programming/Debug
- USB-UART serial (Micro-USB)
- JTAG (GPIO12-15, optional)
- OpenOCD compatible
- GDB debugging

### Arduino IDE Settings (DevKitC-VE with WROVER-E)
```
Board: ESP32 Wrover Module
Flash Mode: QIO
Flash Size: 8MB (64Mb)
Partition Scheme: Default (or 8M with spiffs)
PSRAM: Enabled
Upload Speed: 921600
```

---

## REFERENCES

- [ESP32 Series Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- [ESP32 Technical Reference Manual](https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf)
- [ESP32-WROVER-E Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-wrover-e_esp32-wrover-ie_datasheet_en.pdf)
- [ESP32-DevKitC Getting Started](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/index.html)
- [ESP-IDF Programming Guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/)

---

*Document Version: 1.0*  
*Last Updated: November 2025*  
*Board: ESP32-DevKitC-VE with ESP32-WROVER-E Module*
