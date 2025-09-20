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
  - BME680 sensor via I2C
- **Output**: InfluxDB v3

## BME680 Sensor Setup

The BME680 environmental sensor connects via I2C and provides:
- Temperature
- Humidity
- Pressure
- Air quality (gas resistance)

**I2C Address**: 0x77

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
- **MQTT Input**: Subscribes to `furnace/data` topic
- **BME680 Input**: Reads from `/sys/bus/i2c/devices/1-0077/iio:device0`
- **Output**: InfluxDB v3 at `http://192.168.50.224:8181`
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

### BME680 Sensor Issues
```bash
# Check if module is loaded
lsmod | grep bme680

# Check I2C device
ls /sys/bus/i2c/devices/1-0077/iio:device0/

# Manual module load
sudo modprobe bme680_i2c
echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device
```

### Port Conflicts
If services fail to start, check for port conflicts:
```bash
netstat -tln | grep -E "1883|8080|8181"
```

Common conflicts:
- Native `influxdb3.service` taking port 8181
- Manual containers taking ports

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
**Last Updated**: 2025-09-19
**Version**: 1.0