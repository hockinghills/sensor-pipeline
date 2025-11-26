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

echo "Copying ads1115.py driver..."
mpremote connect "$DEVICE" fs cp ads1115.py :ads1115.py

echo "Copying furnace_monitor.py..."
mpremote connect "$DEVICE" fs cp furnace_monitor.py :furnace_monitor.py

echo "Copying main.py (auto-run on boot)..."
mpremote connect "$DEVICE" fs cp main.py :main.py

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
