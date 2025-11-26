"""
Main entry point for ESP32 furnace monitor.
Auto-runs on boot if copied to the ESP32.

Includes watchdog timer and automatic crash recovery for 24/7 operation.
"""

import time
from machine import WDT
from furnace_monitor import FurnaceMonitor

# Configuration
WIFI_SSID = "holyshitHollar"
WIFI_PASSWORD = "gotNewWifi93$"
VECTOR_HOST = "192.168.50.224"  # Pi IP address
VECTOR_PORT = 9000  # Vector UDP port

# Watchdog timeout (ms) - must be fed more frequently than this
WDT_TIMEOUT_MS = 30000  # 30 seconds


def run_monitor():
    """Run monitor with exception recovery."""
    # Enable watchdog timer
    wdt = WDT(timeout=WDT_TIMEOUT_MS)
    print("Watchdog enabled: {} second timeout".format(WDT_TIMEOUT_MS // 1000))

    # Infinite loop with crash recovery
    restart_count = 0

    while True:
        try:
            print("\n=== Starting furnace monitor (restart #{}) ===".format(restart_count))

            # Create and initialize monitor
            fm = FurnaceMonitor(
                ssid=WIFI_SSID,
                password=WIFI_PASSWORD,
                vector_host=VECTOR_HOST,
                vector_port=VECTOR_PORT
            )

            fm.init()
            wdt.feed()

            # Run monitoring with watchdog feeding
            fm.monitor(duration_sec=86400, interval_sec=1, watchdog=wdt)

            # If we get here, monitoring completed normally
            print("Monitoring cycle complete, restarting...")
            restart_count += 1
            wdt.feed()
            time.sleep(1)

        except KeyboardInterrupt:
            print("\n=== Stopped by user ===")
            break

        except Exception as e:
            # Log crash and restart
            restart_count += 1
            print("\n!!! CRASH DETECTED (restart #{}) !!!".format(restart_count))
            print("Error: {}".format(e))
            print("Restarting in 5 seconds...")

            try:
                wdt.feed()
            except:
                pass

            time.sleep(5)
            # Loop continues, will restart monitoring


if __name__ == "__main__":
    run_monitor()
