# Furnace Monitor MicroPython Firmware

ESP32-S3 firmware for flame dynamics and control signal monitoring.

## Hardware

- **ESP32-S3** with MicroPython
- **ADS1115 #1** (0x48): I2C0 on GPIO 17/18 - UV flame sensor
- **ADS1115 #2** (0x49): I2C1 on GPIO 41/42 - 4-20mA control signal (100Ω sense resistor)

## Files

- `ads1115.py` - ADS1115 16-bit ADC driver
- `furnace_monitor.py` - Main monitoring system with FFT analysis
- `main.py` - Auto-run configuration (edit WiFi/Vector settings)
- `deploy_to_esp32.sh` - Deployment script

## Quick Start

1. **Edit main.py** with your WiFi credentials and Pi IP:
   ```python
   WIFI_SSID = "YOUR_SSID"
   WIFI_PASSWORD = "YOUR_PASSWORD"
   VECTOR_HOST = "192.168.50.224"  # Pi IP address
   ```

2. **Deploy to ESP32:**
   ```bash
   ./deploy_to_esp32.sh
   ```

3. **Or manual deployment:**
   ```bash
   mpremote connect /dev/ttyACM0 fs cp ads1115.py :ads1115.py
   mpremote connect /dev/ttyACM0 fs cp furnace_monitor.py :furnace_monitor.py
   mpremote connect /dev/ttyACM0 fs cp main.py :main.py
   ```

4. **Reset ESP32** to auto-run

## Data Output

Sends JSON via UDP to Vector on port 9000:

```json
{
  "timestamp": 1234567890.123,
  "flame": {
    "status": "normal",
    "flicker_freq": 10.5,
    "flicker_mag": 0.0234,
    "thermo_freq": 0.0,
    "thermo_mag": 0.0,
    "rms": 0.0156
  },
  "control": {
    "voltage": 1.234,
    "percent": 67.8,
    "milliamps": 12.34
  }
}
```

## Flame Analysis

- **Flicker frequency (1-20 Hz)**: Normal combustion = 8-12 Hz
- **Thermoacoustic (30-400 Hz)**: Detects resonance/instability
- **Status**: normal, unstable, check, no_signal

## Monitoring

Connect via serial to see real-time output:

```bash
mpremote connect /dev/ttyACM0
```

Or run manually:

```python
from furnace_monitor import FurnaceMonitor
fm = FurnaceMonitor(
    ssid="YOUR_SSID",
    password="YOUR_PASSWORD",
    vector_host="192.168.50.224"
)
fm.init()
fm.monitor(duration_sec=86400, interval_sec=1)  # 24 hours, 1 sec interval
```

## Sampling Rate

- **Current (ADS1115)**: 860 SPS, Nyquist = 430 Hz
- **Future (ADS1256)**: 30,000 SPS, Nyquist = 15 kHz

ADS1115 captures full flicker range (1-20 Hz) and most thermoacoustic (30-400 Hz).
