"""
Sensor Pipeline Deployment
Single source of truth for the entire system configuration.

Run locally: pyinfra @local deploy.py
Run remotely: pyinfra piiot deploy.py
"""

from pathlib import Path
from pyinfra import host
from pyinfra.operations import apt, files, server, systemd

# Paths
PYINFRA_DIR = Path(__file__).resolve().parent
REPO_DIR = PYINFRA_DIR.parent
QUADLETS_SRC = PYINFRA_DIR / "quadlets"
QUADLETS_DEST = Path.home() / ".config" / "containers" / "systemd"
MONIT_SRC = PYINFRA_DIR / "monit" / "sensor-pipeline.conf"
MONIT_DEST = Path("/etc/monit/conf.d/sensor-pipeline.conf")

# =============================================================================
# PACKAGES
# =============================================================================

apt.packages(
    name="Install monit",
    packages=["monit"],
    _sudo=True,
)

# =============================================================================
# CLEANUP - Remove old/unused quadlets
# =============================================================================

OLD_QUADLETS = [
    "telegraf.container",
    "esphome.container",
    "grafana.container",
    "influxdb.container",
]

for quadlet in OLD_QUADLETS:
    files.file(
        name=f"Remove old quadlet: {quadlet}",
        path=str(QUADLETS_DEST / quadlet),
        present=False,
    )

# =============================================================================
# QUADLETS - Deploy service definitions
# =============================================================================

files.directory(
    name="Ensure quadlets directory exists",
    path=str(QUADLETS_DEST),
    present=True,
)

ACTIVE_QUADLETS = [
    "victoriametrics.container",
    "hivemq.container",
    "vector.container",
]

for quadlet in ACTIVE_QUADLETS:
    files.put(
        name=f"Deploy quadlet: {quadlet}",
        src=str(QUADLETS_SRC / quadlet),
        dest=str(QUADLETS_DEST / quadlet),
        mode="644",
    )

# =============================================================================
# MONIT - Deploy monitoring configuration
# =============================================================================

files.put(
    name="Deploy monit configuration",
    src=str(MONIT_SRC),
    dest=str(MONIT_DEST),
    mode="644",
    _sudo=True,
)

# =============================================================================
# SYSTEMD - Reload and manage services
# =============================================================================

server.shell(
    name="Reload systemd user daemon",
    commands=["systemctl --user daemon-reload"],
)

# Stop old containers that shouldn't be running
OLD_CONTAINERS = ["telegraf", "esphome", "grafana", "influxdb2", "pdc-agent", "questdb"]

server.shell(
    name="Stop and remove old containers",
    commands=[f"podman stop {c} 2>/dev/null; podman rm {c} 2>/dev/null || true" for c in OLD_CONTAINERS],
)

# Start services in dependency order
# Using shell because quadlet services can't be enabled/disabled traditionally
server.shell(
    name="Start services in order",
    commands=[
        "systemctl --user start hivemq",
        "systemctl --user start victoriametrics",
        "sleep 2",  # Give VictoriaMetrics time to be ready
        "systemctl --user start vector",
    ],
)

# Start monit
systemd.service(
    name="Enable and start monit",
    service="monit",
    running=True,
    enabled=True,
    _sudo=True,
)

# =============================================================================
# VERIFICATION
# =============================================================================

server.shell(
    name="Verify services are running",
    commands=[
        "echo '=== Service Status ==='",
        "systemctl --user is-active hivemq victoriametrics vector",
        "echo '=== Health Checks ==='",
        "curl -sf http://127.0.0.1:8428/health && echo ' VictoriaMetrics OK'",
        "curl -sf http://127.0.0.1:8686/health && echo ' Vector OK'",
        "timeout 1 bash -c '</dev/tcp/127.0.0.1/1883' && echo ' HiveMQ OK'",
    ],
)
