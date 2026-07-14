# LONELY BINARY ESP32-S3 N16R8 GOLD EDITION
## Hardware Reference Document

---

## CORE PROCESSOR

### CPU
- **Architecture:** Dual-core Xtensa LX7 32-bit RISC
- **Clock Frequency:** Up to 240 MHz (configurable per core)
- **Cores:** Can run simultaneously or power down one for efficiency

### Ultra-Low-Power (ULP) Coprocessors
- **ULP-RISC-V:** Full RISC-V instruction set coprocessor
- **ULP-FSM:** Finite State Machine coprocessor
- Both can run while main CPU is in deep sleep
- Access to RTC memory, RTC GPIO, and RTC peripherals during sleep

---

## MEMORY

### Flash Storage: 16MB (128 Mbit)
- SPI interface, up to 80 MHz clock (120 MHz available with specific flash)
- Stores program code and persistent data
- Non-volatile - retains data across power cycles
- Wear leveling recommended for write-heavy applications

### PSRAM: 8MB Octal SPI
- High-speed external RAM via 8-line SPI interface
- **With ECC disabled:** Full 8MB, max ambient temp 65°C
- **With ECC enabled:** 7MB usable, max ambient temp 85°C
- Volatile - data lost on power down
- Slower than internal SRAM but vastly larger

### Internal SRAM: 512KB
- 328KB available for application data
- 16KB instruction cache
- 16KB data cache
- Fastest memory available

### RTC Memory
- **RTC FAST:** 8KB - accessible during deep sleep, fast access
- **RTC SLOW:** 16KB - accessible during deep sleep, ULP coprocessor storage
- Retains data during all sleep modes

---

## GPIO SPECIFICATIONS

### Pin Count
- **Physical GPIO:** 45 pins (GPIO0-GPIO21, GPIO26-GPIO48)
- **Actually Usable:** ~36 pins (after reserved pins excluded)

### Reserved Pins - DO NOT USE
| GPIO Range | Reason |
|------------|--------|
| GPIO26-GPIO32 | Internal SPI flash |
| GPIO33-GPIO37 | Octal PSRAM (8MB models) |
| GPIO19-GPIO20 | USB-JTAG (reconfigurable but disables USB debug) |

### Strapping Pins
Control boot behavior - usable after boot but affect startup:

| Pin | Function | Default State |
|-----|----------|---------------|
| GPIO0 | Boot mode selection | Weak pull-up |
| GPIO3 | JTAG mode configuration | Weak pull-down |
| GPIO45 | SPI flash voltage | Weak pull-down |
| GPIO46 | ROM message printing | Weak pull-down |

### Power-Up Glitches
Design circuits to tolerate these transients:

| GPIO | Glitch Type | Duration |
|------|-------------|----------|
| GPIO1-17 | Low-level | 60µs |
| GPIO18 | Low + High | 60µs each |
| GPIO21 | Two high-level | 60µs each |

### Electrical Characteristics (per pin)
| Parameter | Value |
|-----------|-------|
| Maximum current (absolute) | 40 mA |
| Recommended current | 28 mA |
| Input voltage range | 0 - 3.6V |
| Output voltage | 0 - 3.3V |
| Internal pull-up/down | 45kΩ typical |

---

## PERIPHERAL INTERFACES

### SPI
- **Controllers:** 4 total (SPI0, SPI1, SPI2/HSPI, SPI3/VSPI)
- **Available for use:** SPI2 and SPI3 (SPI0/1 reserved for flash/PSRAM)
- **Modes:** Master or Slave
- **Clock:** Up to 80 MHz
- **Line modes:** 1-line, 2-line, 4-line
- **Pin assignment:** Any available GPIO via GPIO Matrix

### I2C
- **Controllers:** 1 hardware I2C (can emulate more in software)
- **Modes:** Master or Slave
- **Clock:** Up to 5 MHz (Fast Mode Plus)
- **Pin assignment:** Any GPIO can be SDA/SCL
- **Addressing:** Supports up to 112 devices per bus
- **Features:** Hardware FIFO buffers

### UART
- **Controllers:** 3 (UART0, UART1, UART2)
- **UART0:** Default USB/Serial (GPIO43 TX, GPIO44 RX)
- **UART1:** Reserved for internal flash
- **UART2:** Available for external devices
- **Baud rate:** Up to 5 Mbps
- **Protocols:** RS232, RS485, IrDA
- **Features:** Hardware flow control (RTS/CTS), DMA support
- **Pin assignment:** Any GPIO via GPIO Matrix

### USB
- **Standard:** Full-speed USB 2.0 OTG
- **Data rate:** 12 Mbps
- **Modes:** Device or Host
- **Classes:** CDC (serial), HID, MSC, custom
- **Debug:** Separate USB-JTAG interface available

### I2S
- **Controllers:** 2 independent
- **Modes:** Master or Slave
- **Sample rate:** Up to 40 MHz
- **Formats:** TDM, PDM, standard I2S
- **Features:** DMA support for streaming

### ADC (Analog-to-Digital Converter)
- **Channels:** 20
- **Resolution:** 12-bit (0-4095)
- **Sampling rate:** Up to 2 MSPS (2 million samples/second)
- **Voltage range:** 0-3.3V (configurable attenuation)
- **Features:** 
  - DMA support for continuous sampling
  - Calibration available for improved accuracy
  - Internal temperature sensor (-40°C to 125°C)

### PWM (LED PWM Controller)
- **Channels:** 8 independent
- **Resolution:** Up to 16-bit
- **Frequency:** Few Hz to 40 MHz
- **Features:** Hardware fade, pulse generation
- **Pin support:** All non-input-only GPIOs

### NO DAC
- **ESP32-S3 does NOT have a DAC**
- For analog output, use:
  - PWM with low-pass filter
  - I2S PDM (Pulse Density Modulation)
  - External DAC IC

### Touch Sensor
- **Channels:** 14 capacitive touch GPIOs
- **Features:**
  - Proximity and touch detection
  - Configurable sensitivity
  - Can wake from deep sleep

### Timers
- **General purpose:** 4x 54-bit timers with 16-bit prescaler
- **System timer:** 52-bit (2 counters, 3 comparators)
- **Watchdog:** Main system + RTC watchdog
- **Behavior:** Continue running in light sleep

### Additional Peripherals
| Peripheral | Description |
|------------|-------------|
| SD/MMC Host | 4-bit SD 3.01/3.1, 8-bit MMC 4.41 |
| Camera Interface | 8/16-bit DVP |
| LCD Interface | 8/16-bit parallel |
| Remote Control | Infrared TX/RX |
| Pulse Counter | Hardware pulse counting |
| MCPWM | 2 modules, 6 PWM outputs each (motor control) |
| TWAI® | CAN 2.0 compatible (ISO 11898-1) |
| GDMA | 5 DMA channels |

---

## WIRELESS

### WiFi
| Parameter | Specification |
|-----------|---------------|
| Standard | 802.11 b/g/n |
| Frequency | 2.4 GHz only |
| Modes | Station, SoftAP, Station+SoftAP |
| Data rate | Up to 150 Mbps (PHY) |
| TX power | Up to +20 dBm (configurable) |
| RX sensitivity | -97 dBm (11b), -74 dBm (11n MCS7) |
| Security | WPA/WPA2/WPA3, WEP, WPS |
| Channels | 1-14 (region dependent) |

### Bluetooth
| Parameter | Specification |
|-----------|---------------|
| Version | Bluetooth 5.0 LE only |
| Data rates | 125 Kbps, 500 Kbps, 1 Mbps, 2 Mbps |
| TX power | Up to +21 dBm |
| RX sensitivity | -98 dBm (125 Kbps) |
| Features | Bluetooth Mesh support |
| **Note** | Classic Bluetooth NOT supported |

### Antenna
- **PCB antenna:** Integrated on some board variants
- **IPEX connector:** U.FL connector for external antenna (50Ω)
- External antenna recommended for range-critical applications

---

## POWER

### Supply Voltage
| Rail | Range | Nominal |
|------|-------|---------|
| VDD (main) | 3.0V - 3.6V | 3.3V |
| VDD_SPI | 1.8V or 3.3V | 3.3V (default) |
| USB input | 5V | Via Type-C |

### Current Consumption

#### Active Mode
| State | Current |
|-------|---------|
| WiFi TX @ 20 dBm | ~360 mA |
| WiFi TX @ 15 dBm | ~280 mA |
| WiFi RX | ~90-100 mA |
| BLE TX | ~90-100 mA |
| BLE RX | ~85-95 mA |
| CPU only (no RF) | ~30-50 mA |

#### Sleep Modes
| Mode | Current | Wake Time |
|------|---------|-----------|
| Modem Sleep | 20-30 mA | Instant |
| Light Sleep | 750µA - 2mA | 2-5 ms |
| Deep Sleep | 7-10 µA | 100-150 ms |
| Deep Sleep + ULP | 150-200 µA | 100-150 ms |
| Hibernation | ~5 µA | 100+ ms |
| Chip disabled | ~1 µA | Full boot |

### Power Modes
- **Active:** Full operation, all peripherals
- **Modem Sleep:** CPU active, WiFi/BT off (automatic during idle)
- **Light Sleep:** CPU suspended, quick wake, connections maintained
- **Deep Sleep:** Only RTC domain active, ULP can run
- **Hibernation:** Minimum power, RTC timer or external wake only

---

## OPERATING CONDITIONS

### Temperature
| Condition | Range |
|-----------|-------|
| Operating (standard) | -40°C to +65°C |
| Operating (PSRAM ECC enabled) | -40°C to +85°C |
| Internal temp sensor range | -40°C to +125°C |
| Storage | -40°C to +150°C |

**Note:** Internal chip temperature exceeds ambient due to power dissipation. At high load or ambient temps, thermal management required.

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
| Internal RC | 17.5 MHz | Less accurate |
| RTC clock | 150 kHz | Low-power domain |
| External 32.768 kHz | Optional | Precision RTC |

### Boot/Wake Timing
| Event | Duration |
|-------|----------|
| Cold boot | 200-300 ms |
| Deep sleep wake | 100-150 ms |
| Light sleep wake | 2-5 ms |

### Interrupt Latency
| Routing | Latency |
|---------|---------|
| GPIO Matrix | 1-2 µs |
| IO_MUX (direct) | 300-500 ns |

---

## PHYSICAL

### Lonely Binary Board Features
- **PCB:** Black solder mask, lead-free immersion gold (ENIG)
- **Compliance:** RoHS, non-toxic, safe for handling
- **Headers:** 2x40 pins, 2.54mm (0.1") pitch
- **USB:** Dual USB Type-C (separate power and data)
- **Antenna:** PCB or IPEX (model dependent)

---

## HARD LIMITATIONS

### What This Board CANNOT Do
- Generate true analog output (no DAC)
- Operate above 3.6V input
- Use GPIO26-37 for external devices
- Run 5 GHz WiFi
- Classic Bluetooth (BLE only)
- Exceed 40 mA per GPIO
- Operate reliably above 85°C ambient (even with ECC)

### Critical Restrictions
- 9 GPIOs unavailable due to flash/PSRAM
- Strapping pins affect boot behavior
- Power-up glitches require circuit design consideration
- PSRAM slower than SRAM (plan memory allocation accordingly)
- Flash has write endurance limits (~100K cycles per sector)

---

## SOFTWARE COMPATIBILITY

### Frameworks
- Arduino IDE (ESP32-S3 board package)
- ESP-IDF (Espressif native)
- MicroPython
- PlatformIO
- CircuitPython
- Lua RTOS

### Programming/Debug
- USB CDC serial (Type-C)
- UART0 (TX/RX pins)
- USB-JTAG (GPIO19/20 or via USB)
- OpenOCD compatible
- GDB debugging

### Arduino IDE Settings (N16R8)
```
Board: ESP32S3 Dev Module
USB CDC On Boot: Enabled
PSRAM: OPI PSRAM
Flash Size: 16MB (128Mb)
Flash Mode: QIO 80MHz
Partition Scheme: 16M Flash (3MB APP/9.9MB FATFS)
Upload Mode: UART0 / Hardware CDC
USB Mode: Hardware CDC and JTAG
```

---

## REFERENCES

- [ESP32-S3 Series Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf)
- [ESP32-S3 Technical Reference Manual](https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf)
- [ESP32-S3-WROOM-1 Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf)
- [Lonely Binary Tutorials](https://lonelybinary.com/en-us/blogs/tinkerblock-esp32-s3-starter-kit)

---

*Document Version: 1.0*
*Last Updated: November 2025*
*Board: Lonely Binary ESP32-S3 N16R8 Gold Edition*
