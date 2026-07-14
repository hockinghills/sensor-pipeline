---
description: Repository Information Overview
alwaysApply: true
---

# Raspberry Pi Sensor Data Pipeline Information

## Summary
A complete IoT sensor data pipeline using Podman quadlets for containerized services on Raspberry Pi. Monitors a glass furnace with ESP32 sensors, BME680 environmental sensors, and pressure sensors, streaming data through MQTT and Vector to VictoriaMetrics for storage and Grafana Cloud for visualization.

## Structure
- **configs/**: Vector configuration files for data ingestion and processing
- **pyinfra/**: Infrastructure automation scripts using PyInfra for deployment
- **scripts/**: Shell scripts for sensor setup, data streaming, and health checks
- **system-config/**: Systemd services and configurations for automatic BME680 sensor initialization

## Specification & Tools
**Type**: Infrastructure as Code / Configuration Repository  
**Version**: N/A  
**Required Tools**: Podman, PyInfra, Monit, Vector, VictoriaMetrics, HiveMQ Edge

## Key Resources
**Main Files**:
- `configs/vector.toml`: Vector configuration for MQTT and sensor data ingestion
- `pyinfra/deploy.py`: PyInfra deployment script for system setup
- `pyinfra/quadlets/*.container`: Podman quadlet definitions for containerized services
- `scripts/health-check.sh`: System health monitoring script
- `scripts/setup-bme680.sh`: BME680 sensor initialization script
- `system-config/bme680-setup.service`: Systemd service for sensor setup

**Configuration Structure**:
- Podman quadlets define containerized services (HiveMQ, Vector, VictoriaMetrics)
- Vector processes data from MQTT topics and sensor inputs
- Monit provides process monitoring and automatic restarts
- Systemd handles sensor hardware initialization at boot

## Usage & Operations
**Key Commands**:
```bash
pyinfra @local deploy.py    # Deploy pipeline locally
pyinfra piiot deploy.py     # Deploy to remote Raspberry Pi host
./scripts/health-check.sh   # Run system health checks
./scripts/setup-bme680.sh   # Initialize BME680 sensor
```

**Integration Points**:
- MQTT broker (HiveMQ Edge) receives data from ESP32 sensors
- I2C bus interface for BME680 environmental sensor
- Serial USB connection for pressure sensors
- VictoriaMetrics for time-series data storage
- Grafana Cloud for dashboards and alerting

## Validation
**Quality Checks**: 
- `scripts/health-check.sh` performs comprehensive system validation
- Monit monitors service health and restarts failed processes
- Grafana Cloud alerts for temperature thresholds and data flow issues

**Testing Approach**: 
- Manual verification of sensor data flow through the pipeline
- Alert testing for safety-critical furnace monitoring
- Boot-time sensor initialization validation