# IoT Sensor Pipeline - Complete Setup Guide

This repository contains the complete configuration for a robust IoT sensor data pipeline running on Raspberry Pi.

## Architecture Overview

```
ESP32 (Furnace Sensors) → MQTT → HiveMQ Edge → Telegraf → InfluxDB v3 → Grafana Cloud
BME680 (I2C Sensor) ----→        ↗
```

## Services Stack

- **HiveMQ Edge**: MQTT broker (port 1883)
- **InfluxDB v3**: Time series database (port 8181)
- **Telegraf**: Data collection agent
- **BME680**: Temperature/pressure/humidity sensor via I2C

## Quick Start

### 1. Copy Quadlet Files
```bash
cp quadlets/*.container ~/.config/containers/systemd/
```

### 2. Copy Configuration Files
```bash
mkdir -p ~/sensor-pipeline/configs
cp configs/telegraf.conf ~/sensor-pipeline/configs/
```

### 3. Set up InfluxDB Data Directories
```bash
mkdir -p ~/.influxdb3 ~/.influxdb3-plugins/.venv/bin
chmod 777 ~/.influxdb3 ~/.influxdb3-plugins
touch ~/.influxdb3-plugins/.venv/bin/activate
```

### 4. Initialize BME680 Sensor
```bash
sudo modprobe bme680_i2c
echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device
```

### 5. Start Services
```bash
systemctl --user daemon-reload
systemctl --user enable --now hivemq.service influxdb.service telegraf.service
```

### 6. Create InfluxDB Database and Token
```bash
# Wait for InfluxDB to start, then:
podman exec influxdb3 influxdb3 create token --admin
# Copy the token output (watch for line breaks!)

podman exec influxdb3 influxdb3 create database --token "YOUR_TOKEN" fucked
```

### 7. Update Telegraf Configuration
Edit `~/sensor-pipeline/configs/telegraf.conf` and replace the token with your new one.

```bash
systemctl --user restart telegraf.service
```

## Service Configurations

### HiveMQ Edge (MQTT Broker)
- **Container**: `hivemq.container`
- **Port**: 1883
- **Network**: Host mode

### InfluxDB v3
- **Container**: `influxdb.container`
- **Port**: 8181 (all interfaces for Tailscale access)
- **Data**: `~/.influxdb3`
- **Plugins**: `~/.influxdb3-plugins` (required for Python environment)
- **User**: 1000:1000 (matches host user)

### Telegraf
- **Container**: `telegraf.container`
- **Config**: `~/sensor-pipeline/configs/telegraf.conf`
- **Inputs**: MQTT (furnace data), multifile (BME680 sensor)
- **Output**: InfluxDB v3
- **Privileges**: Required for I2C access

## Troubleshooting

### InfluxDB Won't Start
**Symptoms**: "Failed to put initial table index conversion marker to object store"

**Solutions**:
1. Check data directory permissions: `chmod 777 ~/.influxdb3`
2. Ensure plugins directory exists: `mkdir -p ~/.influxdb3-plugins/.venv/bin && touch ~/.influxdb3-plugins/.venv/bin/activate`
3. Verify user mapping in quadlet: `User=1000:1000`

### BME680 Sensor Not Found
**Symptoms**: "no such file or directory" for sensor files

**Solutions**:
1. Load kernel module: `sudo modprobe bme680_i2c`
2. Bind device: `echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device`
3. Verify device appears: `ls /sys/bus/i2c/devices/1-0077/iio:device0/`

### Grafana Cloud Authentication Issues
**Symptoms**: "Unauthenticated" errors

**Solutions**:
1. **Check token for line breaks** - Most common issue! Copy token to text editor and ensure it's on one line
2. Verify InfluxDB is listening on all interfaces (not just localhost)
3. Use correct database name: `fucked`

### MQTT Connection Issues
**Symptoms**: "EOF" errors in Telegraf

**Solutions**:
1. Verify HiveMQ is running: `systemctl --user status hivemq.service`
2. Check network connectivity: `mosquitto_pub -h localhost -t test -m hello`

### Port Conflicts
**Symptoms**: Services fail to start with bind errors

**Solutions**:
1. Check for old processes: `sudo netstat -tlpn | grep PORT`
2. Kill old binaries before starting containers

## Data Sources

### MQTT Topics
- `furnace/data`: JSON payload with temp, cstemp, flame, pressure, heap

### I2C Sensors
- BME680 at address 0x77: temperature, pressure, humidity
- Files: `/sys/bus/i2c/devices/1-0077/iio:device0/in_*_input`

## Backup/Restore

### Backup Current Configuration
```bash
# Copy this entire directory to backup location
tar -czf sensor-pipeline-backup-$(date +%Y%m%d).tar.gz ~/sensor-pipeline-backup/
```

### Restore from Backup
```bash
# Extract and run quick start steps above
tar -xzf sensor-pipeline-backup-*.tar.gz
```

## Security Notes

- InfluxDB is exposed on all interfaces for Tailscale access
- Default database name is intentionally unusual for security through obscurity
- Token should be rotated periodically
- Consider firewall rules for production deployments

## Monitoring

### Check Service Status
```bash
systemctl --user status hivemq.service influxdb.service telegraf.service
```

### View Live Data
```bash
# MQTT messages
mosquitto_sub -h localhost -t "furnace/data"

# InfluxDB data
podman exec influxdb3 influxdb3 query --token "YOUR_TOKEN" --database fucked "SELECT * FROM furnace ORDER BY time DESC LIMIT 5"
```

### Common Log Locations
```bash
journalctl --user -u hivemq.service
journalctl --user -u influxdb.service
journalctl --user -u telegraf.service
```

## License

Internal use only.

---

**Last Updated**: 2025-09-21
**Tested On**: Raspberry Pi 4, Raspberry Pi OS Bookworm
**Container Runtime**: Podman with systemd quadlets