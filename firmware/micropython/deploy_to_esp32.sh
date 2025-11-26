#!/bin/bash
# Deploy furnace monitor to ESP32-S3

DEVICE="/dev/ttyACM0"

echo "=== Deploying Furnace Monitor to ESP32 ==="
echo "Device: $DEVICE"
echo ""

echo "Copying ads1115.py driver..."
mpremote connect $DEVICE fs cp ads1115.py :ads1115.py

echo "Copying furnace_monitor.py..."
mpremote connect $DEVICE fs cp furnace_monitor.py :furnace_monitor.py

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "To run the monitor:"
echo "  mpremote connect $DEVICE"
echo "  >>> from furnace_monitor import FurnaceMonitor"
echo "  >>> fm = FurnaceMonitor(ssid='YOUR_SSID', password='YOUR_PASS', vector_host='PI_IP')"
echo "  >>> fm.init()"
echo "  >>> fm.monitor()"
