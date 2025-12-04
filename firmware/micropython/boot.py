# Auto-start furnace monitoring on boot
# This file is executed on every boot (including wake-boot from deepsleep)

import time
import sys
import machine
from machine import WDT, RTC

# Enable watchdog IMMEDIATELY - 60 second timeout for boot sequence
wdt = WDT(timeout=60000)
wdt.feed()

print("\n" + "="*50)
print("Furnace Monitor - Auto-start enabled")
print("="*50 + "\n")

# Boot counter for failsafe mode (persistent in RTC memory)
rtc = RTC()
try:
    boot_data = rtc.memory()
    boot_count = int(boot_data.decode()) if boot_data else 0
except Exception as e:
    print(f"Boot counter read failed: {e}")
    boot_count = 0
boot_count += 1
rtc.memory(str(boot_count).encode())
print(f"Boot count: {boot_count}")
wdt.feed()

# Failsafe mode after 3 failed boots
if boot_count > 3:
    print(f"FAILSAFE: {boot_count} failed boots detected")
    print("Entering safe mode - WebREPL only, no monitoring")
    # Reset counter for next normal boot attempt
    rtc.memory(b'0')

    # Try to get WiFi up for remote recovery
    try:
        from config import WIFI_SSID, WIFI_PASSWORD
        from furnace_monitor import setup_wifi
        setup_wifi(WIFI_SSID, WIFI_PASSWORD)

        # Start WebREPL for remote access
        try:
            from webrepl_cfg import PASS
            if PASS == 'CHANGEME':
                print("WebREPL password is still 'CHANGEME' - refusing to start")
                print("Edit webrepl_cfg.py and set a unique password")
            elif 4 <= len(PASS) <= 9:
                import webrepl
                webrepl.start()
                print("WebREPL started - remote recovery enabled on port 8266")
            else:
                print(f"WebREPL password must be 4-9 characters (got {len(PASS)})")
        except Exception as e:
            print(f"Failsafe WebREPL failed: {e}")
    except Exception as e:
        print(f"Failsafe WiFi failed: {e}")

    # Stay in safe mode indefinitely, feeding watchdog
    print("Waiting in safe mode for remote recovery...")
    while True:
        wdt.feed()
        time.sleep(30)

# Give system a moment to settle
time.sleep(2)
wdt.feed()

# Connect WiFi FIRST - WebREPL needs network to work
wifi_ok = False
wdt.feed()
try:
    from config import WIFI_SSID, WIFI_PASSWORD
    from furnace_monitor import setup_wifi
    print("Connecting WiFi for WebREPL...")
    wifi_ok = setup_wifi(WIFI_SSID, WIFI_PASSWORD)
    if wifi_ok:
        print("WiFi connected")
    else:
        print("WiFi failed - WebREPL will not work")
except ImportError as e:
    print(f"Config not found: {e}")
    sys.print_exception(e)
except OSError as e:
    print(f"WiFi setup failed (OSError): {e}")
    sys.print_exception(e)
except Exception as e:
    print(f"WiFi setup failed (unexpected): {e}")
    sys.print_exception(e)

wdt.feed()

# Start WebREPL if WiFi is up
if wifi_ok:
    try:
        from webrepl_cfg import PASS
        if PASS == 'CHANGEME':
            print("WebREPL password is still 'CHANGEME' - refusing to start")
            print("Edit webrepl_cfg.py and set a unique password")
        elif not (4 <= len(PASS) <= 9):
            print(f"WebREPL password must be 4-9 characters (got {len(PASS)})")
        else:
            import webrepl
            webrepl.start()
            print("WebREPL started - remote access enabled on port 8266")
    except ImportError:
        print("WebREPL not configured (webrepl_cfg.py missing)")
    except OSError as e:
        print(f"WebREPL failed (OSError): {e}")
        sys.print_exception(e)
    except Exception as e:
        print(f"WebREPL failed to start: {e}")
        sys.print_exception(e)

wdt.feed()

# Run the monitor from main.py (has watchdog and crash recovery)
# Pass RTC so counter can be reset after successful sensor init
try:
    from main import run_monitor
    run_monitor(rtc=rtc)
except Exception as e:
    print(f"FATAL: Monitor failed to start: {e}")
    sys.print_exception(e)
    # Clean shutdown before reset
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.disconnect()
        wlan.active(False)
    except Exception as cleanup_err:
        print(f"WiFi cleanup failed: {cleanup_err}")
    print("Rebooting in 10 seconds...")
    time.sleep(10)
    machine.reset()
