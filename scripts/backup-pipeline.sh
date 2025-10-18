#!/bin/bash
# Pre-Migration Backup Script for Sensor Pipeline
# Creates comprehensive backup of configuration, data, and container state

set -e

BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$HOME/pipeline-backups"
BACKUP_NAME="pipeline-backup-${BACKUP_DATE}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "🔄 Starting sensor pipeline backup: ${BACKUP_NAME}"

# Create backup directory
mkdir -p "${BACKUP_PATH}"

# 1. Git repository state
echo "📦 Backing up git repository state..."
cd ~/sensor-pipeline
git status > "${BACKUP_PATH}/git-status.txt"
git log --oneline -20 > "${BACKUP_PATH}/git-log.txt"
git diff > "${BACKUP_PATH}/git-diff.txt" || true

# Create git tag
TAG_NAME="backup-${BACKUP_DATE}"
git tag -a "${TAG_NAME}" -m "Backup snapshot before ESPHome migration at ${BACKUP_DATE}"
echo "✅ Created git tag: ${TAG_NAME}"

# 2. Service states
echo "📋 Saving service states..."
systemctl --user list-units --type=service --all | grep -E "(hivemq|influx|telegraf)" > "${BACKUP_PATH}/service-status.txt" || true
systemctl --user status hivemq.service > "${BACKUP_PATH}/hivemq-status.txt" 2>&1 || true
systemctl --user status influxdb.service > "${BACKUP_PATH}/influxdb-status.txt" 2>&1 || true
systemctl --user status telegraf.service > "${BACKUP_PATH}/telegraf-status.txt" 2>&1 || true

# 3. Container images
echo "🐳 Saving container image information..."
podman images --format "{{.Repository}}:{{.Tag}} {{.ID}} {{.Created}}" | grep -E "(hivemq|telegraf|influxdb)" > "${BACKUP_PATH}/container-images.txt"

# 4. Running container states
echo "💾 Creating container snapshots..."
podman commit influxdb3 localhost/influxdb3:backup-${BACKUP_DATE} 2>&1 | tee -a "${BACKUP_PATH}/container-commits.log"
podman commit hivemq localhost/hivemq:backup-${BACKUP_DATE} 2>&1 | tee -a "${BACKUP_PATH}/container-commits.log"
podman commit telegraf localhost/telegraf:backup-${BACKUP_DATE} 2>&1 | tee -a "${BACKUP_PATH}/container-commits.log"

# 5. Quadlet configurations
echo "⚙️  Backing up quadlet configurations..."
cp -r ~/sensor-pipeline/quadlets "${BACKUP_PATH}/quadlets-source"
cp -r ~/.config/containers/systemd/*.container "${BACKUP_PATH}/quadlets-deployed" 2>/dev/null || true

# 6. Telegraf configuration
echo "📝 Backing up Telegraf configuration..."
cp ~/sensor-pipeline/configs/telegraf.conf "${BACKUP_PATH}/"

# 7. InfluxDB data (CRITICAL)
echo "🗄️  Backing up InfluxDB data (this may take a moment)..."
systemctl --user stop influxdb.service
sleep 2

INFLUX_DATA_SIZE=$(du -sh ~/.influxdb3 | cut -f1)
echo "   InfluxDB data size: ${INFLUX_DATA_SIZE}"

tar -czf "${BACKUP_PATH}/influxdb3-data.tar.gz" -C ~/ .influxdb3
echo "✅ InfluxDB data backed up"

systemctl --user start influxdb.service
sleep 3
echo "✅ InfluxDB service restarted"

# 8. HiveMQ data
echo "📨 Backing up HiveMQ data..."
tar -czf "${BACKUP_PATH}/hivemq-data.tar.gz" -C ~/sensor-pipeline/data hivemq 2>/dev/null || echo "   (no HiveMQ data found)"

# 9. Create backup manifest
echo "📄 Creating backup manifest..."
cat > "${BACKUP_PATH}/MANIFEST.txt" << EOF
Sensor Pipeline Backup
======================
Date: ${BACKUP_DATE}
Host: $(hostname)
User: $(whoami)

Git Tag: ${TAG_NAME}
Git Commit: $(git rev-parse HEAD)
Git Branch: $(git branch --show-current)

Services Backed Up:
- HiveMQ Edge
- InfluxDB v3
- Telegraf

Container Images:
$(cat "${BACKUP_PATH}/container-images.txt")

InfluxDB Data Size: ${INFLUX_DATA_SIZE}

Files in Backup:
$(ls -lh "${BACKUP_PATH}")

To restore from this backup, run:
  ~/sensor-pipeline/scripts/restore-pipeline.sh ${BACKUP_NAME}
EOF

# 10. Create quick restore script
cat > "${BACKUP_PATH}/quick-restore.sh" << 'EOF'
#!/bin/bash
# Quick restore script for this specific backup
set -e
BACKUP_PATH="$(dirname "$(readlink -f "$0")")"
~/sensor-pipeline/scripts/restore-pipeline.sh "$(basename "${BACKUP_PATH}")"
EOF
chmod +x "${BACKUP_PATH}/quick-restore.sh"

# Summary
echo ""
echo "✅ ================================================"
echo "✅ BACKUP COMPLETE"
echo "✅ ================================================"
echo ""
echo "Backup Location: ${BACKUP_PATH}"
echo "Git Tag: ${TAG_NAME}"
echo "Total Backup Size: $(du -sh "${BACKUP_PATH}" | cut -f1)"
echo ""
echo "To restore from this backup:"
echo "  ${BACKUP_PATH}/quick-restore.sh"
echo "  or"
echo "  ~/sensor-pipeline/scripts/restore-pipeline.sh ${BACKUP_NAME}"
echo ""
