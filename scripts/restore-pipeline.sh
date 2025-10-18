#!/bin/bash
# Pipeline Restore Script - Emergency Rollback
# Restores sensor pipeline from backup snapshot

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

if [ -z "$1" ]; then
    echo -e "${RED}Usage: $0 <backup-name>${NC}"
    echo ""
    echo "Available backups:"
    ls -1 ~/pipeline-backups/ 2>/dev/null || echo "  (no backups found)"
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_DIR="$HOME/pipeline-backups"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

if [ ! -d "${BACKUP_PATH}" ]; then
    echo -e "${RED}ERROR: Backup not found: ${BACKUP_PATH}${NC}"
    exit 1
fi

echo -e "${YELLOW}🚨 ================================================${NC}"
echo -e "${YELLOW}🚨 EMERGENCY PIPELINE RESTORE${NC}"
echo -e "${YELLOW}🚨 ================================================${NC}"
echo ""
echo "Restoring from: ${BACKUP_NAME}"
echo ""
echo -e "${RED}WARNING: This will:${NC}"
echo "  - Stop all pipeline services"
echo "  - Restore git repository state"
echo "  - Restore InfluxDB data (OVERWRITING CURRENT DATA)"
echo "  - Restore quadlet configurations"
echo "  - Restart all services"
echo ""
read -p "Continue? (type 'yes' to proceed): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}Starting restore...${NC}"

# 1. Stop all services
echo "🛑 Stopping services..."
systemctl --user stop telegraf.service 2>/dev/null || true
systemctl --user stop influxdb.service 2>/dev/null || true
systemctl --user stop hivemq.service 2>/dev/null || true
systemctl --user stop esphome.service 2>/dev/null || true
sleep 3

# 2. Restore git repository
echo "📦 Restoring git repository state..."
cd ~/sensor-pipeline

if [ -f "${BACKUP_PATH}/git-status.txt" ]; then
    GIT_TAG=$(grep -oP 'backup-\d{8}-\d{6}' "${BACKUP_PATH}/MANIFEST.txt" | head -1)
    if [ -n "$GIT_TAG" ]; then
        echo "   Checking out git tag: ${GIT_TAG}"
        git checkout "${GIT_TAG}" 2>/dev/null || echo "   (git tag not found, using current state)"
    fi
fi

# 3. Restore quadlet configurations
echo "⚙️  Restoring quadlet configurations..."
if [ -d "${BACKUP_PATH}/quadlets-deployed" ]; then
    rm -f ~/.config/containers/systemd/*.container
    cp "${BACKUP_PATH}"/quadlets-deployed/*.container ~/.config/containers/systemd/ 2>/dev/null || true
fi

# 4. Restore Telegraf configuration
echo "📝 Restoring Telegraf configuration..."
if [ -f "${BACKUP_PATH}/telegraf.conf" ]; then
    cp "${BACKUP_PATH}/telegraf.conf" ~/sensor-pipeline/configs/
fi

# 5. Restore InfluxDB data (CRITICAL)
echo "🗄️  Restoring InfluxDB data..."
if [ -f "${BACKUP_PATH}/influxdb3-data.tar.gz" ]; then
    echo "   Removing current InfluxDB data..."
    rm -rf ~/.influxdb3

    echo "   Extracting backup data..."
    tar -xzf "${BACKUP_PATH}/influxdb3-data.tar.gz" -C ~/

    echo "✅ InfluxDB data restored"
else
    echo -e "${YELLOW}   WARNING: No InfluxDB backup found${NC}"
fi

# 6. Restore HiveMQ data
echo "📨 Restoring HiveMQ data..."
if [ -f "${BACKUP_PATH}/hivemq-data.tar.gz" ]; then
    rm -rf ~/sensor-pipeline/data/hivemq
    mkdir -p ~/sensor-pipeline/data
    tar -xzf "${BACKUP_PATH}/hivemq-data.tar.gz" -C ~/sensor-pipeline/data/
    echo "✅ HiveMQ data restored"
fi

# 7. Reload systemd
echo "🔄 Reloading systemd..."
systemctl --user daemon-reload

# 8. Restart services in dependency order
echo "▶️  Starting services..."

echo "   Starting HiveMQ..."
systemctl --user start hivemq.service
sleep 2

echo "   Starting InfluxDB..."
systemctl --user start influxdb.service
sleep 3

echo "   Starting Telegraf..."
systemctl --user start telegraf.service
sleep 2

# 9. Check service status
echo ""
echo "📊 Service Status:"
systemctl --user is-active hivemq.service && echo -e "   HiveMQ:   ${GREEN}✅ RUNNING${NC}" || echo -e "   HiveMQ:   ${RED}❌ FAILED${NC}"
systemctl --user is-active influxdb.service && echo -e "   InfluxDB: ${GREEN}✅ RUNNING${NC}" || echo -e "   InfluxDB: ${RED}❌ FAILED${NC}"
systemctl --user is-active telegraf.service && echo -e "   Telegraf: ${GREEN}✅ RUNNING${NC}" || echo -e "   Telegraf: ${RED}❌ FAILED${NC}"

echo ""
echo -e "${GREEN}✅ ================================================${NC}"
echo -e "${GREEN}✅ RESTORE COMPLETE${NC}"
echo -e "${GREEN}✅ ================================================${NC}"
echo ""
echo "Restored from: ${BACKUP_NAME}"
echo ""
echo "Check detailed service status:"
echo "  systemctl --user status hivemq influxdb telegraf"
echo ""
