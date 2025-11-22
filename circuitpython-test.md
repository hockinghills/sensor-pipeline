import wifi
import time
import os
import ipaddress

# --- CONFIGURATION ---
TARGET_SSID = "YOUR_SSID"
TARGET_PASS = "YOUR_PASSWORD"
# ---------------------

print(f"\n--- Connecting to {TARGET_SSID} (Anti-Brownout Mode) ---")

wifi.radio.enabled = False
time.sleep(1)
wifi.radio.enabled = True

# THE MAGIC FIX
# 8.5 dBm is plenty for a house. 
# You can try increasing this to 10 or 12 later if you need more range.
try:
    wifi.radio.tx_power = 8.5
    print(f"TX Power capped at: {wifi.radio.tx_power} dBm")
except Exception as e:
    print(f"Power setting failed: {e}")

try:
    print("Handshaking...")
    wifi.radio.connect(TARGET_SSID, TARGET_PASS)
    
    print("\nSUCCESS! Connected.")
    print(f"IP Address: {wifi.radio.ipv4_address}")
    print(f"Signal Strength: {wifi.radio.ap_info.rssi}")

    # Ping Google to prove we have real internet
    print("Pinging Google...")
    ping_ip = ipaddress.IPv4Address("8.8.8.8")
    ping = wifi.radio.ping(ping_ip)
    if ping:
        print(f"Ping successful: {ping * 1000:.0f} ms")
    else:
        print("Ping failed (No Internet?)")

    while True:
        # Your main loop code goes here
        pass

except Exception as e:
    print(f"\nFAILURE: {e}")
