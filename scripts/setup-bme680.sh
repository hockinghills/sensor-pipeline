#!/bin/bash
# BME680 Sensor Setup Script
# This script initializes the BME680 sensor on I2C bus

set -e

echo "🌡️  Setting up BME680 sensor..."

# Check if running as root for modprobe
if [[ $EUID -eq 0 ]]; then
    echo "❌ Don't run this script as root. It will sudo when needed."
    exit 1
fi

# Load BME680 I2C kernel module
echo "📡 Loading BME680 I2C driver..."
sudo modprobe bme680_i2c
if lsmod | grep -q bme680; then
    echo "✅ BME680 module loaded successfully"
else
    echo "❌ Failed to load BME680 module"
    exit 1
fi

# Check if device exists on I2C bus
echo "🔍 Scanning I2C bus for device at 0x77..."
if sudo i2cdetect -y 1 | grep -q "77"; then
    echo "✅ Device found at address 0x77"
else
    echo "❌ No device found at 0x77. Check wiring!"
    exit 1
fi

# Bind device to driver
echo "🔗 Binding BME680 device to driver..."
if [ ! -d "/sys/bus/i2c/devices/1-0077" ]; then
    echo "bme680 0x77" | sudo tee /sys/bus/i2c/devices/i2c-1/new_device > /dev/null
    sleep 2
fi

# Verify sensor files are available
echo "📁 Checking sensor files..."
SENSOR_DIR="/sys/bus/i2c/devices/1-0077/iio:device0"
if [ -d "$SENSOR_DIR" ]; then
    echo "✅ Sensor directory found: $SENSOR_DIR"

    # Check for required files
    for file in in_temp_input in_pressure_input in_humidityrelative_input; do
        if [ -f "$SENSOR_DIR/$file" ]; then
            echo "✅ Found: $file"
        else
            echo "⚠️  Missing: $file"
        fi
    done
else
    echo "❌ Sensor directory not found: $SENSOR_DIR"
    exit 1
fi

# Test reading values
echo "📊 Testing sensor readings..."
if [ -f "$SENSOR_DIR/in_temp_input" ]; then
    temp=$(cat "$SENSOR_DIR/in_temp_input")
    temp_c=$(echo "scale=2; $temp / 1000" | bc)
    echo "🌡️  Temperature: ${temp_c}°C"
fi

if [ -f "$SENSOR_DIR/in_pressure_input" ]; then
    pressure=$(cat "$SENSOR_DIR/in_pressure_input")
    pressure_hpa=$(echo "scale=2; $pressure / 1000" | bc)
    echo "🌬️  Pressure: ${pressure_hpa} hPa"
fi

if [ -f "$SENSOR_DIR/in_humidityrelative_input" ]; then
    humidity=$(cat "$SENSOR_DIR/in_humidityrelative_input")
    humidity_pct=$(echo "scale=2; $humidity / 1000" | bc)
    echo "💧 Humidity: ${humidity_pct}%"
fi

echo "🎉 BME680 setup complete!"
echo "💡 To make this persistent across reboots, ensure the Telegraf quadlet"
echo "    ExecStartPre commands are in place to run these steps automatically."