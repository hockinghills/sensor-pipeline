# WiFi Network Configurations - EXAMPLE TEMPLATE
# Copy this to secrets.py and fill in your actual credentials

NETWORKS = {
    'hollar': {
        'ssid': 'YOUR_HOLLAR_SSID',
        'password': 'YOUR_HOLLAR_PASSWORD',
        'vector_host': 'YOUR_PI_TAILSCALE_IP',  # e.g., 100.x.x.x
        'vector_port': 9000
    },
    'studio': {
        'ssid': 'YOUR_STUDIO_SSID',
        'password': 'YOUR_STUDIO_PASSWORD',
        'vector_host': 'YOUR_PI_LOCAL_IP',  # e.g., 192.168.x.x
        'vector_port': 9000
    }
}

# Active network selection
# Change to 'hollar' or 'studio' depending on where the ESP32 is deployed
ACTIVE_NETWORK = 'studio'  # Default to studio - change before deployment
