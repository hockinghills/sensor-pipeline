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
- **Startup time**: ~90 seconds to fully initialize

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
- **Output**: InfluxDB v3
- **Startup**: Waits for HiveMQ MQTT port to be available before starting

## I2C Sensor Setup

### BME680 Environmental Sensor
The BME680 connects via I2C and provides:
- Temperature
- Humidity
- Pressure
- Air quality (gas resistance)

**I2C Address**: 0x77
**IIO Device**: `/sys/bus/i2c/devices/1-0077/iio:device0`

The sensor is automatically initialized by the telegraf quadlet on startup.

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

### Telegraf Configuration
Located in `configs/telegraf.conf`:
- **MQTT Input**: Subscribes to `furnace/data` topic at 100ms interval from `tcp://127.0.0.1:1883`
- **BME680 Input**: Reads from `/sys/bus/i2c/devices/1-0077/iio:device0` at 1000ms interval
- **Output**: InfluxDB v3 at `http://127.0.0.1:8181`
- **Bucket**: `fucked`

**Important**: All services use localhost addresses (127.0.0.1) to ensure the pipeline continues functioning during network outages or router reboots. This prevents "network unreachable" errors when external network connectivity is lost.

### Telegraf Startup Sequence
The telegraf quadlet includes ExecStartPre commands to:
1. Wait for HiveMQ MQTT port (1883) to be available
2. Load BME680 I2C kernel module
3. Initialize BME680 sensor on I2C bus
4. Create symlink for easy access to sensor device

This ensures all dependencies are ready before Telegraf starts, preventing connection errors on boot.

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

#### Verifying BME680 on I2C Bus
```bash
# Scan I2C bus for devices
i2cdetect -y 1

# Should show:
# 0x77 - BME680 sensor (shows as UU if driver loaded)
```

#### Manual Sensor Initialization
If the sensor doesn't initialize automatically:
```bash
# BME680
sudo modprobe bme680_i2c
echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device

# Verify
ls /sys/bus/i2c/devices/1-0077/iio:device*/
```

#### Reading Sensor Values Directly
```bash
# BME680 temperature (in millidegrees C)
cat /sys/bus/i2c/devices/1-0077/iio:device0/in_temp_input

# BME680 pressure
cat /sys/bus/i2c/devices/1-0077/iio:device0/in_pressure_input

# BME680 humidity
cat /sys/bus/i2c/devices/1-0077/iio:device0/in_humidityrelative_input
```

### Port Conflicts
If services fail to start, check for port conflicts:
```bash
netstat -tln | grep -E "1883|8080|8181"
```

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
- netcat (nc) for port checking
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

## Pipeline Verification

Use this process to verify the data pipeline is functioning correctly. Run BEFORE and AFTER making changes to ensure nothing broke.

### Quick Health Check

```bash
# 1. Verify ESP32 MQTT data is flowing
timeout 2 mosquitto_sub -h 127.0.0.1 -t 'furnace/data' -C 1
```
**Expected output:**
```json
{"temp":2313.53,"cjtemp":36.08,"flame":6.71,"pressure_inlet":1.03,"pressure_outlet":0.06,"heap":196076}
```
Fields present:
- `temp`: Furnace temperature (°F)
- `cjtemp`: Cold junction temperature (°C)
- `flame`: Flame sensor voltage
- `pressure_inlet`: Inlet pressure (PSI)
- `pressure_outlet`: Outlet pressure (PSI)
- `heap`: ESP32 free heap memory (bytes)

```bash
# 2. Verify BME680 sensor is readable
cat /sys/bus/i2c/devices/1-0077/iio:device0/in_temp_input
cat /sys/bus/i2c/devices/1-0077/iio:device0/in_pressure_input
cat /sys/bus/i2c/devices/1-0077/iio:device0/in_humidityrelative_input
```
**Expected output:**
```
36720               # Temperature in millidegrees Celsius (36.72°C)
98.212000000        # Pressure in kPa
43.148000000        # Relative humidity in percent
```

```bash
# 3. Check Telegraf for errors
podman logs --tail 20 telegraf
```
**Expected output (clean startup, no errors):**
```
2025-10-18T06:40:14Z I! Loading config: /etc/telegraf/telegraf.conf
2025-10-18T06:40:14Z I! Starting Telegraf 1.35.4
2025-10-18T06:40:14Z I! Loaded inputs: mqtt_consumer multifile
2025-10-18T06:40:14Z I! Loaded outputs: influxdb_v2
2025-10-18T06:40:14Z I! [inputs.mqtt_consumer] Connected [tcp://127.0.0.1:1883]
```

No `E!` (error) lines should appear repeatedly. One-time startup warnings are acceptable.

### If Something Breaks
1. Check service status: `systemctl --user status hivemq.service telegraf.service influxdb.service`
2. Verify config syntax: Check `configs/telegraf.conf` for typos
3. Check Grafana Cloud: Is data still appearing in dashboards?
4. Restart services: `systemctl --user restart telegraf.service`

---

**Created**: 2025-09-19
**Last Updated**: 2025-10-18
**Version**: 1.4
