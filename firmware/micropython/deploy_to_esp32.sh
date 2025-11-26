#!/bin/bash
# Deploy furnace monitor to ESP32-S3

set -e  # Exit on error

DEVICE="${1:-/dev/ttyACM0}"

# Validate device exists
if [ ! -e "$DEVICE" ]; then
    echo "ERROR: Device $DEVICE not found"
    echo "Usage: $0 [device]"
    echo "Example: $0 /dev/ttyACM0"
    exit 1
fi

echo "=== Deploying Furnace Monitor to ESP32 ==="
echo "Device: $DEVICE"
echo ""

# Verify mpremote is installed
if ! command -v mpremote &> /dev/null; then
    echo "ERROR: mpremote not found. Install with: pip install mpremote"
    exit 1
fi

# Validate source files exist
for file in ads1115.py furnace_monitor.py main.py; do
    if [ ! -f "$file" ]; then
        echo "ERROR: $file not found in current directory"
        echo "Run this script from: firmware/micropython/"
        exit 1
    fi
done

# Check for config.py
if [ ! -f "config.py" ]; then
    echo "WARNING: config.py not found locally"
    echo ""
    echo "Checking if config.py exists on device..."
    if ! mpremote connect "$DEVICE" fs ls : | grep -q "config.py"; then
        echo ""
        echo "ERROR: config.py not found on device or locally"
        echo ""
        echo "Create config.py with your WiFi credentials and Vector server details:"
        echo "  WIFI_SSID = 'your_ssid'"
        echo "  WIFI_PASSWORD = 'your_password'"
        echo "  VECTOR_HOST = '192.168.50.224'"
        echo "  VECTOR_PORT = 9000"
        echo ""
        echo "Then either:"
        echo "  1. Place config.py in firmware/micropython/ and re-run this script"
        echo "  2. Manually copy it to the device: mpremote connect $DEVICE fs cp config.py :config.py"
        exit 1
    else
        echo "config.py found on device, continuing..."
    fi
else
    echo "Copying config.py (credentials)..."
    mpremote connect "$DEVICE" fs cp config.py :config.py
fi

echo "Copying ads1115.py driver..."
mpremote connect "$DEVICE" fs cp ads1115.py :ads1115.py

echo "Copying furnace_monitor.py..."
mpremote connect "$DEVICE" fs cp furnace_monitor.py :furnace_monitor.py

echo "Copying main.py (auto-run on boot)..."
mpremote connect "$DEVICE" fs cp main.py :main.py

echo ""
echo "Verifying deployment..."
echo "Files on device:"
mpremote connect "$DEVICE" fs ls : | grep -E '(ads1115.py|furnace_monitor.py|main.py|config.py)' || true

# Verify all required files are present
MISSING_FILES=0
for file in ads1115.py furnace_monitor.py main.py config.py; do
    if ! mpremote connect "$DEVICE" fs ls : | grep -q "$file"; then
        echo "ERROR: $file not found on device after deployment!"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done

if [ $MISSING_FILES -gt 0 ]; then
    echo ""
    echo "=== Deployment FAILED: $MISSING_FILES file(s) missing ==="
    exit 1
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "The monitor will auto-start on next ESP32 boot."
echo ""
echo "To start now without rebooting:"
echo "  mpremote connect $DEVICE run main.py"
echo ""
echo "To test manually:"
echo "  mpremote connect $DEVICE"
echo "  >>> from furnace_monitor import quick_test"
echo "  >>> quick_test()"
