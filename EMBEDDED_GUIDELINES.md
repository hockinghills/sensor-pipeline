# Embedded Systems Code Guidelines
## Lyon's Pyre Glasswerks Furnace Monitoring System

This document provides context for AI code review tools (CodeRabbit, Claude Code, etc.) working on this codebase. **Read this before reviewing or writing code.**

---

## Project Overview

This system monitors a 150-pound Charlie Correll recuperated pot furnace operating at 2300°F (1260°C). It is research-grade instrumentation for analyzing combustion dynamics in glass hot shop operations.

**Operational Requirements:**
- 24/7 continuous operation
- Real-time temperature monitoring (safety-critical)
- Data pipeline to Grafana Cloud for analysis
- Must survive network outages, sensor failures, and power events
- Recovery without human intervention

**This is not a hobby project.** Code quality directly affects expensive equipment and operational safety.

---

## Hardware Platform

### Microcontroller: ESP32-S3 N16R8

**Full specifications:** See `docs/hardware/esp32-s3-n16r8-hardware-reference.md`

| Resource | Available | Notes |
|----------|-----------|-------|
| CPU | Dual-core 240MHz | Both cores available |
| Flash | 16MB | Program storage |
| PSRAM | 8MB | Runtime data, buffers |
| SRAM | 512KB | Fast access, limited |
| WiFi | 802.11 b/g/n | 2.4GHz only |
| GPIO | ~36 usable | Some reserved for flash/PSRAM |

**Memory Guidance:**
- Multi-MB allocations are FINE (use PSRAM)
- Large sensor buffers are EXPECTED
- Don't flag memory usage without understanding available resources
- DO flag unbounded growth or allocations in tight loops

### Temperature Sensing: MAX31856

**Full specifications:** See `docs/hardware/max31856-esp32s3-hardware-reference.md`

**Critical Details:**
- SPI Mode 1 or 3 (CPHA must be 1)
- Type S thermocouples (platinum, -50°C to +1768°C)
- 19-bit resolution (0.0078125°C)
- Internal cold-junction compensation
- Conversion time: ~150-250ms depending on averaging

**Common Bug Patterns:**
1. Wrong SPI mode (CPHA=0 causes intermittent failures)
2. Setting MOSI after clock edge instead of before
3. Two's complement sign check in wrong position
4. Reading before conversion completes

### Analog Input: ADS1115

**Full specifications:** See `docs/hardware/ads1115-esp32s3-hardware-reference.md`

**Critical Details:**
- I2C address 0x48 (7-bit format)
- 16-bit resolution
- Programmable gain (±0.256V to ±6.144V FSR)
- Sample rates 8-860 SPS

**Common Bug Patterns:**
1. Using 8-bit address format (0x90) instead of 7-bit (0x48)
2. Not waiting for conversion to complete
3. Reading config register instead of conversion register
4. FSR setting doesn't match input voltage range

---

## Code Patterns

### Required: Hardware Communication

All I2C/SPI operations must follow this pattern:

```python
def read_sensor():
    try:
        # Perform hardware communication
        raw_data = i2c.readfrom_mem(ADDR, REG, LENGTH)
        
        # Validate response
        if not validate_data(raw_data):
            log_error("Invalid sensor response")
            return None
            
        # Convert to meaningful value
        value = convert_raw_to_value(raw_data)
        
        # Range check
        if not (MIN_VALID <= value <= MAX_VALID):
            log_warning(f"Value {value} outside expected range")
            
        return value
        
    except OSError as e:
        log_error(f"I2C communication failed: {e}")
        return None
```

**Non-negotiable:**
- Try/except around all bus operations
- Validation of returned data
- Range checking on converted values
- Error logging for diagnostics
- Graceful return on failure (not crash)

### Required: Initialization Sequence

Hardware initialization must:

```python
def init_sensor():
    # 1. Allow power stabilization
    time.sleep_ms(10)
    
    # 2. Verify device is present
    devices = i2c.scan()
    if EXPECTED_ADDR not in devices:
        raise RuntimeError(f"Sensor not found at 0x{EXPECTED_ADDR:02X}")
    
    # 3. Write configuration
    write_config(CONFIG_VALUE)
    
    # 4. Read back and verify
    actual = read_config()
    if actual != CONFIG_VALUE:
        raise RuntimeError(f"Config mismatch: wrote {CONFIG_VALUE:04X}, read {actual:04X}")
    
    # 5. Wait for first conversion if applicable
    time.sleep_ms(CONVERSION_TIME)
    
    # 6. Verify we can read valid data
    test_reading = read_sensor()
    if test_reading is None:
        raise RuntimeError("Failed to get initial reading")
```

### Required: Network Resilience

```python
class DataBuffer:
    """Buffer sensor data during network outages."""
    
    def __init__(self, max_size_mb=4):
        self.buffer = []
        self.max_bytes = max_size_mb * 1024 * 1024
        
    def add(self, reading):
        self.buffer.append(reading)
        self._enforce_limit()
        
    def _enforce_limit(self):
        # Drop oldest data if buffer full
        # (preserves most recent readings)
        while self._size_bytes() > self.max_bytes:
            self.buffer.pop(0)
```

Network code must:
- Never block sensor acquisition waiting for network
- Buffer data locally during outages
- Implement retry with exponential backoff
- Log network failures for diagnostics
- Resume automatically when connection restored

### Required: Watchdog Usage

```python
from machine import WDT

# Initialize watchdog with appropriate timeout
wdt = WDT(timeout=30000)  # 30 seconds

def main_loop():
    while True:
        # Feed watchdog at start of each cycle
        wdt.feed()
        
        # Do sensor readings
        readings = read_all_sensors()
        
        # Feed again if processing takes time
        wdt.feed()
        
        # Handle data
        process_readings(readings)
        
        # Feed before any potentially slow operations
        wdt.feed()
        
        # Network operations
        if network_available():
            send_data(readings)
```

Any operation that might take more than a few seconds must feed the watchdog.

---

## Two's Complement Conversion

This is a common source of bugs. Here's the correct pattern:

### 16-bit Signed (ADS1115)

```python
def to_signed_16(msb, lsb):
    raw = (msb << 8) | lsb
    if raw >= 0x8000:
        raw -= 0x10000
    return raw
```

### 14-bit Signed (MAX31856 Cold Junction)

```python
def to_signed_14(msb, lsb):
    raw = ((msb << 8) | lsb) >> 2  # Shift first
    if raw >= 0x2000:              # Then check sign (bit 13)
        raw -= 0x4000
    return raw
```

### 19-bit Signed (MAX31856 Thermocouple)

```python
def to_signed_19(high, mid, low):
    raw = ((high << 16) | (mid << 8) | low) >> 5  # Shift first
    if raw >= 0x40000:                             # Then check sign (bit 18)
        raw -= 0x80000
    return raw
```

**The bug pattern:** Checking the sign bit before shifting, or checking the wrong bit position.

---

## What Not To Flag

### Acceptable Patterns

**Large buffers:**
```python
# This is FINE - we have 8MB PSRAM
sensor_buffer = bytearray(1024 * 1024)  # 1MB buffer
reading_history = [None] * 10000         # Pre-allocated list
```

**High-frequency operations:**
```python
# This is FINE - it's the point of the system
while True:
    for sensor in sensors:
        reading = sensor.read()  # Multiple sensors, fast polling
        buffer.add(reading)
    time.sleep_ms(100)  # 10Hz update rate
```

**Complex data structures:**
```python
# This is FINE - necessary for the application
class SensorReading:
    def __init__(self):
        self.timestamp = None
        self.tc_temp = None
        self.cj_temp = None
        self.fault_status = None
        self.raw_data = bytearray(16)
        self.metadata = {}
```

**Verbose error handling:**
```python
# This is FINE - we need diagnostics
try:
    result = i2c.readfrom_mem(addr, reg, 2)
except OSError as e:
    print(f"I2C read failed: addr=0x{addr:02X}, reg=0x{reg:02X}, error={e}")
    print(f"Bus state: SDA={sda.value()}, SCL={scl.value()}")
    print(f"Last successful read: {last_success_time}")
    return None
```

### Patterns That ARE Problems

**Unbounded growth:**
```python
# BAD - grows forever
readings = []
while True:
    readings.append(sensor.read())  # Never cleaned up
```

**Allocation in tight loops:**
```python
# BAD - allocates on every iteration
while True:
    data = bytearray(1024)  # Should be pre-allocated
    sensor.read_into(data)
```

**Blocking without timeout:**
```python
# BAD - can hang forever
response = socket.recv(1024)  # No timeout set
```

**Silent failures:**
```python
# BAD - hides problems
try:
    value = sensor.read()
except:
    pass  # Silent failure, no logging
```

---

## Temperature Units

This codebase uses **Celsius internally**. Fahrenheit conversion happens only at display/API boundaries.

```python
# Internal storage: always Celsius
tc_temp_c = read_thermocouple()

# Conversion only when needed for display
tc_temp_f = tc_temp_c * 9/5 + 32
```

**Operating temperature reference:**
- Glass working temp: ~2300°F = ~1260°C
- Annealing: ~900°F = ~482°C
- Room temp: ~70°F = ~21°C

---

## File Organization

```
project/
├── firmware/
│   └── micropython/
│       ├── main.py              # Entry point
│       ├── sensors/
│       │   ├── max31856.py      # Thermocouple driver
│       │   ├── ads1115.py       # ADC driver
│       │   └── flame.py         # Flame sensor
│       ├── network/
│       │   ├── mqtt.py          # MQTT client
│       │   └── wifi.py          # WiFi management
│       └── util/
│           ├── buffer.py        # Data buffering
│           └── watchdog.py      # Watchdog wrapper
├── pipeline/
│   └── ...                      # Data pipeline code
├── dashboards/
│   └── ...                      # Grafana dashboards
├── docs/
│   └── hardware/
│       ├── esp32-s3-n16r8-hardware-reference.md
│       ├── max31856-esp32s3-hardware-reference.md
│       └── ads1115-esp32s3-hardware-reference.md
├── tests/
│   └── ...
├── .coderabbit.yaml
└── EMBEDDED_GUIDELINES.md       # This file
```

---

## Checklist for Code Review

Before approving any PR that touches sensor code:

**Communication:**
- [ ] Correct I2C address format (7-bit for MicroPython)
- [ ] Correct SPI mode (CPHA=1 for MAX31856)
- [ ] Try/except around all bus operations
- [ ] Timeout handling

**Data Conversion:**
- [ ] Correct byte order (check datasheet)
- [ ] Correct bit shift before sign check
- [ ] Correct sign bit position for data width
- [ ] Correct LSB weight for final conversion

**Initialization:**
- [ ] Device presence verified
- [ ] Configuration written and verified
- [ ] Appropriate startup delays
- [ ] Initial reading validated

**Reliability:**
- [ ] Errors logged with useful context
- [ ] Graceful degradation on sensor failure
- [ ] No blocking operations without timeout
- [ ] Watchdog fed during long operations

---

## References

- ESP32-S3 N16R8: `docs/hardware/esp32-s3-n16r8-hardware-reference.md`
- MAX31856: `docs/hardware/max31856-esp32s3-hardware-reference.md`
- ADS1115: `docs/hardware/ads1115-esp32s3-hardware-reference.md`
- [MicroPython ESP32 Documentation](https://docs.micropython.org/en/latest/esp32/quickref.html)
- [Grafana Cloud](https://grafana.com/products/cloud/)

---

*Document Version: 1.0*
*Last Updated: November 2025*
*Project: Lyon's Pyre Glasswerks Furnace Monitoring*
