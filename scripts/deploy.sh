#!/bin/bash
# Sensor Pipeline Deployment Script
# Deploys the complete IoT sensor pipeline

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying IoT Sensor Pipeline..."
echo "📁 Project directory: $PROJECT_DIR"

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check if running on correct user
if [[ $EUID -eq 0 ]]; then
    echo "❌ Don't run this script as root. Use your regular user account."
    exit 1
fi

# Check for podman
if ! command -v podman &> /dev/null; then
    echo "❌ Podman not found. Please install podman first."
    exit 1
fi

# Check for systemd user directory
USER_SYSTEMD_DIR="$HOME/.config/containers/systemd"
if [ ! -d "$USER_SYSTEMD_DIR" ]; then
    echo "📁 Creating systemd user directory..."
    mkdir -p "$USER_SYSTEMD_DIR"
fi

# Step 1: Deploy quadlet files
echo "📋 Deploying quadlet configurations..."
cp "$PROJECT_DIR"/quadlets/*.container "$USER_SYSTEMD_DIR/"
echo "✅ Copied quadlet files to $USER_SYSTEMD_DIR"

# Step 2: Create config directories
echo "📁 Creating configuration directories..."
mkdir -p ~/sensor-pipeline/configs
cp "$PROJECT_DIR"/configs/* ~/sensor-pipeline/configs/
echo "✅ Configuration files deployed"

# Step 3: Set up InfluxDB data directories
echo "💾 Setting up InfluxDB data directories..."
mkdir -p ~/.influxdb3 ~/.influxdb3-plugins/.venv/bin
chmod 777 ~/.influxdb3 ~/.influxdb3-plugins
touch ~/.influxdb3-plugins/.venv/bin/activate
echo "✅ InfluxDB directories prepared"

# Step 4: Initialize BME680 sensor
echo "🌡️  Initializing BME680 sensor..."
if [ -f "$SCRIPT_DIR/setup-bme680.sh" ]; then
    bash "$SCRIPT_DIR/setup-bme680.sh"
else
    echo "⚠️  BME680 setup script not found. You'll need to initialize manually."
fi

# Step 5: Reload systemd and start services
echo "🔄 Reloading systemd configuration..."
systemctl --user daemon-reload

echo "🚀 Starting services..."
systemctl --user enable hivemq.service influxdb.service telegraf.service

# Start HiveMQ first
echo "📡 Starting HiveMQ Edge..."
systemctl --user start hivemq.service
sleep 5

# Start InfluxDB
echo "💾 Starting InfluxDB v3..."
systemctl --user start influxdb.service
sleep 10

# Check if InfluxDB is running
if systemctl --user is-active --quiet influxdb.service; then
    echo "✅ InfluxDB started successfully"

    # Create token and database
    echo "🔑 Creating InfluxDB token..."
    TOKEN_OUTPUT=$(podman exec influxdb3 influxdb3 create token --admin 2>/dev/null)
    TOKEN=$(echo "$TOKEN_OUTPUT" | grep "Token:" | cut -d' ' -f2)

    if [ -n "$TOKEN" ]; then
        echo "✅ Token created: $TOKEN"

        # Create database
        echo "💾 Creating database 'fucked'..."
        podman exec influxdb3 influxdb3 create database --token "$TOKEN" fucked
        echo "✅ Database created"

        # Update Telegraf config with new token
        echo "🔧 Updating Telegraf configuration with new token..."
        sed -i "s|token = \".*\"|token = \"$TOKEN\"|" ~/sensor-pipeline/configs/telegraf.conf
        echo "✅ Telegraf configuration updated"
    else
        echo "❌ Failed to create token. You'll need to do this manually."
    fi
else
    echo "❌ InfluxDB failed to start. Check logs: journalctl --user -u influxdb.service"
    exit 1
fi

# Start Telegraf
echo "📊 Starting Telegraf..."
systemctl --user start telegraf.service
sleep 5

# Check service status
echo "🔍 Checking service status..."
for service in hivemq influxdb telegraf; do
    if systemctl --user is-active --quiet ${service}.service; then
        echo "✅ ${service}.service is running"
    else
        echo "❌ ${service}.service is not running"
    fi
done

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update Grafana Cloud with the new token:"
echo "   Token: $TOKEN"
echo "2. Verify data flow:"
echo "   podman exec influxdb3 influxdb3 query --token \"$TOKEN\" --database fucked \"SHOW TABLES\""
echo "3. Check for flame sensor wiring if needed"
echo ""
echo "📚 For troubleshooting, see: $PROJECT_DIR/README.md"