"""
Main entry point for ESP32 furnace monitor.
Auto-runs on boot if copied to the ESP32.

Includes watchdog timer and automatic crash recovery for 24/7 operation.
"""

import time
import gc
from machine import WDT
from furnace_monitor import FurnaceMonitor

# Configuration - load from config.py (not in version control)
try:
    from config import WIFI_SSID, WIFI_PASSWORD, VECTOR_HOST, VECTOR_PORT
except ImportError:
    print("ERROR: config.py not found")
    print("Create firmware/micropython/config.py with:")
    print("  WIFI_SSID = 'your_ssid'")
    print("  WIFI_PASSWORD = 'your_password'")
    print("  VECTOR_HOST = '192.168.50.224'")
    print("  VECTOR_PORT = 9000")
    raise

# Watchdog timeout (ms) - must be fed more frequently than this
WDT_TIMEOUT_MS = 30000  # 30 seconds


def run_monitor(rtc=None):
    """Run monitor with exception recovery.

    Args:
        rtc: Optional RTC object for boot counter management.
             If provided, boot counter is reset after successful sensor init.
    """
    # Enable watchdog timer
    wdt = WDT(timeout=WDT_TIMEOUT_MS)
    print(f"Watchdog enabled: {WDT_TIMEOUT_MS // 1000} second timeout")

    # Infinite loop with crash recovery
    restart_count = 0

    while True:
        gc.collect()  # Explicit GC before each monitoring cycle
        fm = None
        try:
            print(f"\n=== Starting furnace monitor (restart #{restart_count}) ===")

            # Create and initialize monitor
            fm = FurnaceMonitor(
                ssid=WIFI_SSID,
                password=WIFI_PASSWORD,
                vector_host=VECTOR_HOST,
                vector_port=VECTOR_PORT
            )

            fm.init()
            wdt.feed()

            # Reset boot counter AFTER successful init - failsafe only triggers
            # if we crash before reaching this point
            if rtc:
                try:
                    rtc.memory(b'0')
                    print("Boot counter reset - startup successful")
                except Exception as e:
                    print(f"Boot counter reset failed (non-fatal): {e}")

            # Run monitoring with watchdog feeding - no duration limit for 24/7 operation
            fm.monitor(duration_sec=None, interval_sec=1, watchdog=wdt)

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
            print(f"\n!!! CRASH DETECTED (restart #{restart_count}) !!!")
            print(f"Error: {e}")

            # Clean up resources before restart
            if fm:
                try:
                    fm.cleanup()
                except Exception as cleanup_error:
                    print(f"! Cleanup failed: {cleanup_error}")

            print("Restarting in 5 seconds...")

            try:
                wdt.feed()
            except:
                pass

            time.sleep(5)
            # Loop continues, will restart monitoring


if __name__ == "__main__":
    run_monitor()
