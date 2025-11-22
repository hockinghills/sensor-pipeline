#!/bin/bash
# BME680 streaming reader - 10Hz (100ms intervals)
# Outputs JSON with temp, pressure, humidity

BME_PATH="/sys/bus/i2c/devices/1-0077/iio:device0"

while true; do
  temp=$(cat "$BME_PATH/in_temp_input" 2>/dev/null)
  pressure=$(cat "$BME_PATH/in_pressure_input" 2>/dev/null)
  humidity=$(cat "$BME_PATH/in_humidityrelative_input" 2>/dev/null)

  if [ -n "$temp" ] && [ -n "$pressure" ] && [ -n "$humidity" ]; then
    echo "{\"temp\":$temp,\"pressure\":$pressure,\"humidity\":$humidity}"
  fi

  sleep 0.1
done
