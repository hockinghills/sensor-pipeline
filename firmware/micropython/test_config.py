from config import WIFI_SSID, WIFI_PASSWORD, VECTOR_HOST, VECTOR_PORT

# Validate config has non-empty values
assert WIFI_SSID, "WIFI_SSID cannot be empty"
assert WIFI_PASSWORD, "WIFI_PASSWORD cannot be empty"
assert VECTOR_HOST, "VECTOR_HOST cannot be empty"
assert isinstance(VECTOR_PORT, int), "VECTOR_PORT must be an integer"
assert 1 <= VECTOR_PORT <= 65535, "VECTOR_PORT must be in range 1-65535"

print(f"Network: {WIFI_SSID[:3]}***")
print(f"Vector: {VECTOR_HOST[:8]}***:{VECTOR_PORT}")
print("Config loaded successfully!")
