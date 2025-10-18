# ESPHome Configuration

This directory contains ESPHome device configurations.

## Files

- `secrets.yaml` - Credentials and sensitive data (edit this first!)
- `piiot-local.yaml` - Pi host configuration with BME680 I2C sensor
- `furnace-esp32.yaml` - Example ESP32 configuration with direct InfluxDB writes
- `README.md` - This file

## Getting Started

1. **Edit `secrets.yaml`** with your actual credentials:
   - WiFi SSID and password
   - OTA password
   - InfluxDB connection details (already populated)

2. **Access ESPHome Dashboard:**
   ```
   http://piiot:6052
   or
   http://100.70.106.23:6052 (via Tailscale)
   ```

3. **Add/Edit Device Configurations:**
   - Create `.yaml` files for each ESP device
   - Use `furnace-esp32.yaml` as a template

4. **Compile and Upload:**
   - Use the dashboard to compile firmware
   - First upload via USB (for ESP devices)
   - Subsequent updates via OTA
   - Pi host config runs directly on the Pi

## InfluxDB Direct Write

All configs use ESPHome's `http_request` component to POST data directly to InfluxDB v3, eliminating the need for MQTT and Telegraf.

### Line Protocol Format

```
measurement,tag=value field=value
```

Example:
```
furnace,host=furnace-esp32 temp=72.5,humidity=45.2
```

## Network & Permissions

- **Network:** ESPHome uses `host` networking mode to discover devices via mDNS
- **Privileged:** Container runs with `--privileged` for I2C/GPIO access on Pi
- **Ports:**
  - 6052: ESPHome Dashboard
  - 3232: OTA updates (per device)
