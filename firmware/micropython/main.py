"""
Main entry point for ESP32 furnace monitor.
Auto-runs on boot if copied to the ESP32.
"""

from furnace_monitor import FurnaceMonitor

# Configuration
WIFI_SSID = "YOUR_SSID"
WIFI_PASSWORD = "YOUR_PASSWORD"
VECTOR_HOST = "192.168.50.224"  # Pi IP address
VECTOR_PORT = 9000  # Vector UDP port

# Create and start monitor
fm = FurnaceMonitor(
    ssid=WIFI_SSID,
    password=WIFI_PASSWORD,
    vector_host=VECTOR_HOST,
    vector_port=VECTOR_PORT
)

fm.init()

# Run indefinitely (use Ctrl+C to stop)
fm.monitor(duration_sec=86400, interval_sec=1)  # 24 hours
