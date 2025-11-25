# ADS1115 16-Bit ADC Hardware Reference
## For Use With ESP32-S3 N16R8

**Scope:** This document covers ADS1115 specifications relevant to ESP32-S3 integration via MicroPython I2C. If using a different microcontroller, verify voltage compatibility and I2C implementation details.

**Source:** Texas Instruments ADS111x Datasheet (SBAS444E, Rev. December 2024)

---

## DEVICE OVERVIEW

The ADS1115 is a 16-bit delta-sigma ADC with:
- Four single-ended or two differential input channels
- Programmable gain amplifier (PGA)
- Internal voltage reference and oscillator
- I2C interface with four selectable addresses
- Digital comparator with ALERT/RDY pin

---

## ELECTRICAL SPECIFICATIONS

### Power Supply

| Parameter | Min | Typical | Max | Unit |
|-----------|-----|---------|-----|------|
| Supply voltage (VDD) | 2.0 | 3.3 | 5.5 | V |
| Operating current | — | 150 | 300 | µA |
| Power-down current (25°C) | — | 0.5 | 5 | µA |

**ESP32-S3 Compatibility:** The ADS1115 operates directly from the ESP32's 3.3V rail. No level shifting required for I2C lines when both devices share VDD.

### Analog Input Voltage Limits

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| Absolute input voltage (any AINx pin) | GND – 0.3 | VDD + 0.3 | V |
| Continuous input current (any pin) | –10 | +10 | mA |

**CRITICAL:** The FSR settings (like ±6.144V) define ADC *scaling*, not allowable input voltage. With VDD = 3.3V, inputs must stay within approximately 0V to 3.3V regardless of FSR setting.

### Digital I/O Levels

| Parameter | Value | Unit |
|-----------|-------|------|
| High-level input (VIH) | 0.7 × VDD to 5.5 | V |
| Low-level input (VIL) | GND to 0.3 × VDD | V |
| Low-level output (VOL) at 3mA | 0.4 max | V |

**ESP32-S3 Compatibility:** At VDD = 3.3V:
- VIH = 2.31V minimum (ESP32 outputs ~3.3V high — compatible)
- VIL = 0.99V maximum (ESP32 outputs ~0V low — compatible)
- Open-drain outputs require external pullups

---

## I2C INTERFACE

### Address Selection

The ADDR pin determines the 7-bit I2C address:

| ADDR Pin Connection | 7-Bit Address | 8-Bit Write | 8-Bit Read |
|---------------------|---------------|-------------|------------|
| GND | 0x48 | 0x90 | 0x91 |
| VDD | 0x49 | 0x92 | 0x93 |
| SDA | 0x4A | 0x94 | 0x95 |
| SCL | 0x4B | 0x96 | 0x97 |

**Note:** Most breakout boards (Adafruit, etc.) default ADDR to GND = **0x48**.

**MicroPython uses 7-bit addresses.** Use 0x48, 0x49, 0x4A, or 0x4B.

### I2C Speed Modes

| Mode | Max Clock | Notes |
|------|-----------|-------|
| Standard | 100 kHz | Always works |
| Fast | 400 kHz | Default for most MicroPython I2C |
| High-Speed | 3.4 MHz | Requires special activation sequence |

**ESP32-S3 Recommendation:** 400 kHz works reliably. The ESP32-S3 hardware I2C supports up to 5 MHz, but 400 kHz provides good margin for wire length and noise immunity.

### I2C Timing (Fast Mode)

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| SCL clock frequency | 0.01 | 400 | kHz |
| Bus free time (between STOP and START) | 600 | — | ns |
| Hold time after START | 600 | — | ns |
| Data setup time | 100 | — | ns |
| SCL low period | 1300 | — | ns |
| SCL high period | 600 | — | ns |

**Pullup Resistors:** Required on SDA and SCL. Typical values: 2.2kΩ to 10kΩ. Lower values for faster speeds or longer wires. Many breakout boards include onboard pullups.

### I2C Communication Pattern

**Write operation (e.g., configure device):**
1. START
2. Address byte (7-bit address + W bit = 0)
3. Pointer register byte (which register to write)
4. Data byte 1 (MSB)
5. Data byte 2 (LSB)
6. STOP

**Read operation (e.g., get conversion):**
1. START
2. Address byte (7-bit address + W bit = 0)
3. Pointer register byte (which register to read)
4. REPEATED START (or STOP then START)
5. Address byte (7-bit address + R bit = 1)
6. Read data byte 1 (MSB) — controller ACKs
7. Read data byte 2 (LSB) — controller NACKs
8. STOP

**Shortcut:** The pointer register is remembered. After setting it once, subsequent reads can skip steps 1-4.

---

## REGISTER MAP

| Pointer Value | Register | Access | Reset Value |
|---------------|----------|--------|-------------|
| 0x00 | Conversion | Read-only | 0x0000 |
| 0x01 | Config | Read/Write | 0x8583 |
| 0x02 | Lo_thresh | Read/Write | 0x8000 |
| 0x03 | Hi_thresh | Read/Write | 0x7FFF |

### Conversion Register (0x00)

16-bit signed result in two's complement format.

| Code | Meaning |
|------|---------|
| 0x7FFF | Positive full-scale (or clipped above) |
| 0x0001 | +1 LSB |
| 0x0000 | Zero (or very small positive/negative) |
| 0xFFFF | –1 LSB |
| 0x8000 | Negative full-scale (or clipped below) |

**Data Format:** Big-endian (MSB first over I2C).

**MicroPython Conversion:**
```python
# Read 2 bytes, convert to signed 16-bit
raw = i2c.readfrom_mem(0x48, 0x00, 2)
value = int.from_bytes(raw, 'big')
if value >= 0x8000:
    value -= 0x10000  # Convert to signed
```

### Config Register (0x01)

**Default value: 0x8583** = single-shot mode, AIN0-AIN1 differential, ±2.048V FSR, 128 SPS, comparator disabled.

#### Bit Layout

| Bits | Field | Default | Description |
|------|-------|---------|-------------|
| 15 | OS | 1 | Operational status / start conversion |
| 14:12 | MUX[2:0] | 000 | Input multiplexer |
| 11:9 | PGA[2:0] | 010 | Programmable gain |
| 8 | MODE | 1 | Operating mode |
| 7:5 | DR[2:0] | 100 | Data rate |
| 4 | COMP_MODE | 0 | Comparator mode |
| 3 | COMP_POL | 0 | Comparator polarity |
| 2 | COMP_LAT | 0 | Comparator latch |
| 1:0 | COMP_QUE[1:0] | 11 | Comparator queue |

#### OS Bit (Bit 15)

**When writing:**
- 0 = No effect
- 1 = Start single-shot conversion (only effective in single-shot mode)

**When reading:**
- 0 = Conversion in progress
- 1 = Not converting (ready for new conversion or in power-down)

#### MUX[2:0] (Bits 14:12) — Input Selection

| Value | AINP | AINN | Description |
|-------|------|------|-------------|
| 000 | AIN0 | AIN1 | Differential (default) |
| 001 | AIN0 | AIN3 | Differential |
| 010 | AIN1 | AIN3 | Differential |
| 011 | AIN2 | AIN3 | Differential |
| 100 | AIN0 | GND | Single-ended |
| 101 | AIN1 | GND | Single-ended |
| 110 | AIN2 | GND | Single-ended |
| 111 | AIN3 | GND | Single-ended |

**Single-ended notes:** Output range is 0x0000 to 0x7FFF only (positive half of full scale). Small offset errors may produce slightly negative readings near 0V input.

#### PGA[2:0] (Bits 11:9) — Full-Scale Range

| Value | FSR | LSB Size | Notes |
|-------|-----|----------|-------|
| 000 | ±6.144V | 187.5 µV | Input still limited to VDD |
| 001 | ±4.096V | 125 µV | Input still limited to VDD |
| 010 | ±2.048V | 62.5 µV | Default, works well at 3.3V |
| 011 | ±1.024V | 31.25 µV | |
| 100 | ±0.512V | 15.625 µV | |
| 101 | ±0.256V | 7.8125 µV | Best for small signals |
| 110 | ±0.256V | 7.8125 µV | Same as 101 |
| 111 | ±0.256V | 7.8125 µV | Same as 101 |

**Important:** FSR defines the ADC's scaling math, not input protection. With VDD = 3.3V and FSR = ±6.144V, you can measure 0-3.3V, but codes above ~17,600 (corresponding to 3.3V) are unused.

#### MODE (Bit 8)

| Value | Mode | Description |
|-------|------|-------------|
| 0 | Continuous | Conversions run automatically at DR rate |
| 1 | Single-shot | One conversion per OS=1 write, then power-down |

#### DR[2:0] (Bits 7:5) — Data Rate

| Value | Rate | Conversion Time | Notes |
|-------|------|-----------------|-------|
| 000 | 8 SPS | 125 ms | Best noise performance |
| 001 | 16 SPS | 62.5 ms | |
| 010 | 32 SPS | 31.25 ms | |
| 011 | 64 SPS | 15.625 ms | |
| 100 | 128 SPS | 7.8 ms | Default |
| 101 | 250 SPS | 4 ms | |
| 110 | 475 SPS | 2.1 ms | |
| 111 | 860 SPS | 1.16 ms | Fastest, most noise |

**Conversion time = 1 / data rate.** Single-cycle settling means no extra settling time needed after switching channels.

**Data rate tolerance: ±10%** — The internal oscillator drifts. An 860 SPS setting may actually run anywhere from 774 to 946 SPS.

#### Comparator Fields (Bits 4:0)

| Field | Default | Purpose |
|-------|---------|---------|
| COMP_MODE | 0 | 0=traditional, 1=window |
| COMP_POL | 0 | 0=active low, 1=active high |
| COMP_LAT | 0 | 0=non-latching, 1=latching |
| COMP_QUE | 11 | 11=comparator disabled |

**To use ALERT/RDY as conversion-ready signal:**
Set Hi_thresh MSB = 1 and Lo_thresh MSB = 0, and COMP_QUE ≠ 11.

---

## CONVERSION TIMING

### Single-Shot Mode Sequence

1. Write config with OS=1 to start conversion
2. Wait for conversion time (based on DR setting)
3. Poll OS bit or wait for ALERT/RDY (if configured)
4. Read conversion register

**Polling method:**
```python
# Start conversion
config = 0xC3E3  # Example: single-shot, AIN0 vs GND, ±4.096V, 860 SPS
i2c.writeto_mem(0x48, 0x01, config.to_bytes(2, 'big'))

# Poll until done
while True:
    cfg = int.from_bytes(i2c.readfrom_mem(0x48, 0x01, 2), 'big')
    if cfg & 0x8000:  # OS bit = 1 means done
        break
    time.sleep_ms(1)

# Read result
raw = i2c.readfrom_mem(0x48, 0x00, 2)
```

### Continuous Mode Timing

In continuous mode, conversions run automatically. Reading the conversion register at any time returns the most recent completed conversion.

**Timing consideration:** If you read faster than the conversion rate, you'll get the same value multiple times. If you read slower, you'll miss some conversions (which is fine for most applications).

---

## VOLTAGE TO CODE CONVERSION

### Formula

```
Code = (Vin / FSR) × 32768
```

For single-ended (positive-only) inputs:
```
Vin = Code × (FSR / 32768)
```

### Example Calculations

**FSR = ±4.096V, measuring 1.65V:**
```
Code = (1.65 / 4.096) × 32768 = 13,200
Voltage = 13200 × (4.096 / 32768) = 1.65V
```

**FSR = ±2.048V, measuring 1.024V:**
```
Code = (1.024 / 2.048) × 32768 = 16,384
```

---

## INPUT IMPEDANCE

The ADS1115 uses switched-capacitor inputs. Effective input impedance varies with gain setting:

| FSR Setting | Differential Impedance | Common-Mode Impedance |
|-------------|------------------------|----------------------|
| ±6.144V | 22 MΩ | 10 MΩ |
| ±4.096V | 15 MΩ | 10 MΩ |
| ±2.048V | 4.9 MΩ | 6 MΩ |
| ±1.024V | 2.4 MΩ | 3 MΩ |
| ±0.512V | 710 kΩ | 100 kΩ |
| ±0.256V | 710 kΩ | 100 kΩ |

**Implication:** High-impedance sources may need buffering, especially at lower FSR settings. Source impedance affects accuracy.

---

## NOISE PERFORMANCE

Effective resolution at different data rates (VDD = 3.3V, FSR = ±2.048V):

| Data Rate | RMS Noise | Noise-Free Bits |
|-----------|-----------|-----------------|
| 8 SPS | 62.5 µV | 16 |
| 128 SPS | 62.5 µV | 16 |
| 860 SPS | 62.5 µV | ~15 |

At lower FSR (higher gain), noise increases proportionally less than signal, improving SNR for small signals.

---

## FAILURE MODES VS NORMAL BEHAVIOR

### ACTUAL HARDWARE FAILURES

These indicate real problems requiring hardware debugging:

**No I2C ACK (NACK on address byte)**
- ADDR pin not connected or floating
- Wrong address being used
- SDA/SCL wired incorrectly or swapped
- Device not powered (check VDD)
- No pullup resistors on I2C lines
- Device damaged

**Stuck at 0x7FFF (positive full-scale)**
- Input voltage exceeds FSR positive limit
- Input pin floating (pulled up internally)
- PGA setting too sensitive for input range

**Stuck at 0x8000 (negative full-scale)**
- Input voltage below 0V (not supported in single-ended)
- Differential input polarity reversed
- PGA setting too sensitive for input range

**Readings jump erratically / high noise**
- Poor grounding between ADS1115 and signal source
- Missing or inadequate decoupling capacitor
- EMI interference (long unshielded wires)
- Ground loops
- Unstable power supply

**I2C bus hangs (SDA stuck low)**
- Interrupted transaction left device mid-byte
- Power glitch during communication
- Fix: toggle SCL 9+ times with SDA high, then send STOP

### NORMAL BEHAVIOR THAT MAY LOOK WRONG

These are expected behaviors, not failures:

**Reading previous conversion value**
- In continuous mode, reading returns the last *completed* conversion
- If you start a new conversion and read immediately, you get the old value
- Solution: Wait for conversion time or poll OS bit

**OS bit reads 0 right after writing 1**
- This is correct — OS=0 means "conversion in progress"
- After conversion completes, OS returns to 1

**Slight negative readings on single-ended inputs near 0V**
- Offset error can produce small negative codes (e.g., 0xFFFF = -1 LSB)
- This is within specification: offset error is ±3 LSB typical
- Solution: Clamp negative values to zero in software if needed

**Cannot reach full-scale code with FSR > VDD**
- With VDD = 3.3V and FSR = ±6.144V, max code is ~17,600 not 32,767
- This is correct — you can only measure up to VDD
- The larger FSR just provides coarser resolution

**First reading after power-up is 0x0000**
- Conversion register initializes to zero
- First valid reading appears after first conversion completes

**Readings drift with temperature**
- Gain drift: 5-40 ppm/°C typical
- Offset drift: 0.005 LSB/°C
- This is within specification

**Data rate varies by ±10%**
- Internal oscillator tolerance
- 860 SPS may actually be 774-946 SPS
- This is within specification

**Comparator doesn't trigger**
- Check COMP_QUE bits — default (11) disables comparator
- Verify threshold registers are set appropriately

---

## ESP32-S3 + MICROPYTHON INTEGRATION

### I2C Initialization

```python
from machine import I2C, Pin

# Hardware I2C (recommended)
i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400000)

# Verify device present
devices = i2c.scan()
if 0x48 not in devices:
    print("ADS1115 not found!")
```

### Pin Selection Guidelines

Any ESP32-S3 GPIO can be used for I2C. Avoid:
- GPIO26-37 (reserved for flash/PSRAM on N16R8)
- GPIO0, 3, 45, 46 (strapping pins — usable but affect boot)
- GPIO19-20 (USB-JTAG — usable but disables USB debug)

### Byte Order

The ADS1115 sends data MSB-first. MicroPython's `int.from_bytes()` with `'big'` handles this correctly.

```python
# Writing 16-bit config
config = 0xC3E3
i2c.writeto_mem(0x48, 0x01, config.to_bytes(2, 'big'))

# Reading 16-bit result
raw = i2c.readfrom_mem(0x48, 0x00, 2)
value = int.from_bytes(raw, 'big')
```

### Timing Between Operations

The ADS1115 doesn't require delays between I2C transactions. However:
- After writing config with OS=1, wait for conversion time before reading
- I2C timeout: If bus idle >25ms, it times out (rarely an issue)

### Handling Signed Values

```python
def read_signed(i2c, addr=0x48):
    """Read conversion register as signed 16-bit integer."""
    raw = i2c.readfrom_mem(addr, 0x00, 2)
    value = int.from_bytes(raw, 'big')
    if value >= 0x8000:
        value -= 0x10000
    return value
```

---

## COMMON CONFIG REGISTER VALUES

Quick reference for typical configurations (single-ended, AIN0 vs GND):

| FSR | Data Rate | Config Value | Use Case |
|-----|-----------|--------------|----------|
| ±4.096V | 128 SPS | 0xC383 | General purpose |
| ±4.096V | 860 SPS | 0xC3E3 | Fast sampling |
| ±2.048V | 128 SPS | 0xC583 | Higher resolution |
| ±0.256V | 8 SPS | 0xC703 | Small signals, low noise |

**Breakdown of 0xC3E3:**
- 0xC3E3 = 1100 0011 1110 0011
- Bit 15 (OS) = 1: Start conversion
- Bits 14:12 (MUX) = 100: AIN0 vs GND
- Bits 11:9 (PGA) = 001: ±4.096V
- Bit 8 (MODE) = 1: Single-shot
- Bits 7:5 (DR) = 111: 860 SPS
- Bits 4:0 = 00011: Comparator disabled

---

## STARTUP SEQUENCE

1. Power on (device enters power-down state with default config 0x8583)
2. Initialize I2C bus at ≤400 kHz
3. Scan bus to verify device responds at expected address
4. Write desired configuration to config register
5. Begin conversions (continuous mode runs automatically; single-shot needs OS=1 trigger)

---

## DECOUPLING AND LAYOUT

- Place 0.1µF ceramic capacitor close to VDD and GND pins
- Keep analog input traces short and away from digital signals
- Use ground plane under device if possible
- For best noise performance, use shielded cables on analog inputs

---

## ABSOLUTE MAXIMUM RATINGS

Exceeding these may permanently damage the device:

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| VDD to GND | –0.3 | 7 | V |
| Analog input to GND | GND – 0.3 | VDD + 0.3 | V |
| Digital input to GND | –0.3 | 5.5 | V |
| Continuous input current | –10 | +10 | mA |
| Operating temperature | –40 | +125 | °C |
| Storage temperature | –60 | +150 | °C |

---

## REFERENCES

- [ADS111x Datasheet (TI)](https://www.ti.com/lit/ds/symlink/ads1115.pdf) — SBAS444E, Rev. December 2024
- [ESP32-S3 N16R8 Hardware Reference](./esp32-s3-n16r8-hardware-reference.md)

---

*Document Version: 1.0*
*Last Updated: November 2025*
*Target Hardware: ADS1115 with ESP32-S3 N16R8*
