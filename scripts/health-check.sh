#!/bin/bash

# IoT Pipeline Health Check Script
# Architecture: ESP32 (UDP) → Vector → VictoriaMetrics → Grafana Cloud

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
echo -e "${BLUE}  ESP32 → UDP → Vector → VictoriaMetrics → Grafana Cloud${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Track overall health
ALL_HEALTHY=true

# 1. Check systemd services
echo -e "${BLUE}[1] Systemd Services${NC}"
for service in vector victoriametrics; do
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
for container in vector victoriametrics; do
    if podman ps --format "{{.Names}}" | grep -q "^${container}$"; then
        uptime=$(podman ps --filter "name=^${container}$" --format "{{.Status}}")
        echo -e "  ${GREEN}${CHECK}${NC} ${container} - ${uptime}"
    else
        echo -e "  ${RED}${CROSS}${NC} ${container} - ${RED}NOT RUNNING${NC}"
        ALL_HEALTHY=false
    fi
done
echo ""

# 3. Check Vector health & component throughput
echo -e "${BLUE}[3] Vector Pipeline${NC}"

# Vector API health
VECTOR_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8686/health 2>/dev/null)
if [ "$VECTOR_HEALTH" = "200" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} Vector API healthy"
else
    echo -e "  ${RED}${CROSS}${NC} Vector API not responding (port 8686)"
    ALL_HEALTHY=false
fi

# Use vector tap to check each data source (2s sample)
echo -e "  ${BLUE}  Sampling live data (2s)...${NC}"

# Furnace UDP (port 9001)
FURNACE_TAP=$(podman exec vector vector tap --quiet --duration-ms 2000 --limit 1 --outputs-of furnace_udp 2>/dev/null | grep -v "INFO")
if [ -n "$FURNACE_TAP" ]; then
    FURNACE_TEMP=$(echo "$FURNACE_TAP" | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        msg = d.get('message', '')
        if 'furnace_temp' in str(d) or 'furnace_temp' in msg:
            # Try parsing the message field if it's JSON
            try:
                inner = json.loads(msg)
                print(f\"{inner.get('furnace_temp', 'N/A')}\")
            except:
                print(f\"{d.get('furnace_temp', 'N/A')}\")
            break
    except: pass
" 2>/dev/null)
    if [ -n "$FURNACE_TEMP" ] && [ "$FURNACE_TEMP" != "N/A" ]; then
        FURNACE_F=$(python3 -c "print(f'{float($FURNACE_TEMP) * 9/5 + 32:.0f}')" 2>/dev/null)
        echo -e "  ${GREEN}${CHECK}${NC} Furnace UDP (port 9001) - receiving data"
        echo -e "      Furnace temp: ${FURNACE_TEMP}°C (${FURNACE_F}°F)"
    else
        echo -e "  ${GREEN}${CHECK}${NC} Furnace UDP (port 9001) - receiving data"
    fi
else
    echo -e "  ${RED}${CROSS}${NC} Furnace UDP (port 9001) - ${RED}NO DATA${NC}"
    echo -e "  ${YELLOW}  Check if ESP32 is powered on and connected to WiFi${NC}"
    ALL_HEALTHY=false
fi

# ESP32-S3 UDP (port 9000)
ESP32S3_TAP=$(podman exec vector vector tap --quiet --duration-ms 2000 --limit 1 --outputs-of esp32s3_udp 2>/dev/null | grep -v "INFO")
if [ -n "$ESP32S3_TAP" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} ESP32-S3 UDP (port 9000) - receiving data"
else
    echo -e "  ${YELLOW}${WARN}${NC} ESP32-S3 UDP (port 9000) - no data in sample window"
fi

# BME680 exec source
BME680_TAP=$(podman exec vector vector tap --quiet --duration-ms 2000 --limit 1 --outputs-of bme680 2>/dev/null | grep -v "INFO")
BME680_ERRORS=$(podman exec vector vector tap --quiet --duration-ms 2000 --limit 5 --inputs-of parse_bme680 2>/dev/null | grep -v "INFO" | grep "stderr" 2>/dev/null)
if [ -n "$BME680_TAP" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} BME680 (sysfs exec) - receiving data"
    if [ -n "$BME680_ERRORS" ]; then
        echo -e "  ${YELLOW}${WARN}${NC} BME680 has read errors (some sysfs files may be missing)"
    fi
else
    echo -e "  ${RED}${CROSS}${NC} BME680 (sysfs exec) - ${RED}NO DATA${NC}"
    echo -e "  ${YELLOW}  Kernel modules may need loading: sudo modprobe bme680_core bme680_i2c${NC}"
    ALL_HEALTHY=false
fi
echo ""

# 4. Check VictoriaMetrics data flow
echo -e "${BLUE}[4] VictoriaMetrics Data Flow${NC}"

VM_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8428/health 2>/dev/null)
if [ "$VM_HEALTH" = "200" ]; then
    echo -e "  ${GREEN}${CHECK}${NC} VictoriaMetrics API healthy (port 8428)"
else
    echo -e "  ${RED}${CROSS}${NC} VictoriaMetrics API not responding (port 8428)"
    ALL_HEALTHY=false
fi

# Check each measurement for recent data (last 2 minutes)
MEASUREMENTS=("furnace_temp:Furnace temperature" "flame_rms:Flame sensor" "pressure_sensor1_psi:Pressure sensor" "recuperator_preheat:Recuperator" "control_voltage:Burner control")

for entry in "${MEASUREMENTS[@]}"; do
    metric="${entry%%:*}"
    label="${entry#*:}"

    result=$(curl -s "http://127.0.0.1:8428/api/v1/query?query=${metric}" 2>/dev/null)
    value=$(echo "$result" | python3 -c "
import sys, json, time
try:
    d = json.load(sys.stdin)
    results = d.get('data', {}).get('result', [])
    if results:
        ts = float(results[0]['value'][0])
        val = results[0]['value'][1]
        age = time.time() - ts
        if age < 120:
            print(f'OK|{val}|{age:.0f}')
        else:
            print(f'STALE|{val}|{age:.0f}')
    else:
        print('EMPTY||')
except:
    print('ERROR||')
" 2>/dev/null)

    status="${value%%|*}"
    rest="${value#*|}"
    val="${rest%%|*}"
    age="${rest#*|}"

    case "$status" in
        OK)
            echo -e "  ${GREEN}${CHECK}${NC} ${label} - ${val} (${age}s ago)"
            ;;
        STALE)
            echo -e "  ${YELLOW}${WARN}${NC} ${label} - STALE data (${age}s ago, value: ${val})"
            ALL_HEALTHY=false
            ;;
        EMPTY)
            echo -e "  ${RED}${CROSS}${NC} ${label} - ${RED}NO DATA${NC}"
            ALL_HEALTHY=false
            ;;
        *)
            echo -e "  ${RED}${CROSS}${NC} ${label} - ${RED}QUERY ERROR${NC}"
            ALL_HEALTHY=false
            ;;
    esac
done
echo ""

# 5. Network Ports
echo -e "${BLUE}[5] Network Ports${NC}"
for port_info in "9000:ESP32-S3 UDP" "9001:Furnace UDP" "8428:VictoriaMetrics API" "8686:Vector API"; do
    port="${port_info%%:*}"
    service="${port_info#*:}"

    # For UDP ports, check with ss; for TCP, check with /dev/tcp
    if [[ "$service" == *"UDP"* ]]; then
        if ss -uln 2>/dev/null | grep -q ":${port} "; then
            echo -e "  ${GREEN}${CHECK}${NC} Port ${port} (${service}) - listening"
        else
            echo -e "  ${RED}${CROSS}${NC} Port ${port} (${service}) - ${RED}NOT LISTENING${NC}"
            ALL_HEALTHY=false
        fi
    else
        if timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null; then
            echo -e "  ${GREEN}${CHECK}${NC} Port ${port} (${service}) - listening"
        else
            echo -e "  ${RED}${CROSS}${NC} Port ${port} (${service}) - ${RED}NOT ACCESSIBLE${NC}"
            ALL_HEALTHY=false
        fi
    fi
done
echo ""

# 6. Tailscale Network
echo -e "${BLUE}[6] Tailscale Network${NC}"

if ! command -v tailscale &> /dev/null; then
    echo -e "  ${RED}${CROSS}${NC} Tailscale - ${RED}NOT INSTALLED${NC}"
    ALL_HEALTHY=false
elif ! tailscale status &> /dev/null; then
    echo -e "  ${RED}${CROSS}${NC} Tailscale - ${RED}NOT RUNNING${NC}"
    echo -e "  ${YELLOW}  Start with: sudo systemctl start tailscaled${NC}"
    ALL_HEALTHY=false
else
    TS_STATUS=$(tailscale status --json 2>/dev/null)
    if [ $? -eq 0 ]; then
        GRAFANA_PEERS=$(echo "$TS_STATUS" | jq -r '.Peer[] | select(.HostName | contains("grafanacloud")) | "\(.HostName):\(.Online)"' 2>/dev/null)

        if [ -n "$GRAFANA_PEERS" ]; then
            GRAFANA_ONLINE=$(echo "$GRAFANA_PEERS" | grep -c "true")
            GRAFANA_TOTAL=$(echo "$GRAFANA_PEERS" | wc -l)

            if [ "$GRAFANA_ONLINE" -gt 0 ]; then
                echo -e "  ${GREEN}${CHECK}${NC} Tailscale connected"
                echo -e "  ${GREEN}${CHECK}${NC} Grafana Cloud peers: ${GRAFANA_ONLINE}/${GRAFANA_TOTAL} online"
            else
                echo -e "  ${YELLOW}${WARN}${NC} Tailscale connected but no Grafana Cloud peers online"
                echo -e "  ${YELLOW}  Grafana dashboards may not be accessible${NC}"
            fi
        else
            echo -e "  ${GREEN}${CHECK}${NC} Tailscale connected"
            echo -e "  ${YELLOW}${WARN}${NC} No Grafana Cloud peers found"
        fi

        TS_IP=$(echo "$TS_STATUS" | jq -r '.Self.TailscaleIPs[0]' 2>/dev/null)
        if [ -n "$TS_IP" ] && [ "$TS_IP" != "null" ]; then
            echo -e "  ${BLUE}  This device (piiot): ${TS_IP}${NC}"
        fi
    else
        echo -e "  ${YELLOW}${WARN}${NC} Tailscale running but status unknown"
    fi
fi
echo ""

# 7. Legacy services (should be stopped/removed)
echo -e "${BLUE}[7] Legacy Services (should be removed)${NC}"
LEGACY_FOUND=false
for service in hivemq telegraf influxdb; do
    if systemctl --user is-active --quiet ${service}.service 2>/dev/null; then
        echo -e "  ${YELLOW}${WARN}${NC} ${service}.service is still running — no longer needed"
        LEGACY_FOUND=true
    fi
done
for container in hivemq telegraf influxdb2; do
    if podman ps --format "{{.Names}}" 2>/dev/null | grep -q "^${container}$"; then
        echo -e "  ${YELLOW}${WARN}${NC} ${container} container still running — no longer needed"
        LEGACY_FOUND=true
    fi
done
if [ "$LEGACY_FOUND" = false ]; then
    echo -e "  ${GREEN}${CHECK}${NC} No legacy services running"
fi
echo ""

# Overall status
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
    echo -e "  • Service logs: journalctl --user -u <service>.service"
    echo -e "  • Container logs: podman logs <container>"
    echo -e "  • Live data: podman exec vector vector tap --quiet --duration-ms 5000"
    echo -e "  • Component metrics: podman exec vector vector top"
    echo -e "  • Restart: systemctl --user restart vector.service"
    exit 1
fi
