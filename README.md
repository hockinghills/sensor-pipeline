# Raspberry Pi Sensor Data Pipeline

A complete IoT sensor data pipeline using Podman quadlets for containerized services.

## Architecture

```
ESP32 → MQTT → HiveMQ Edge → Telegraf → InfluxDB v3 → Grafana
BME680 Sensor → Telegraf → InfluxDB v3 → Grafana
```

## Components

### 1. HiveMQ Edge MQTT Broker
- **Port**: 1883 (MQTT), 8080 (Web UI)
- **Data**: Persisted in `data/hivemq/`
- **Purpose**: Receives MQTT messages from ESP32 sensors

### 2. InfluxDB v3 Core
- **Port**: 8181
- **Data**: Persisted in `data/influxdb/`
- **Purpose**: Time-series database for sensor data
- **Node ID**: piiot

### 3. Telegraf
- **Purpose**: Data collection agent
- **Inputs**:
  - MQTT consumer (from HiveMQ)
  - BME680 environmental sensor via I2C (0x77)
  - ADS1115 ADC for O2 sensor via I2C (0x48)
- **Output**: InfluxDB v3

## I2C Sensor Setup

### BME680 Environmental Sensor
The BME680 connects via I2C and provides:
- Temperature
- Humidity
- Pressure
- Air quality (gas resistance)

**I2C Address**: 0x77

### ADS1115 ADC for O2 Sensor
The ADS1115 16-bit ADC connects via I2C and reads an automotive O2 sensor on channel A1:
- Voltage range: ~0-1V (after polarity correction)
- O2 sensor calibration: 0.0196V = 0% O2 (rich), 0.2373V = 21% O2 (air)
- Formula: `O2% = (voltage - 0.0196) × 96.47`
- Sampling rate: 100ms

**I2C Address**: 0x48
**Channel**: A1 (in_voltage1_raw)

## Installation

### 1. Clone Repository
```bash
git clone <this-repo>
cd sensor-pipeline
```

### 2. Copy Quadlets
```bash
cp quadlets/*.container ~/.config/containers/systemd/
```

### 3. Copy Telegraf Config
```bash
cp configs/telegraf.conf ~/sensor-pipeline/configs/
```

### 4. Create Data Directories
Data directories are automatically created by the containers.

### 5. Reload and Start Services
```bash
systemctl --user daemon-reload
systemctl --user start hivemq.service influxdb.service telegraf.service
```

### 6. Enable Auto-start
```bash
systemctl --user enable hivemq.service influxdb.service telegraf.service
```

## Configuration

### InfluxDB Setup
After first start, create database and token:
```bash
# Access InfluxDB
curl http://localhost:8181/health

# Create initial database and token via API
# (Token and bucket creation commands to be added)
```

### Telegraf Configuration
Located in `configs/telegraf.conf`:
- **MQTT Input**: Subscribes to `furnace/data` topic at 10ms interval
- **BME680 Input**: Reads from `/sys/bus/i2c/devices/1-0077/iio:device1` at 1000ms interval
- **ADS1115 Input**: Reads from `/sys/bus/i2c/devices/1-0048/iio:device0` at 100ms interval
- **Output**: InfluxDB v3 at `http://127.0.0.1:8181`
- **Bucket**: `fucked`

## Troubleshooting

### Service Status
```bash
systemctl --user status hivemq.service influxdb.service telegraf.service
```

### Logs
```bash
journalctl --user -u hivemq.service -f
journalctl --user -u influxdb.service -f
journalctl --user -u telegraf.service -f
```

### Container Status
```bash
podman ps
podman logs hivemq
podman logs influxdb3
podman logs telegraf
```

### I2C Sensor Issues

#### Verifying Sensors on I2C Bus
```bash
# Scan I2C bus for devices
i2cdetect -y 1

# Should show:
# 0x48 - ADS1115 ADC (shows as UU if driver loaded)
# 0x77 - BME680 sensor (shows as UU if driver loaded)
```

#### IIO Device Number Problem (IMPORTANT)

**Known Issue**: IIO device numbers (`device0`, `device1`) can change on reboot depending on initialization order.

**Current Configuration**:
- BME680 → `/sys/bus/i2c/devices/1-0077/iio:device1`
- ADS1115 → `/sys/bus/i2c/devices/1-0048/iio:device0`

**How to Detect the Problem**:
If data stops flowing after reboot, device numbers may have swapped. Check Telegraf logs:
```bash
podman logs telegraf 2>&1 | grep -i "no such file"
```

**How to Fix**:
1. Check which device numbers were actually assigned:
```bash
ls -la /sys/bus/i2c/devices/1-0077/iio:device*
ls -la /sys/bus/i2c/devices/1-0048/iio:device*
```

2. Edit `configs/telegraf.conf` and update the `base_dir` paths to match actual device numbers:
```bash
# For BME680 (look for this section):
[[inputs.multifile]]
  base_dir = "/sys/bus/i2c/devices/1-0077/iio:deviceN"  # Change N to actual number

# For ADS1115 (look for this section):
[[inputs.multifile]]
  base_dir = "/sys/bus/i2c/devices/1-0048/iio:deviceN"  # Change N to actual number
```

3. Restart Telegraf:
```bash
systemctl --user restart telegraf.service
```

**Why This Happens**:
The device numbers are assigned by the kernel in the order devices are initialized. The quadlet ExecStartPre commands run in sequence, which *should* keep the order stable, but this is not guaranteed.

**Attempted Solutions (Did Not Work)**:
- udev rules with SYMLINK (ADS1115 worked, BME680 did not match rules)
- /dev/iio/* symlinks (Telegraf multifile plugin cannot follow symlinks)
- Wildcard paths in base_dir (Telegraf does not expand wildcards)

#### Manual Sensor Initialization
```bash
# BME680
sudo modprobe bme680_i2c
echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device

# ADS1115
sudo modprobe ti-ads1015
echo "ads1015 0x48" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device

# Verify
ls /sys/bus/i2c/devices/1-0077/iio:device*/
ls /sys/bus/i2c/devices/1-0048/iio:device*/
```

#### Reading Sensor Values Directly
```bash
# BME680 temperature (in millidegrees C)
cat /sys/bus/i2c/devices/1-0077/iio:device*/in_temp_input

# ADS1115 channel A1 voltage (raw value in millivolts)
cat /sys/bus/i2c/devices/1-0048/iio:device*/in_voltage1_raw

# O2 sensor requires polarity reversal: actual_voltage = -1 * raw_value
```

### Port Conflicts
If services fail to start, check for port conflicts:
```bash
netstat -tln | grep -E "1883|8080|8181"
```

Common conflicts:
- Native `influxdb3.service` taking port 8181
- Manual containers taking ports

### InfluxDB v3 Initialization Issues

**Known Issue**: InfluxDB v3 may fail with "Failed to put initial table index conversion marker to object store" error.

**Root Cause Analysis**:
- InfluxDB v3 container runs as UID 1500 (influxdb3 user)
- Data directories are created with UID 1000 (louthenw user)
- Container cannot write to directories due to permission mismatch

**Container User Test**:
```bash
# Check what user the container runs as
podman run --rm docker.io/library/influxdb:3.3-core id

# Test if container can write to data directory
podman run --rm -v /home/louthenw/sensor-pipeline/data/influxdb:/var/lib/influxdb3:Z \
  docker.io/library/influxdb:3.3-core touch /var/lib/influxdb3/test-write
```

**Potential Solutions Under Investigation**:
1. Use `--without-auth` flag for InfluxDB v3 (found in help documentation)
2. Add `User=1000:1000` directive to quadlet to match directory ownership
3. Change directory ownership to match container user (UID 1500)

**Working Setup Comparison**:
- Previous working data was in `/home/louthenw/.influxdb3/piiot/` owned by UID 1000
- Quadlet was working with this setup before reboot
- Native `influxdb3.service` took over port 8181 after reboot, blocking quadlet

**Status**: Investigation ongoing. HiveMQ and Telegraf services are running successfully.

## Data Flow

1. **ESP32 Sensors** → Send JSON data via MQTT to topic `furnace/data`
2. **BME680 Sensor** → Exposes data via I2C interface
3. **HiveMQ Edge** → Receives MQTT messages on port 1883
4. **Telegraf** →
   - Subscribes to MQTT topics from HiveMQ
   - Reads BME680 data from I2C
   - Sends all data to InfluxDB
5. **InfluxDB v3** → Stores time-series data
6. **Grafana** → Visualizes data from InfluxDB

## File Structure

```
sensor-pipeline/
├── README.md
├── quadlets/
│   ├── hivemq.container      # HiveMQ Edge quadlet
│   ├── influxdb.container    # InfluxDB v3 quadlet
│   └── telegraf.container    # Telegraf quadlet
├── configs/
│   └── telegraf.conf         # Telegraf configuration
├── data/
│   ├── hivemq/              # HiveMQ persistence
│   ├── influxdb/            # InfluxDB data
│   └── telegraf/            # Telegraf logs (if needed)
└── scripts/
    └── (future backup/maintenance scripts)
```

## Network Configuration

- **Pi IP**: 192.168.50.224
- **MQTT Port**: 1883
- **HiveMQ Web UI**: http://192.168.50.224:8080
- **InfluxDB API**: http://192.168.50.224:8181

## Dependencies

- Podman with quadlet support
- systemd user services enabled
- I2C kernel modules for BME680
- Network connectivity for container pulls

## Backup

Important directories to backup:
- `data/influxdb/` - All sensor data
- `data/hivemq/` - MQTT broker state
- `configs/telegraf.conf` - Data collection config

## Recovery

In case of issues:
1. Stop all services: `systemctl --user stop hivemq.service influxdb.service telegraf.service`
2. Check service status and logs
3. Verify container images: `podman images`
4. Restart services: `systemctl --user start hivemq.service influxdb.service telegraf.service`

---

**Created**: 2025-09-19
**Last Updated**: 2025-10-04
**Version**: 1.2