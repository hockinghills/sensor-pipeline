# MAX31856 Precision Thermocouple Interface Hardware Reference
## For Use With ESP32-S3 N16R8

**Scope:** This document covers MAX31856 specifications relevant to ESP32-S3 integration via MicroPython SPI. Type S thermocouples are emphasized for glass furnace applications, but all supported types are documented.

**Source:** Maxim/Analog Devices MAX31856 Datasheet (Rev 0, February 2015)

---

## DEVICE OVERVIEW

The MAX31856 is a precision thermocouple-to-digital converter with:
- 19-bit ADC for thermocouple voltage measurement
- Internal cold-junction temperature sensor
- Automatic linearization for 8 thermocouple types (B, E, J, K, N, R, S, T)
- Cold-junction compensation
- Fault detection (open circuit, over/undervoltage, temperature range)
- SPI interface
- ±45V input protection

**Resolution:** 0.0078125°C (approximately 1/128°C)

---

## ELECTRICAL SPECIFICATIONS

### Power Supply

| Parameter | Min | Typical | Max | Unit |
|-----------|-----|---------|-----|------|
| Supply voltage (AVDD, DVDD) | 3.0 | 3.3 | 3.6 | V |
| AVDD to DVDD difference | -100 | — | +100 | mV |
| Active current | — | 1.2 | 2 | mA |
| Standby current | — | 5.25 | 10 | µA |

**ESP32-S3 Compatibility:** The MAX31856 operates within ESP32's 3.3V rail. Both AVDD and DVDD should be connected to the same 3.3V supply.

### Digital I/O Levels

| Parameter | Value | Unit |
|-----------|-------|------|
| Input low (VIL) | ≤ 0.8 | V |
| Input high (VIH) | ≥ 2.1 | V |
| Output low (VOL) at 1.6mA | ≤ 0.4 | V |
| Output high (VOH) at -1.6mA | ≥ VDD - 0.4 | V |
| Input leakage | ±1 | µA |
| Input capacitance | 8 | pF |

**ESP32-S3 Compatibility:** At 3.3V operation, these levels are fully compatible with ESP32-S3 GPIO.

### Thermocouple Input

| Parameter | Min | Typical | Max | Unit |
|-----------|-----|---------|-----|------|
| Input protection voltage | -45 | — | +45 | V |
| Input common-mode range | 0.5 | — | 1.4 | V |
| Input bias current (25°C) | -10 | — | +10 | nA |
| Input bias current (-40°C to +85°C) | -10 | — | +65 | nA |
| Differential bias current (25°C) | — | ±0.2 | — | nA |
| BIAS output voltage | — | 0.735 | — | V |
| BIAS output resistance | — | 2 | — | kΩ |

### Accuracy

| Parameter | Condition | Min | Max | Unit |
|-----------|-----------|-----|-----|------|
| Thermocouple voltage accuracy | -20°C to +85°C | -0.15 | +0.15 | %FS |
| Cold-junction accuracy | -20°C to +85°C | -0.7 | +0.7 | °C |
| Cold-junction accuracy | -55°C to +125°C | -2 | +2 | °C |

---

## SPI INTERFACE

### SPI Mode

**CRITICAL: The MAX31856 supports both CPOL=0 and CPOL=1, but requires CPHA=1.**

| Parameter | Requirement |
|-----------|-------------|
| Clock polarity (CPOL) | 0 or 1 (auto-detected) |
| Clock phase (CPHA) | **Must be 1** |
| Bit order | MSB first |
| Data width | 8 bits per transfer |

**SPI Mode Summary:**
- CPOL=0, CPHA=1 → SPI Mode 1
- CPOL=1, CPHA=1 → SPI Mode 3

The MAX31856 samples SCLK when CS goes low to determine clock polarity. Either mode 1 or mode 3 works.

### SPI Timing Requirements

| Parameter | Symbol | Min | Max | Unit |
|-----------|--------|-----|-----|------|
| Clock frequency | fSCL | — | 5 | MHz |
| Clock high time | tCH | 100 | — | ns |
| Clock low time | tCL | 100 | — | ns |
| Clock rise/fall time | tR, tF | — | 200 | ns |
| CS fall to first SCLK rise | tCC | 100 | — | ns |
| Last SCLK to CS rise | tCCH | 100 | — | ns |
| CS high between transfers | tCWH | 400 | — | ns |
| **Data setup time (SDI to SCLK)** | **tDC** | **35** | — | **ns** |
| **Data hold time (SCLK to SDI)** | **tCDH** | **35** | — | **ns** |
| SCLK fall to SDO valid | tCDD | — | 80 | ns |
| CS rise to SDO high-Z | tCDZ | — | 40 | ns |

### CRITICAL: SPI Timing for Data Input (SDI)

**This is where bugs happen.**

The data setup time (tDC = 35ns minimum) means:
- **SDI must be stable at least 35ns BEFORE the sampling clock edge**
- For CPOL=1/CPHA=1 (Mode 3): Data is sampled on SCLK rising edge
- For CPOL=0/CPHA=1 (Mode 1): Data is sampled on SCLK falling edge

**BUG PATTERN:** Setting MOSI (SDI) after the clock edge instead of before violates tDC. This causes intermittent communication failures that may appear as random bit errors or completely failed transactions.

**Correct sequence for bit-banged SPI (Mode 1, CPOL=0, CPHA=1):**
```
1. Set SDI to bit value
2. Wait for data setup time (≥35ns)
3. Raise SCLK (this is when MAX31856 samples SDI)
4. Wait for clock high time (≥100ns)
5. Lower SCLK
6. Wait for clock low time (≥100ns)
7. Repeat for next bit
```

**Incorrect (buggy) sequence:**
```
1. Raise SCLK
2. Set SDI to bit value  ← WRONG: data changes after sample edge
3. Wait
4. Lower SCLK
```

**ESP32-S3 Hardware SPI:** When using hardware SPI at ≤5 MHz, timing is handled automatically. Bit-banged implementations must respect these timing constraints.

### CS Timing

- **CS must go low at least 100ns before first SCLK edge** (tCC)
- **CS must stay low until at least 100ns after last SCLK edge** (tCCH)
- **CS must stay high at least 400ns between transactions** (tCWH)

### Address Byte Format

Every SPI transaction starts with an address byte:

| Bit 7 | Bits 6:0 |
|-------|----------|
| R/W | Register Address |

- **Bit 7 = 0:** Read operation (address 0x00-0x0F)
- **Bit 7 = 1:** Write operation (address 0x80-0x8F)

**Example:** 
- Read register 0x0F → Send 0x0F
- Write register 0x00 → Send 0x80

### Multi-Byte Transfers

The address auto-increments during multi-byte transfers. Reading 3 bytes starting at 0x0C returns registers 0x0C, 0x0D, 0x0E (the linearized temperature).

---

## REGISTER MAP

| Read Addr | Write Addr | Name | Default | Description |
|-----------|------------|------|---------|-------------|
| 0x00 | 0x80 | CR0 | 0x00 | Configuration 0 |
| 0x01 | 0x81 | CR1 | 0x03 | Configuration 1 |
| 0x02 | 0x82 | MASK | 0xFF | Fault Mask |
| 0x03 | 0x83 | CJHF | 0x7F | Cold-Junction High Fault Threshold |
| 0x04 | 0x84 | CJLF | 0xC0 | Cold-Junction Low Fault Threshold |
| 0x05 | 0x85 | LTHFTH | 0x7F | TC High Fault Threshold MSB |
| 0x06 | 0x86 | LTHFTL | 0xFF | TC High Fault Threshold LSB |
| 0x07 | 0x87 | LTLFTH | 0x80 | TC Low Fault Threshold MSB |
| 0x08 | 0x88 | LTLFTL | 0x00 | TC Low Fault Threshold LSB |
| 0x09 | 0x89 | CJTO | 0x00 | Cold-Junction Offset |
| 0x0A | 0x8A | CJTH | 0x00 | Cold-Junction Temp MSB |
| 0x0B | 0x8B | CJTL | 0x00 | Cold-Junction Temp LSB |
| 0x0C | — | LTCBH | 0x00 | Linearized TC Temp Byte 2 (read-only) |
| 0x0D | — | LTCBM | 0x00 | Linearized TC Temp Byte 1 (read-only) |
| 0x0E | — | LTCBL | 0x00 | Linearized TC Temp Byte 0 (read-only) |
| 0x0F | — | SR | 0x00 | Fault Status (read-only) |

---

## CONFIGURATION REGISTERS

### CR0 (0x00/0x80) - Configuration 0

| Bit | Name | Default | Description |
|-----|------|---------|-------------|
| 7 | CMODE | 0 | 0=Normally off, 1=Auto conversion (~100ms cycle) |
| 6 | 1SHOT | 0 | Write 1 to trigger single conversion (self-clears) |
| 5:4 | OCFAULT[1:0] | 00 | Open-circuit detection mode |
| 3 | CJ | 0 | 0=Internal CJ sensor enabled, 1=Disabled |
| 2 | FAULT | 0 | 0=Comparator mode, 1=Interrupt mode |
| 1 | FAULTCLR | 0 | Write 1 to clear fault status (self-clears) |
| 0 | 50/60Hz | 0 | 0=60Hz rejection, 1=50Hz rejection |

#### Open-Circuit Detection (OCFAULT[1:0])

| Value | Mode | Test Time | Use Case |
|-------|------|-----------|----------|
| 00 | Disabled | 0 | Fastest conversions |
| 01 | Enabled | ~10ms | Low cable resistance (<5kΩ) |
| 10 | Enabled | ~32ms | Medium cable (5-40kΩ, τ<2ms) |
| 11 | Enabled | ~100ms | High cable (5-40kΩ, τ>2ms) |

Open-circuit detection runs every 16 conversions in auto mode.

### CR1 (0x01/0x81) - Configuration 1

| Bit | Name | Default | Description |
|-----|------|---------|-------------|
| 7 | Reserved | 0 | — |
| 6:4 | AVGSEL[2:0] | 000 | Averaging mode |
| 3:0 | TC TYPE[3:0] | 0011 | Thermocouple type |

#### Averaging Mode (AVGSEL[2:0])

| Value | Samples | Added Time (60Hz) | Added Time (50Hz) |
|-------|---------|-------------------|-------------------|
| 000 | 1 | 0 | 0 |
| 001 | 2 | +16.67ms / +33.33ms* | +20ms / +40ms* |
| 010 | 4 | +50ms / +100ms* | +60ms / +120ms* |
| 011 | 8 | +117ms / +233ms* | +140ms / +280ms* |
| 1xx | 16 | +250ms / +500ms* | +300ms / +600ms* |

*First value is for continuous mode (conversions 2+), second is for 1-shot or first conversion.

#### Thermocouple Type (TC TYPE[3:0])

| Value | Type | Temp Range | Sensitivity | CJ Range |
|-------|------|------------|-------------|----------|
| 0000 | B | +250°C to +1820°C | ~10 µV/°C | 0°C to +125°C |
| 0001 | E | -200°C to +1000°C | ~76 µV/°C | -55°C to +125°C |
| 0010 | J | -210°C to +1200°C | ~58 µV/°C | -55°C to +125°C |
| 0011 | K | -200°C to +1372°C | ~41 µV/°C | -55°C to +125°C |
| 0100 | N | -200°C to +1300°C | ~36 µV/°C | -55°C to +125°C |
| 0101 | R | -50°C to +1768°C | ~10.5 µV/°C | -50°C to +125°C |
| **0110** | **S** | **-50°C to +1768°C** | **~9.6 µV/°C** | **-50°C to +125°C** |
| 0111 | T | -200°C to +400°C | ~52 µV/°C | -55°C to +125°C |
| 10xx | Voltage (Gain=8) | ±78.125mV FSR | — | — |
| 11xx | Voltage (Gain=32) | ±19.531mV FSR | — | — |

**For glass furnace (Type S):** Use TC TYPE = 0110 (0x06).

### Fault Mask Register (0x02/0x82)

| Bit | Name | Default | Description |
|-----|------|---------|-------------|
| 7:6 | Reserved | 11 | — |
| 5 | CJ High Mask | 1 | 1=Masked (no FAULT assertion) |
| 4 | CJ Low Mask | 1 | 1=Masked |
| 3 | TC High Mask | 1 | 1=Masked |
| 2 | TC Low Mask | 1 | 1=Masked |
| 1 | OVUV Mask | 1 | 1=Masked |
| 0 | Open Mask | 1 | 1=Masked |

**Default (0xFF) masks all faults.** To use FAULT pin, write 0 to relevant mask bits.

**Note:** CJ Range and TC Range faults (bits 7:6 in fault status) NEVER assert FAULT pin regardless of mask.

### Fault Status Register (0x0F) - Read Only

| Bit | Name | Description |
|-----|------|-------------|
| 7 | CJ Range | Cold junction out of normal range |
| 6 | TC Range | Thermocouple out of normal range |
| 5 | CJHIGH | CJ temp above high threshold |
| 4 | CJLOW | CJ temp below low threshold |
| 3 | TCHIGH | TC temp above high threshold |
| 2 | TCLOW | TC temp below low threshold |
| 1 | OVUV | Input overvoltage or undervoltage |
| 0 | OPEN | Open thermocouple detected |

---

## TEMPERATURE DATA FORMATS

### Cold-Junction Temperature (Registers 0x0A, 0x0B)

**Format:** 14-bit signed value, 0.015625°C per LSB

| Byte | Bits | Weight |
|------|------|--------|
| 0x0A (MSB) | [7:0] | Sign, 2^6 to 2^0 |
| 0x0B (LSB) | [7:2] | 2^-1 to 2^-6 |
| 0x0B (LSB) | [1:0] | Always 0 (unused) |

**Range:** -64°C to +127.984375°C (clamped at these limits)

### CRITICAL: Two's Complement Conversion for Cold Junction

**This is where the second bug pattern occurs.**

The cold-junction temperature is stored as a 14-bit signed value across two bytes. The correct conversion sequence is:

```python
def read_cold_junction(msb, lsb):
    # Step 1: Combine bytes into 16-bit value
    raw = (msb << 8) | lsb
    
    # Step 2: Shift right to get 14-bit value (discard 2 LSBs)
    raw = raw >> 2
    
    # Step 3: Check sign bit BEFORE any offset application
    if raw & 0x2000:  # Bit 13 is sign bit for 14-bit value
        raw = raw - 0x4000  # Convert from unsigned to signed
    
    # Step 4: Convert to temperature
    temp_c = raw * 0.015625
    
    return temp_c
```

**BUG PATTERN:** Applying offset correction (from register 0x09) before checking the sign bit produces wrong results for negative temperatures. The offset is already incorporated into the register value by the chip - it should NOT be applied again in software.

**Correct understanding:**
- The value in registers 0x0A/0x0B already includes any offset from register 0x09
- Software should only convert the raw value to temperature
- No additional offset math needed

**Example values:**

| Temperature | MSB (0x0A) | LSB (0x0B) | Raw 14-bit | Notes |
|-------------|------------|------------|------------|-------|
| +25.0°C | 0x19 | 0x00 | 0x0640 | 1600 × 0.015625 |
| +0.5°C | 0x00 | 0x80 | 0x0020 | 32 × 0.015625 |
| 0.0°C | 0x00 | 0x00 | 0x0000 | |
| -0.5°C | 0xFF | 0x80 | 0x3FE0→-32 | Two's complement |
| -25.0°C | 0xE7 | 0x00 | 0x39C0→-1600 | |
| -55.0°C | 0xC9 | 0x00 | 0x3240→-3520 | Near limit |

### Linearized Thermocouple Temperature (Registers 0x0C, 0x0D, 0x0E)

**Format:** 19-bit signed value, 0.0078125°C per LSB (1/128°C)

| Byte | Bits | Weight |
|------|------|--------|
| 0x0C (High) | [7:0] | Sign, 2^10 to 2^4 |
| 0x0D (Mid) | [7:0] | 2^3 to 2^-4 |
| 0x0E (Low) | [7:3] | 2^-5 to 2^-7 |
| 0x0E (Low) | [4:0] | Unused (read as X) |

**Range:** Depends on thermocouple type (see TC TYPE table)

```python
def read_thermocouple_temp(high, mid, low):
    # Step 1: Combine into 24-bit value
    raw = (high << 16) | (mid << 8) | low
    
    # Step 2: Shift right 5 bits to get 19-bit value
    raw = raw >> 5
    
    # Step 3: Check sign bit (bit 18 of 19-bit value)
    if raw & 0x40000:  # Bit 18 set = negative
        raw = raw - 0x80000  # Convert to signed
    
    # Step 4: Convert to temperature
    temp_c = raw * 0.0078125
    
    return temp_c
```

---

## CONVERSION TIMING

### Base Conversion Times

| Mode | Filter | First/1-Shot | Subsequent (Auto) |
|------|--------|--------------|-------------------|
| Normal | 60Hz | 143-155 ms | 82-90 ms |
| Normal | 50Hz | 169-185 ms | 98-110 ms |

### With Averaging

Add the following times per the AVGSEL setting:

**1-Shot or First Conversion:**
- 60Hz: Add (samples - 1) × 33.33 ms
- 50Hz: Add (samples - 1) × 40 ms

**Auto Mode (conversions 2+):**
- 60Hz: Add (samples - 1) × 16.67 ms
- 50Hz: Add (samples - 1) × 20 ms

### With Open-Circuit Detection

When enabled (OCFAULT ≠ 00), additional time is added every 16th conversion:

| OCFAULT | CJ Enabled | CJ Disabled |
|---------|------------|-------------|
| 01 | +13-15 ms | +40-44 ms |
| 10 | +33-37 ms | +60-66 ms |
| 11 | +113-125 ms | +140-154 ms |

### Timing Summary for Glass Furnace Application

**Typical setup:** Type S, 60Hz filter, 4-sample averaging, open-circuit detection enabled (mode 10)

- 1-shot conversion: ~143 + 100 = ~243 ms
- Plus open-circuit check (every 16): +37 ms
- **Safe polling interval: 300 ms**

---

## DATA READY INDICATION

### DRDY Pin

- Goes **LOW** when new conversion data is available
- Returns **HIGH** when linearized temperature registers (0x0C-0x0E) OR cold-junction registers (0x0A-0x0B) are read
- Open-drain output (requires external pullup if used)

### Polling Method (without DRDY)

If not using DRDY pin, poll the conversion:

1. Start conversion (write 1-shot bit or use auto mode)
2. Wait appropriate time based on configuration
3. Read temperature registers

**Note:** There is no status bit to indicate "conversion complete." You must either use DRDY or wait the appropriate time.

---

## FAULT DETECTION

### Open-Circuit Detection

Detects broken thermocouple wires by injecting a small current and checking for response.

**Detection criteria:** High impedance at thermocouple input

**Timing modes:** Selectable based on cable characteristics (see OCFAULT bits)

**Limitations:**
- Only runs every 16 conversions in auto mode
- Cable resistance must be < 40kΩ per lead
- Disabled during OVUV fault condition

### Over/Undervoltage Detection

**Overvoltage threshold:** VDD - 0.1V to VDD + 0.35V  
**Undervoltage threshold:** -0.3V to 0V

**CRITICAL:** While OVUV fault is active:
- Conversions are suspended
- Other fault detection is suspended
- OPEN fault cannot be detected or cleared

### Temperature Range Faults

**CJ Range (Bit 7):** Set when cold-junction temperature is outside normal operating range for selected thermocouple type.

**TC Range (Bit 6):** Set when linearized thermocouple temperature is outside normal range for selected type.

**Note:** These bits set but NEVER trigger the FAULT pin, regardless of mask settings.

### Fault Modes

**Comparator Mode (FAULT bit = 0):**
- Fault status bits reflect current state
- Clear automatically when fault condition clears
- 2°C hysteresis on temperature thresholds

**Interrupt Mode (FAULT bit = 1):**
- Fault status bits latch when fault occurs
- Must write FAULTCLR bit to clear
- May re-assert immediately if fault still present

---

## INITIALIZATION SEQUENCE

### Recommended Startup Sequence

```python
def init_max31856_type_s():
    # 1. Wait for power stabilization
    time.sleep_ms(10)
    
    # 2. Write Configuration 1: Type S thermocouple, 4-sample averaging
    #    AVGSEL = 010 (4 samples), TC TYPE = 0110 (Type S)
    #    Value: 0b00100110 = 0x26
    write_register(0x81, 0x26)
    
    # 3. Write Configuration 0: Auto mode, 60Hz filter, OC detection
    #    CMODE=1, OCFAULT=10, CJ enabled, comparator mode, 60Hz
    #    Value: 0b10100000 = 0xA0
    write_register(0x80, 0xA0)
    
    # 4. Optionally configure fault thresholds
    #    (defaults are ±127°C for CJ, ±2047°C for TC)
    
    # 5. Optionally unmask desired faults
    #    Example: unmask open-circuit detection
    write_register(0x82, 0xFE)  # Unmask bit 0 only
    
    # 6. First conversion takes ~250ms with this config
    time.sleep_ms(300)
    
    # 7. Now ready to read
```

### Register Write Verification

After writing configuration registers, read them back to verify:

```python
def verify_config():
    cr0 = read_register(0x00)
    cr1 = read_register(0x01)
    
    if cr0 != expected_cr0 or cr1 != expected_cr1:
        # Communication error - check SPI wiring and timing
        return False
    return True
```

---

## FAILURE MODES VS NORMAL BEHAVIOR

### ACTUAL HARDWARE FAILURES

**No SPI response (MISO stays high/low):**
- CS not connected or wrong polarity
- SCK not reaching device
- MISO not connected
- Device not powered
- Wrong SPI mode (must be mode 1 or 3, CPHA=1)

**All reads return 0xFF:**
- Device in reset (power issue)
- SPI timing violation (see tDC, tCDH requirements)
- Wrong address format (forgot to set bit 7 for writes)

**FAULT pin always asserted:**
- Thermocouple not connected (open circuit)
- Thermocouple polarity reversed (OVUV fault)
- Thermocouple shorted
- Check fault status register to identify specific fault

**Temperature reads 0°C constantly:**
- Conversion not triggered (check CMODE or 1SHOT)
- Reading before conversion completes
- OVUV fault suspending conversions

**Erratic temperature readings:**
- Thermocouple wires picking up noise
- Missing input filter capacitors
- Ground loop between thermocouple and electronics
- EMI from nearby equipment (furnace elements, motors)

**Cold junction reads wrong temperature:**
- MAX31856 not thermally coupled to cold junction
- Heat sources near the IC
- Thermal gradient between IC and thermocouple connection

### NORMAL BEHAVIOR THAT MAY LOOK WRONG

**Temperature is slightly negative when furnace is off:**
- Normal: thermocouple may be slightly below ambient
- Check cold-junction temperature matches actual ambient

**Readings oscillate by ~1°C:**
- Normal: this is within specification
- Averaging mode reduces this

**First reading after power-up is 0:**
- Normal: no conversion has run yet
- Wait for first conversion to complete

**DRDY doesn't go low:**
- Normal if: you haven't started a conversion
- Normal if: you already read the temperature registers (DRDY resets)

**TC Range fault (bit 6) is set:**
- May be normal during startup before furnace reaches operating temp
- Type S has limited low-end range (-50°C)
- Does not affect readings, just indicates out-of-optimal range

**Open fault intermittent:**
- May indicate marginal connection
- Check thermocouple wire crimp/weld
- Increase OCFAULT timing if cable has high resistance/capacitance

**Temperature reading clamps at limit:**
- Normal: the chip clamps at min/max of thermocouple range
- For Type S: -50°C to +1768°C
- Readings outside this range read as the limit value

---

## ESP32-S3 + MICROPYTHON INTEGRATION

### Hardware SPI Initialization

```python
from machine import SPI, Pin

# Hardware SPI (recommended)
spi = SPI(1, 
          baudrate=1000000,  # 1 MHz (conservative, max is 5 MHz)
          polarity=1,        # CPOL=1
          phase=1,           # CPHA=1 (required)
          bits=8,
          firstbit=SPI.MSB)

cs = Pin(10, Pin.OUT, value=1)  # CS starts high
```

### Pin Selection Guidelines

Any ESP32-S3 GPIO can be used. Avoid:
- GPIO26-37 (reserved for flash/PSRAM on N16R8)
- GPIO0, 3, 45, 46 (strapping pins)

Typical setup:
- SCK: GPIO12
- MOSI (SDI): GPIO11  
- MISO (SDO): GPIO13
- CS: GPIO10
- DRDY: GPIO9 (optional)
- FAULT: GPIO14 (optional)

### Basic Read/Write Functions

```python
def read_register(reg):
    """Read single register."""
    cs.value(0)
    spi.write(bytes([reg & 0x7F]))  # Ensure bit 7 = 0 for read
    result = spi.read(1)
    cs.value(1)
    return result[0]

def write_register(reg, value):
    """Write single register."""
    cs.value(0)
    spi.write(bytes([reg | 0x80, value]))  # Set bit 7 = 1 for write
    cs.value(1)

def read_registers(start_reg, count):
    """Read multiple consecutive registers."""
    cs.value(0)
    spi.write(bytes([start_reg & 0x7F]))
    result = spi.read(count)
    cs.value(1)
    return result
```

### Complete Temperature Read

```python
def read_temperatures():
    """Read both cold-junction and thermocouple temperatures."""
    
    # Read all temperature registers at once (0x0A through 0x0F)
    data = read_registers(0x0A, 6)
    
    cj_msb, cj_lsb = data[0], data[1]
    tc_high, tc_mid, tc_low = data[2], data[3], data[4]
    fault = data[5]
    
    # Cold junction: 14-bit signed, 0.015625°C/LSB
    cj_raw = ((cj_msb << 8) | cj_lsb) >> 2
    if cj_raw & 0x2000:
        cj_raw -= 0x4000
    cj_temp = cj_raw * 0.015625
    
    # Thermocouple: 19-bit signed, 0.0078125°C/LSB
    tc_raw = ((tc_high << 16) | (tc_mid << 8) | tc_low) >> 5
    if tc_raw & 0x40000:
        tc_raw -= 0x80000
    tc_temp = tc_raw * 0.0078125
    
    return {
        'cold_junction': cj_temp,
        'thermocouple': tc_temp,
        'fault': fault
    }
```

### Fault Interpretation

```python
def interpret_fault(fault_byte):
    """Decode fault status register."""
    faults = []
    
    if fault_byte & 0x80:
        faults.append('CJ_RANGE')   # Cold junction out of range
    if fault_byte & 0x40:
        faults.append('TC_RANGE')   # Thermocouple out of range
    if fault_byte & 0x20:
        faults.append('CJ_HIGH')    # CJ above high threshold
    if fault_byte & 0x10:
        faults.append('CJ_LOW')     # CJ below low threshold
    if fault_byte & 0x08:
        faults.append('TC_HIGH')    # TC above high threshold
    if fault_byte & 0x04:
        faults.append('TC_LOW')     # TC below low threshold
    if fault_byte & 0x02:
        faults.append('OVUV')       # Over/undervoltage on input
    if fault_byte & 0x01:
        faults.append('OPEN')       # Open thermocouple
        
    return faults if faults else ['OK']
```

---

## TYPE S THERMOCOUPLE NOTES

Type S (Platinum-Rhodium / Platinum) is used in glass furnace applications because:

- Temperature range up to +1768°C covers glass working temps (~2300°F = ~1260°C)
- Excellent stability at high temperatures
- Resistant to oxidation
- Lower sensitivity (~9.6 µV/°C) means more susceptible to noise - use input filtering

**Cold junction range for Type S:** -50°C to +125°C

If cold junction goes below -50°C (unlikely in practice), the CJ Range fault will set but readings may still be useful.

---

## NOISE AND GROUNDING

### Input Filter Capacitors

**Recommended:** 100nF ceramic across T+ and T-

**High-noise environments (near furnace elements):**
- 100nF between T+ and T-
- 10nF between T+ and GND
- 10nF between T- and GND

### Series Resistors

For additional input protection beyond ±45V:
- Add 100Ω to 2kΩ in series with T+ and T-
- Higher values allow more overvoltage protection
- Higher values add offset error due to bias current

### Ground Loops

Thermocouples create a ground loop if both the measurement junction and the MAX31856 ground are connected to the same ground plane through different paths. 

**Solutions:**
- Keep thermocouple electrically isolated from furnace ground
- Use shielded thermocouple cable with shield grounded at one end only
- Ensure single-point grounding of electronics

---

## ABSOLUTE MAXIMUM RATINGS

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| AVDD, DVDD | -0.3 | +4.0 | V |
| T+, T-, BIAS | -45 | +45 | V |
| T+, T-, BIAS current | -20 | +20 | mA |
| Other pins | -0.3 | DVDD + 0.3 | V |
| Operating temperature | -55 | +125 | °C |
| Storage temperature | -65 | +150 | °C |

---

## BUG PREVENTION CHECKLIST

Before deploying MAX31856 driver code, verify:

**SPI Configuration:**
- [ ] CPHA = 1 (mode 1 or mode 3)
- [ ] Bit order is MSB first
- [ ] Clock speed ≤ 5 MHz
- [ ] CS timing respected (100ns setup, 100ns hold, 400ns between)

**Data Timing (if bit-banging):**
- [ ] SDI stable 35ns BEFORE sampling clock edge
- [ ] SDI held stable 35ns AFTER sampling clock edge
- [ ] Not setting MOSI after clock edge

**Two's Complement Handling:**
- [ ] Sign bit checked after combining bytes
- [ ] Sign bit checked after bit shifting
- [ ] Not applying offset register value in software (chip does it)
- [ ] Correct bit positions used for sign (bit 13 for CJ, bit 18 for TC)

**Temperature Conversion:**
- [ ] Using correct LSB weight (0.015625°C for CJ, 0.0078125°C for TC)
- [ ] Correct bit shift before conversion (>>2 for CJ, >>5 for TC)

---

## REFERENCES

- [MAX31856 Datasheet (Analog Devices)](https://www.analog.com/media/en/technical-documentation/data-sheets/max31856.pdf) — Rev 0, February 2015
- [ESP32-S3 N16R8 Hardware Reference](./esp32-s3-n16r8-hardware-reference.md)
- [ADS1115 Hardware Reference](./ads1115-esp32s3-hardware-reference.md)

---

*Document Version: 1.0*
*Last Updated: November 2025*
*Target Hardware: MAX31856 with ESP32-S3 N16R8*
*Application: Lyon's Pyre Glasswerks Furnace Monitoring*
