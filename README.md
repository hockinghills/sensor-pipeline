# Raspberry Pi Sensor Data Pipeline

A complete IoT sensor data pipeline using Podman quadlets for containerized services.

## Architecture

```
ESP32 → MQTT → HiveMQ Edge → Telegraf → InfluxDB v2.7 → Grafana Cloud
BME680 Sensor → Telegraf/Vector → InfluxDB v2.7 → Grafana Cloud
```

## Equipment Being Monitored

### Glass Furnace
This pipeline monitors a **150 lb free-standing recuperated pot furnace** designed and built by Charles Correll. The furnace is used for **Lyon's Pyre Glasswerks**, Michael's art glass business, located in his garage.

**Operating Parameters:**
- **Normal operating temperature**: ~2320°F (glass melting temperature)
- **Idle/maintenance temperature**: ~1900°F (standby mode)
- **Fuel**: Natural gas with recuperative burner system
- **Safety-critical**: High-frequency monitoring (100ms) for temperature and flame detection

**Monitored Parameters:**
- **Furnace temperature**: Thermocouple measurement with cold junction compensation
- **Flame sensor**: Monitors burner operation and flame presence
- **Gas pressure**: Inlet and outlet pressure monitoring (PSI)
- **ESP32 health**: Free heap memory to detect device issues

### Grafana Cloud Alerting
**Active alerts configured for safety monitoring:**
- **Temperature alerts**: High/low temperature threshold violations
- **Data flow alerts**: Missing data (connectivity or hardware failure)
- **Flame sensor alerts**: Burner operation problems
- **Alert recipients**: louthenw (active), Michael (to be added)

These alerts provide critical safety monitoring for the glass furnace operation.

## Components

### 1. HiveMQ Edge MQTT Broker
- **Port**: 1883 (MQTT), 8080 (Web UI)
- **Data**: Persisted in `data/hivemq/`
- **Purpose**: Receives MQTT messages from ESP32 sensors
- **Startup time**: ~90 seconds to fully initialize

### 2. InfluxDB v2.7
- **Port**: 8086
- **Data**: Persisted in `data/influxdb/`
- **Purpose**: Time-series database for sensor data
- **Organization**: empyrean
- **Bucket**: fucked

### 3. Telegraf
- **Purpose**: Data collection agent
- **Inputs**:
  - MQTT consumer (from HiveMQ)
  - BME680 environmental sensor via I2C (0x77)
- **Output**: InfluxDB v2.7
- **Startup**: Waits for HiveMQ MQTT port to be available before starting

### 4. Vector (Replacing Telegraf)
- **Purpose**: High-performance data pipeline (testing/migration phase)
- **Inputs**:
  - ESP32 pressure sensors via serial USB
  - BME680 environmental sensor via sysfs
- **Output**: InfluxDB v2.7
- **Config**: `configs/vector.toml`
- **Status**: Running in parallel with Telegraf, will fully replace it

## I2C Sensor Setup

### BME680 Environmental Sensor
The BME680 connects via I2C and provides:
- Temperature
- Humidity
- Pressure

**Note**: Gas resistance (air quality) measurement is not enabled to maximize sensor reading speed. The gas sensor heater adds significant delay to readings.

**I2C Address**: 0x77
**IIO Device**: `/sys/bus/i2c/devices/1-0077/iio:device0`

#### Automatic Initialization at Boot

The BME680 sensor is automatically initialized at boot using systemd services:

1. **Kernel Modules**: `/etc/modules-load.d/bme680.conf` loads `bme680_core` and `bme680_i2c` drivers
2. **Device Registration**: `bme680-setup.service` automatically registers the sensor on the I2C bus at address 0x77

The sensor will be fully operational immediately after boot without manual intervention.

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
systemctl --user start hivemq.service influxdb.service telegraf.service vector.service
```

### 6. Enable Auto-start
Note: All services are managed by Podman quadlets and start automatically on user login.

### 7. Install BME680 Boot Configuration (Optional but Recommended)
For automatic BME680 sensor initialization at boot:
```bash
# Copy systemd service
sudo cp system-config/bme680-setup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bme680-setup.service

# Copy modules auto-load config
sudo cp system-config/bme680.conf /etc/modules-load.d/

# Start the service now (or it will run on next boot)
sudo systemctl start bme680-setup.service
```

## Configuration

### Telegraf Configuration
Located in `configs/telegraf.conf`:
- **MQTT Input**: Subscribes to `furnace/data` topic at 100ms interval from `tcp://127.0.0.1:1883`
- **BME680 Input**: Reads from `/sys/bus/i2c/devices/1-0077/iio:device0` at 1000ms interval
- **Output**: InfluxDB v2.7 at `http://127.0.0.1:8086`
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
systemctl --user status hivemq.service influxdb.service telegraf.service vector.service
```

### Logs
```bash
journalctl --user -u hivemq.service -f
journalctl --user -u influxdb.service -f
journalctl --user -u telegraf.service -f
journalctl --user -u vector.service -f
```

### Container Status
```bash
podman ps
podman logs hivemq
podman logs influxdb2
podman logs telegraf
podman logs vector
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
The BME680 sensor initializes automatically at boot via systemd services. If you need to manually trigger initialization (for testing or troubleshooting):

```bash
# Load kernel modules
sudo modprobe bme680_core bme680_i2c

# Register device on I2C bus
echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device

# Verify
ls /sys/bus/i2c/devices/1-0077/iio:device*/
```

To check the automatic boot service status:
```bash
sudo systemctl status bme680-setup.service
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
netstat -tln | grep -E "1883|8080|8086"
```

## Data Flow

1. **ESP32 Sensors** → Send JSON data via MQTT to topic `furnace/data`
2. **BME680 Sensor** → Exposes data via I2C interface
3. **HiveMQ Edge** → Receives MQTT messages on port 1883
4. **Telegraf** →
   - Subscribes to MQTT topics from HiveMQ
   - Reads BME680 data from I2C
   - Sends all data to InfluxDB
5. **InfluxDB v2.7** → Stores time-series data
6. **Grafana Cloud** → Visualizes data remotely with alerting

## File Structure

```
sensor-pipeline/
├── README.md
├── quadlets/
│   ├── hivemq.container      # HiveMQ Edge quadlet
│   ├── influxdb.container    # InfluxDB v2.7 quadlet
│   ├── telegraf.container    # Telegraf quadlet
│   └── vector.container      # Vector quadlet
├── configs/
│   ├── telegraf.conf         # Telegraf configuration
│   └── vector.toml           # Vector configuration
├── system-config/
│   ├── bme680-setup.service  # BME680 systemd service
│   └── bme680.conf           # BME680 modules auto-load config
├── data/
│   ├── hivemq/               # HiveMQ persistence
│   ├── influxdb/             # InfluxDB data
│   └── telegraf/             # Telegraf logs (if needed)
└── scripts/
    ├── health-check.sh       # Comprehensive pipeline health check
    ├── backup.sh             # Backup script
    └── setup-bme680.sh       # BME680 setup script
```

## Network Configuration

- **Pi IP**: 192.168.50.224
- **MQTT Port**: 1883
- **HiveMQ Web UI**: http://192.168.50.224:8080
- **InfluxDB API**: http://192.168.50.224:8086

## Dependencies

- Podman with quadlet support
- systemd user services enabled
- I2C kernel modules for BME680 (`bme680_core`, `bme680_i2c`)
- systemd system service for BME680 auto-initialization (`bme680-setup.service`)
- Bash built-in `/dev/tcp/` for port checking (no external dependencies)
- Network connectivity for container pulls
- Tailscale for Grafana Cloud connectivity
- `jq` for JSON parsing (used by health check script)

## Backup

Important directories to backup:
- `data/influxdb/` - All sensor data
- `data/hivemq/` - MQTT broker state
- `configs/telegraf.conf` - Telegraf configuration
- `configs/vector.toml` - Vector configuration

## Recovery

In case of issues:
1. Stop all services: `systemctl --user stop hivemq.service influxdb.service telegraf.service vector.service`
2. Check service status and logs
3. Verify container images: `podman images`
4. Restart services: `systemctl --user start hivemq.service influxdb.service telegraf.service vector.service`

---

## Pipeline Verification

### Automated Health Check Script

The easiest way to verify the entire pipeline is with the health check script:

```bash
~/sensor-pipeline/scripts/health-check.sh
```

This comprehensive script checks:
1. **Systemd Services** - All services running (HiveMQ, InfluxDB, Telegraf, Vector)
2. **Container Status** - All containers up with uptime
3. **ESP32 MQTT Data Flow** - Live furnace sensor data
4. **BME680 Environmental Sensor** - Temperature, pressure, humidity readings
5. **Telegraf/Vector Status** - Data pipeline health and error detection
6. **Network Ports** - MQTT (1883), HiveMQ Web UI (8080), InfluxDB (8086)
7. **Tailscale Network** - Grafana Cloud peer connectivity

**Example output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IoT Sensor Pipeline Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1] Systemd Services
  ✓ hivemq.service - running
  ✓ influxdb.service - running
  ✓ telegraf.service - running
  ✓ vector.service - running

[7] Tailscale Network
  ✓ Tailscale connected
  ✓ Grafana Cloud peers: 10/10 online

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Overall Status: HEALTHY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

The script returns exit code 0 if healthy, 1 if issues detected (useful for automation).

---

### Manual Health Check Steps

Use this process to verify the data pipeline is functioning correctly. Run BEFORE and AFTER making changes to ensure nothing broke.

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
1. Run health check: `~/sensor-pipeline/scripts/health-check.sh`
2. Check service status: `systemctl --user status hivemq.service telegraf.service influxdb.service vector.service`
3. Verify config syntax: Check `configs/telegraf.conf` and `configs/vector.toml` for typos
4. Check Grafana Cloud: Is data still appearing in dashboards?
5. Restart services: `systemctl --user restart telegraf.service` or `systemctl --user restart vector.service`

---

## Recent Updates (2025-10-18)

### Reboot Resilience Fixes
Fixed critical issues preventing graceful reboot recovery:

1. **Removed `nc` dependency** - Replaced with bash built-in `/dev/tcp/` for MQTT port checking
   - File: `telegraf.container` line 14
   - Old: `nc -z 127.0.0.1 1883`
   - New: `timeout 1 bash -c "</dev/tcp/127.0.0.1/1883"`

2. **Fixed BME680 kernel module loading** - Added `bme680_core` dependency
   - File: `telegraf.container` line 15-16
   - Now loads both `bme680_core` and `bme680_i2c` in correct order

3. **Fixed I2C symlink path** - Changed to absolute path for reliability
   - File: `telegraf.container` line 17
   - Old: `ln -sf ../iio:device0`
   - New: `ln -sf /sys/bus/i2c/devices/1-0077/iio:device0`

4. **Added HiveMQ Web UI port** - Web interface now accessible
   - File: `hivemq.container` line 10
   - Added: `PublishPort=8080:8080`

### New Health Check Script
Added comprehensive monitoring script at `scripts/health-check.sh`:
- Checks all services, containers, sensors, and network connectivity
- Validates Tailscale and Grafana Cloud peer status
- Shows live sensor readings
- Color-coded output with ✓/✗ indicators
- Exit codes for automation (0=healthy, 1=issues)

**Pipeline now survives reboots without intervention!**

---

## Recent Updates (2025-10-24)

### BME680 Automatic Boot Configuration
Implemented persistent boot configuration for the BME680 environmental sensor:

1. **Module Auto-loading** - Created `/etc/modules-load.d/bme680.conf`
   - Automatically loads `bme680_core` and `bme680_i2c` kernel modules at boot
   - Eliminates need for manual module loading after reboot

2. **Systemd Service** - Created `bme680-setup.service`
   - Automatically registers BME680 device on I2C bus at startup
   - Service file: `/etc/systemd/system/bme680-setup.service`
   - Runs before telegraf.service to ensure sensor is available
   - Includes cleanup on service stop

3. **Performance Optimization** - Gas sensor disabled
   - Telegraf only reads temperature, pressure, and humidity
   - Gas resistance measurement skipped to maximize reading speed
   - Eliminates heater activation delay for faster sampling

**The BME680 sensor now initializes automatically on every boot with no manual intervention required.**

---

## Recent Updates (2025-11-20)

### Vector Data Pipeline
Deployed Vector as high-performance replacement for Telegraf:

1. **Vector Container** - Added `vector.container` quadlet
   - Uses timberio/vector:latest-alpine image
   - Configuration in `configs/vector.toml`
   - Running in parallel with Telegraf during migration

2. **Inputs Configured**:
   - ESP32 pressure sensors via serial USB (`/dev/ttyACM0`)
   - BME680 environmental sensor via sysfs reads

3. **Benefits over Telegraf**:
   - Better handling of slow sensor reads
   - More flexible data transformation (VRL language)
   - Pre-deployment config validation
   - Lower resource usage

4. **Migration Plan**: Vector will fully replace Telegraf once testing is complete

---

---

## Telegraf Failure Log

| Date | Time | Reason |
|------|------|--------|
| 2025-11-14 | 22:00 | MQTT connection reset by peer |
| 2025-11-15 | 01:06 | MQTT connection reset by peer |

---

**Created**: 2025-09-19
**Last Updated**: 2025-11-20
**Version**: 1.9
