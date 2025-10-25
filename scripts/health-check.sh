#!/bin/bash

# IoT Pipeline Health Check Script
# Verifies all components of the sensor data pipeline

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Unicode symbols
CHECK="✓"
CROSS="✗"
WARN="⚠"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  IoT Sensor Pipeline Health Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Track overall health
ALL_HEALTHY=true

# 1. Check systemd services
echo -e "${BLUE}[1] Systemd Services${NC}"
for service in hivemq influxdb telegraf; do
    if systemctl --user is-active --quiet ${service}.service; then
        echo -e "  ${GREEN}${CHECK}${NC} ${service}.service - running"
    else
        echo -e "  ${RED}${CROSS}${NC} ${service}.service - ${RED}FAILED${NC}"
        ALL_HEALTHY=false
    fi
done
echo ""

# 2. Check container status
echo -e "${BLUE}[2] Container Status${NC}"
for container in hivemq influxdb2 telegraf; do
    if podman ps --format "{{.Names}}" | grep -q "^${container}$"; then
        uptime=$(podman ps --filter "name=${container}" --format "{{.Status}}")
        echo -e "  ${GREEN}${CHECK}${NC} ${container} - ${uptime}"
    else
        echo -e "  ${RED}${CROSS}${NC} ${container} - ${RED}NOT RUNNING${NC}"
        ALL_HEALTHY=false
    fi
done
echo ""

# 3. Check ESP32 MQTT data
echo -e "${BLUE}[3] ESP32 MQTT Data Flow${NC}"
MQTT_DATA=$(timeout 3 mosquitto_sub -h 127.0.0.1 -t 'furnace/data' -C 1 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$MQTT_DATA" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} ESP32 publishing to 'furnace/data'"
    echo -e "  ${BLUE}  Latest data:${NC}"

    # Parse and display JSON fields nicely
    temp=$(echo "$MQTT_DATA" | jq -r '.temp // "N/A"' 2>/dev/null)
    cjtemp=$(echo "$MQTT_DATA" | jq -r '.cjtemp // "N/A"' 2>/dev/null)
    flame=$(echo "$MQTT_DATA" | jq -r '.flame // "N/A"' 2>/dev/null)
    pressure_in=$(echo "$MQTT_DATA" | jq -r '.pressure_inlet // "N/A"' 2>/dev/null)
    pressure_out=$(echo "$MQTT_DATA" | jq -r '.pressure_outlet // "N/A"' 2>/dev/null)
    heap=$(echo "$MQTT_DATA" | jq -r '.heap // "N/A"' 2>/dev/null)

    if [ "$temp" != "N/A" ]; then
        echo -e "    • Furnace temp: ${temp}°F"
        echo -e "    • Cold junction: ${cjtemp}°C"
        echo -e "    • Flame sensor: ${flame}V"
        echo -e "    • Pressure (in/out): ${pressure_in}/${pressure_out} PSI"
        echo -e "    • Free heap: ${heap} bytes"
    else
        echo "$MQTT_DATA"
    fi
else
    echo -e "  ${RED}${CROSS}${NC} ESP32 MQTT data - ${RED}NO DATA${NC}"
    echo -e "  ${YELLOW}  Check if ESP32 is powered on and connected to WiFi${NC}"
    ALL_HEALTHY=false
fi
echo ""

# 4. Check BME680 sensor
echo -e "${BLUE}[4] BME680 Environmental Sensor${NC}"
BME_PATH="/sys/bus/i2c/devices/1-0077/iio:device0"
if [ -d "$BME_PATH" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} BME680 sensor detected on I2C"

    # Read sensor values
    if [ -r "$BME_PATH/in_temp_input" ]; then
        temp_raw=$(cat "$BME_PATH/in_temp_input" 2>/dev/null)
        temp_c=$(awk "BEGIN {printf \"%.2f\", $temp_raw/1000}")

        pressure_raw=$(cat "$BME_PATH/in_pressure_input" 2>/dev/null)

        humidity_raw=$(cat "$BME_PATH/in_humidityrelative_input" 2>/dev/null)

        echo -e "  ${BLUE}  Current readings:${NC}"
        echo -e "    • Temperature: ${temp_c}°C"
        echo -e "    • Pressure: ${pressure_raw} kPa"
        echo -e "    • Humidity: ${humidity_raw}%"
    else
        echo -e "  ${YELLOW}${WARN}${NC} BME680 detected but not readable"
        ALL_HEALTHY=false
    fi
else
    echo -e "  ${RED}${CROSS}${NC} BME680 sensor - ${RED}NOT DETECTED${NC}"
    echo -e "  ${YELLOW}  Run: sudo modprobe bme680_core && sudo modprobe bme680_i2c${NC}"
    echo -e "  ${YELLOW}  Then: echo 'bme680 0x77' | sudo tee /sys/bus/i2c/devices/i2c-1/new_device${NC}"
    ALL_HEALTHY=false
fi
echo ""

# 5. Check Telegraf logs for errors
echo -e "${BLUE}[5] Telegraf Status${NC}"
TELEGRAF_ERRORS=$(podman logs --tail 50 telegraf 2>&1 | grep -c "E!")
TELEGRAF_CONNECTED=$(podman logs --tail 20 telegraf 2>&1 | grep "Connected \[tcp://127.0.0.1:1883\]" | tail -1)

if [ -n "$TELEGRAF_CONNECTED" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} Telegraf connected to MQTT broker"
else
    echo -e "  ${YELLOW}${WARN}${NC} Telegraf MQTT connection status unknown"
fi

if [ "$TELEGRAF_ERRORS" -eq 0 ]; then
    echo -e "  ${GREEN}${CHECK}${NC} No recent errors in logs"
elif [ "$TELEGRAF_ERRORS" -lt 5 ]; then
    echo -e "  ${YELLOW}${WARN}${NC} ${TELEGRAF_ERRORS} error(s) in recent logs"
    echo -e "  ${YELLOW}  Run: podman logs telegraf | grep 'E!' | tail -5${NC}"
else
    echo -e "  ${RED}${CROSS}${NC} ${TELEGRAF_ERRORS} errors in recent logs"
    echo -e "  ${YELLOW}  Run: podman logs telegraf | grep 'E!' | tail -10${NC}"
    ALL_HEALTHY=false
fi
echo ""

# 6. Check port availability
echo -e "${BLUE}[6] Network Ports${NC}"
for port_info in "1883:HiveMQ MQTT" "8080:HiveMQ Web UI" "8086:InfluxDB API"; do
    port="${port_info%%:*}"
    service="${port_info#*:}"

    if timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        echo -e "  ${GREEN}${CHECK}${NC} Port ${port} (${service}) - listening"
    else
        echo -e "  ${RED}${CROSS}${NC} Port ${port} (${service}) - ${RED}NOT ACCESSIBLE${NC}"
        ALL_HEALTHY=false
    fi
done
echo ""

# 7. Check Tailscale connectivity
echo -e "${BLUE}[7] Tailscale Network${NC}"

# Check if tailscale is running
if ! command -v tailscale &> /dev/null; then
    echo -e "  ${RED}${CROSS}${NC} Tailscale - ${RED}NOT INSTALLED${NC}"
    ALL_HEALTHY=false
elif ! tailscale status &> /dev/null; then
    echo -e "  ${RED}${CROSS}${NC} Tailscale - ${RED}NOT RUNNING${NC}"
    echo -e "  ${YELLOW}  Start with: sudo systemctl start tailscaled${NC}"
    ALL_HEALTHY=false
else
    # Check if tailscale is connected
    TS_STATUS=$(tailscale status --json 2>/dev/null)
    if [ $? -eq 0 ]; then
        # Get Grafana Cloud connection status
        GRAFANA_PEERS=$(echo "$TS_STATUS" | jq -r '.Peer[] | select(.HostName | contains("grafanacloud")) | "\(.HostName):\(.Online)"' 2>/dev/null)

        if [ -n "$GRAFANA_PEERS" ]; then
            GRAFANA_ONLINE=$(echo "$GRAFANA_PEERS" | grep -c "true")
            GRAFANA_TOTAL=$(echo "$GRAFANA_PEERS" | wc -l)

            if [ "$GRAFANA_ONLINE" -gt 0 ]; then
                echo -e "  ${GREEN}${CHECK}${NC} Tailscale connected"
                echo -e "  ${GREEN}${CHECK}${NC} Grafana Cloud peers: ${GRAFANA_ONLINE}/${GRAFANA_TOTAL} online"

                # Show which Grafana instances are connected
                echo "$GRAFANA_PEERS" | while IFS=: read -r hostname status; do
                    if [ "$status" = "true" ]; then
                        echo -e "    • ${hostname} - ${GREEN}online${NC}"
                    else
                        echo -e "    • ${hostname} - ${YELLOW}offline${NC}"
                    fi
                done
            else
                echo -e "  ${YELLOW}${WARN}${NC} Tailscale connected but no Grafana Cloud peers online"
                echo -e "  ${YELLOW}  Grafana dashboards may not be accessible${NC}"
            fi
        else
            echo -e "  ${GREEN}${CHECK}${NC} Tailscale connected"
            echo -e "  ${YELLOW}${WARN}${NC} No Grafana Cloud peers found"
        fi

        # Get this device's tailscale IP
        TS_IP=$(echo "$TS_STATUS" | jq -r '.Self.TailscaleIPs[0]' 2>/dev/null)
        if [ -n "$TS_IP" ] && [ "$TS_IP" != "null" ]; then
            echo -e "  ${BLUE}  This device (piiot): ${TS_IP}${NC}"
        fi
    else
        echo -e "  ${YELLOW}${WARN}${NC} Tailscale running but status unknown"
    fi
fi
echo ""

# 8. Overall status
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}${CHECK} Overall Status: HEALTHY${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
else
    echo -e "${RED}${CROSS} Overall Status: ISSUES DETECTED${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo -e "  • Check service logs: journalctl --user -u <service>.service"
    echo -e "  • Check container logs: podman logs <container>"
    echo -e "  • Restart services: systemctl --user restart telegraf.service"
    exit 1
fi
