#!/bin/bash
# Backup Script for IoT Sensor Pipeline
# Creates a complete backup of the current running configuration

set -e

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="sensor-pipeline-backup-$BACKUP_DATE"
BACKUP_DIR="$HOME/backups/$BACKUP_NAME"

echo "💾 Creating backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR"/{quadlets,configs,data,scripts}

# Backup quadlet configurations
echo "📋 Backing up quadlet configurations..."
cp ~/.config/containers/systemd/*.container "$BACKUP_DIR/quadlets/" 2>/dev/null || echo "⚠️  No quadlet files found"

# Backup Telegraf configuration
echo "📊 Backing up Telegraf configuration..."
if [ -f ~/sensor-pipeline/configs/telegraf.conf ]; then
    cp ~/sensor-pipeline/configs/telegraf.conf "$BACKUP_DIR/configs/"
else
    echo "⚠️  Telegraf config not found at ~/sensor-pipeline/configs/telegraf.conf"
fi

# Backup current token (if available)
echo "🔑 Extracting current InfluxDB token..."
if systemctl --user is-active --quiet influxdb.service; then
    # Try to extract token from running Telegraf config
    if [ -f ~/sensor-pipeline/configs/telegraf.conf ]; then
        CURRENT_TOKEN=$(grep 'token = ' ~/sensor-pipeline/configs/telegraf.conf | cut -d'"' -f2)
        if [ -n "$CURRENT_TOKEN" ]; then
            echo "$CURRENT_TOKEN" > "$BACKUP_DIR/configs/influxdb_token.txt"
            echo "✅ Current token saved"
        fi
    fi
else
    echo "⚠️  InfluxDB not running, cannot extract token"
fi

# Backup service status
echo "📋 Recording service status..."
systemctl --user status hivemq.service influxdb.service telegraf.service > "$BACKUP_DIR/service_status.txt" 2>&1 || true

# Create restoration notes
cat > "$BACKUP_DIR/RESTORE_NOTES.md" << 'EOF'
# Restoration Notes

## Quick Restore
1. Copy quadlet files: `cp quadlets/*.container ~/.config/containers/systemd/`
2. Copy configs: `mkdir -p ~/sensor-pipeline/configs && cp configs/* ~/sensor-pipeline/configs/`
3. Set up directories: `mkdir -p ~/.influxdb3 ~/.influxdb3-plugins/.venv/bin && chmod 777 ~/.influxdb3 ~/.influxdb3-plugins && touch ~/.influxdb3-plugins/.venv/bin/activate`
4. Initialize BME680: See main README.md
5. Reload and start: `systemctl --user daemon-reload && systemctl --user start hivemq.service influxdb.service telegraf.service`

## Token
If `configs/influxdb_token.txt` exists, use this token in:
- Telegraf configuration
- Grafana Cloud configuration

## Manual Token Creation
If token is lost, create new one:
```bash
podman exec influxdb3 influxdb3 create token --admin
podman exec influxdb3 influxdb3 create database --token "NEW_TOKEN" fucked
```

EOF

# Copy current working scripts if they exist
if [ -d ~/sensor-pipeline-backup/scripts ]; then
    echo "📜 Backing up scripts..."
    cp ~/sensor-pipeline-backup/scripts/* "$BACKUP_DIR/scripts/" 2>/dev/null || true
fi

# Create system info
echo "💻 Recording system information..."
cat > "$BACKUP_DIR/system_info.txt" << EOF
Backup Date: $(date)
Hostname: $(hostname)
OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)
Kernel: $(uname -r)
Podman Version: $(podman --version)
Architecture: $(uname -m)

Disk Space:
$(df -h)

Memory:
$(free -h)

I2C Devices:
$(sudo i2cdetect -y 1 2>/dev/null || echo "Could not scan I2C")

Network Interfaces:
$(ip addr show | grep inet)
EOF

# Create compressed archive
echo "🗜️  Creating compressed archive..."
cd "$HOME/backups"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

echo "✅ Backup complete: $HOME/backups/${BACKUP_NAME}.tar.gz"
echo "📁 Size: $(du -h "$HOME/backups/${BACKUP_NAME}.tar.gz" | cut -f1)"

# Clean up old backups (keep last 5)
echo "🧹 Cleaning up old backups..."
cd "$HOME/backups"
ls -t sensor-pipeline-backup-*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f || true

echo "🎉 Backup process complete!"