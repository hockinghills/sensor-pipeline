#include "thingProperties.h"
#include <esp_netif.h>
#include <Adafruit_MAX31856.h>
#include <WiFi.h>
#include <ArduinoMqttClient.h>
#include <sys/time.h>
#include <esp_task_wdt.h> 

// --- MQTT Constants ---
// Your Pi's IP
const char broker[] = "192.168.50.224";
const int  port     = 1883;

// --- Pin Definitions ---
const int THERMOCOUPLE_CS_PIN = 5;
const int THERMOCOUPLE_MOSI_PIN = 23;
const int THERMOCOUPLE_MISO_PIN = 19;
const int THERMOCOUPLE_CLK_PIN = 18;
const int FLAME_ADC_PIN = 32;

// --- Voltage Divider Constants ---
// Flame sensor voltage divider: 32kΩ / (32kΩ + 10kΩ)
// Vout = Vin × R_bottom / (R_top + R_bottom)
// To reconstruct Vin from ADC Vout: Vin = Vout × (R_top + R_bottom) / R_bottom
const float VOLTAGE_DIVIDER_R_TOP = 32.0f;   // kΩ
const float VOLTAGE_DIVIDER_R_BOTTOM = 10.0f; // kΩ
const float VOLTAGE_DIVIDER_RATIO = (VOLTAGE_DIVIDER_R_TOP + VOLTAGE_DIVIDER_R_BOTTOM) / VOLTAGE_DIVIDER_R_BOTTOM;  // 4.2, not 3.2

// --- Task Handles ---
TaskHandle_t otaTaskHandle = NULL;
TaskHandle_t sensorTaskHandle = NULL;

// --- Network Objects ---
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

// --- Sensor Objects ---
Adafruit_MAX31856 max31856 = Adafruit_MAX31856(THERMOCOUPLE_CS_PIN,
                                                THERMOCOUPLE_MOSI_PIN, 
                                                THERMOCOUPLE_MISO_PIN, 
                                                THERMOCOUPLE_CLK_PIN);

// Add these variables after your existing declarations (around line 35):

// --- Mutex for Thread-Safe Access ---
SemaphoreHandle_t metricsMutex = NULL;

// --- Network Telemetry Variables ---
struct NetworkMetrics {
  int rssi = 0;
  unsigned long connectionUptime = 0;
  unsigned long lastConnectTime = 0;
  unsigned long mqttReconnectCount = 0;
  unsigned long wifiReconnectCount = 0;
  unsigned long packetsSent = 0;
  unsigned long packetsLost = 0;
  unsigned long lastLatencyMs = 0;
  char lastConnectionState[32] = "DISCONNECTED";  // Fixed buffer, no heap allocation
  unsigned long stateChangeCount = 0;
} netMetrics;

unsigned long lastNetworkMetricsTime = 0;
const unsigned long networkMetricsInterval = 5000; // 5 seconds
unsigned long pingStartTime = 0;
bool awaitingPong = false;

// --- MQTT Health Tracking ---
int consecutivePongFailures = 0;
const int MAX_PONG_FAILURES = 3;  // Force reconnect after this many failures
unsigned long lastMqttConnectAttempt = 0;
const unsigned long MQTT_RECONNECT_COOLDOWN = 5000;  // Don't spam reconnects

// --- Variables ---
bool sensorAvailable = false;  // Flag to track sensor initialization status
unsigned long lastMqttTime = 0;
// With Continuous Mode, we can now comfortably hit 10Hz (100ms)
const unsigned long mqttInterval = 100; 

// --- Forward Declarations ---
bool checkMQTT(); 
void publishMqttData();
void onFlameStrengthChange() {} 
void onFurnaceChange() {}       

// ===========================================================================
// CORE 0: OTA Task
// ===========================================================================
void otaTask(void *parameter) {
    // Add this task to watchdog (10 second timeout)
    esp_task_wdt_add(NULL);

    for(;;) {
        ArduinoCloud.update();
        esp_task_wdt_reset();  // Feed watchdog after successful update
        vTaskDelay(250 / portTICK_PERIOD_MS);
    }
}

// ===========================================================================
// CORE 1: Sensor & MQTT Task
// ===========================================================================
void sensorTask(void *parameter) {
    // Add this task to watchdog (10 second timeout)
    esp_task_wdt_add(NULL);

    for(;;) {
        unsigned long currentMillis = millis();

        if (WiFi.status() == WL_CONNECTED) {
            // Only poll MQTT when WiFi is connected
            mqttClient.poll();

            if (checkMQTT()) {
                if (currentMillis - lastMqttTime >= mqttInterval) {
                    publishMqttData();
                    lastMqttTime = currentMillis;
                }
            }
        } else {
            Serial.println("WiFi disconnected in sensor task");
        }

        // Feed watchdog after successful sensor cycle
        esp_task_wdt_reset();

        // Short yield to keep FreeRTOS happy
        vTaskDelay(20 / portTICK_PERIOD_MS);
    }
}

void setup() {
    Serial.begin(115200);
    delay(1500);
    Serial.println("=== ESP32 Furnace Monitor Starting ===");
    Serial.println("Firmware: jul28a_fixed with MQTT health tracking");

    // Initialize mutex for shared variable protection
    metricsMutex = xSemaphoreCreateMutex();
    if (metricsMutex == NULL) {
        Serial.println("FATAL: Failed to create mutex!");
        while(1);
    }

    // Initialize watchdog timer (10 second timeout)
    esp_task_wdt_init(10, true);  // 10s timeout, panic on timeout
    Serial.println("Watchdog timer initialized");

    // 1. Setup Cloud/WiFi
    initProperties(); 
    ArduinoCloud.begin(ArduinoIoTPreferredConnection);
    
    // 2. Setup Hardware
    bool sensorInitialized = false;
    for (int retry = 0; retry < 3; retry++) {
        if (max31856.begin()) {
            sensorInitialized = true;
            Serial.println("MAX31856 initialized successfully");
            break;
        }
        Serial.println("MAX31856 init failed, retrying...");
        delay(1000);
    }

    if (!sensorInitialized) {
        Serial.println("MAX31856 init failed after 3 retries - continuing without sensor");
        sensorAvailable = false;
    } else {
        sensorAvailable = true;
    } 
    
    // --------------------------------------------------------
    // THE CRITICAL FIX
    // --------------------------------------------------------
    max31856.setThermocoupleType(MAX31856_TCTYPE_S);
    
    // Continuous Mode tells the chip to convert as fast as it can 
    // in the background. Crucially, it tells the Adafruit library 
    // NOT to insert the blocking delay() when we read it.
    max31856.setConversionMode(MAX31856_CONTINUOUS);
    // --------------------------------------------------------

    analogSetPinAttenuation(FLAME_ADC_PIN, ADC_11db);


    // 3. Wait for WiFi
    Serial.print("Waiting for WiFi...");
    unsigned long startWait = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startWait < 20000) {
        delay(500);
        Serial.print(".");
        ArduinoCloud.update(); 
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(" Connected!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println(" WiFi connection timeout!");
    }

    // 4. Time Sync
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");

    // 5. MQTT Setup
    mqttClient.setUsernamePassword("", "");
    mqttClient.setId("ESP32Client");
    mqttClient.setKeepAliveInterval(60000);
    mqttClient.setConnectionTimeout(5000);  // 5 second timeout to prevent blocking
    mqttClient.onMessage(onMqttMessage);
    netMetrics.lastConnectTime = millis();

    Serial.println("=== Setup Complete: Tasks Starting ===");

    xTaskCreatePinnedToCore(otaTask, "OTATask", 32768, NULL, 0, &otaTaskHandle, 0);
    xTaskCreatePinnedToCore(sensorTask, "SensorTask", 16384, NULL, 1, &sensorTaskHandle, 1);  // 16KB stack for snprintf operations
}

void loop() {
    vTaskDelete(NULL);
}

// --- Helper Functions ---

void forceDisconnectMQTT() {
    Serial.println(">>> Forcing MQTT disconnect");
    mqttClient.stop();
    consecutivePongFailures = 0;
    awaitingPong = false;
}

bool checkMQTT() {
    unsigned long now = millis();
    
    // If we've had too many pong failures, force disconnect
    if (consecutivePongFailures >= MAX_PONG_FAILURES) {
        Serial.print("!!! ");
        Serial.print(consecutivePongFailures);
        Serial.println(" consecutive pong failures - forcing reconnect");
        forceDisconnectMQTT();
    }
    
    if (!mqttClient.connected()) {
        // Don't spam reconnect attempts
        if (now - lastMqttConnectAttempt < MQTT_RECONNECT_COOLDOWN) {
            return false;
        }
        lastMqttConnectAttempt = now;
        
        Serial.print("MQTT connecting to ");
        Serial.print(broker);
        Serial.print(":");
        Serial.print(port);
        Serial.print("... ");
        
        if (mqttClient.connect(broker, port)) {
            Serial.println("SUCCESS!");

            // Subscribe to pong response (one-time on connect)
            mqttClient.subscribe("furnace/pong");
            Serial.println("Subscribed to furnace/pong");

            // Track reconnection (mutex protected)
            if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
                netMetrics.mqttReconnectCount++;
                xSemaphoreGive(metricsMutex);
            }
            
            consecutivePongFailures = 0;
            return true;
        } else {
            Serial.print("FAILED! Error code: ");
            Serial.println(mqttClient.connectError());
            return false;
        }
    }
    return true;
}

 
// Add MQTT message callback for latency measurement
void onMqttMessage(int messageSize) {
    String topic = mqttClient.messageTopic();
    Serial.print("MQTT message received on topic: ");
    Serial.println(topic);
    
    if (awaitingPong && topic == "furnace/pong") {
        unsigned long latency = millis() - pingStartTime;
        Serial.print("Pong received! Latency: ");
        Serial.print(latency);
        Serial.println("ms");

        if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
            netMetrics.lastLatencyMs = latency;
            xSemaphoreGive(metricsMutex);
        }

        awaitingPong = false;
        consecutivePongFailures = 0;  // Reset failure counter on success
    }
}


// Replace your publishMqttData() function with this enhanced version:

void publishMqttData() {
    // Check if sensor is available before attempting to read
    if (!sensorAvailable) {
        Serial.println("Sensor unavailable - skipping temperature publish");
        return;
    }

    // Sensor data (existing)
    float tempC = max31856.readThermocoupleTemperature();
    float coldJunctionC = max31856.readCJTemperature();
    
    // Check for MAX31856 faults
    uint8_t fault = max31856.readFault();
    if (fault) {
        Serial.print("MAX31856 Fault: 0x");
        Serial.println(fault, HEX);
        if (fault & MAX31856_FAULT_CJRANGE) Serial.println("  - Cold Junction Range Fault");
        if (fault & MAX31856_FAULT_TCRANGE) Serial.println("  - Thermocouple Range Fault");
        if (fault & MAX31856_FAULT_CJHIGH)  Serial.println("  - Cold Junction High Fault");
        if (fault & MAX31856_FAULT_CJLOW)   Serial.println("  - Cold Junction Low Fault");
        if (fault & MAX31856_FAULT_TCHIGH)  Serial.println("  - Thermocouple High Fault");
        if (fault & MAX31856_FAULT_TCLOW)   Serial.println("  - Thermocouple Low Fault");
        if (fault & MAX31856_FAULT_OVUV)    Serial.println("  - Over/Under Voltage Fault");
        if (fault & MAX31856_FAULT_OPEN)    Serial.println("  - Thermocouple Open Fault");
        max31856.clearFault();
    }

    // Validate sensor readings
    if (isnan(tempC) || tempC < -100 || tempC > 1800) {
        Serial.print("Invalid thermocouple reading: ");
        Serial.println(tempC);
        return;
    }

    if (isnan(coldJunctionC) || coldJunctionC < -40 || coldJunctionC > 150) {
        Serial.print("Invalid cold junction reading: ");
        Serial.println(coldJunctionC);
        return;
    }

    int raw_adc = analogRead(FLAME_ADC_PIN);

    // Validate ADC reading
    if (raw_adc < 0 || raw_adc > 4095) {
        Serial.print("Invalid ADC reading: ");
        Serial.println(raw_adc);
        return;
    }

    float flame_voltage = ((raw_adc / 4095.0f) * 3.3f) * VOLTAGE_DIVIDER_RATIO;
    
    // Debug output every 10th reading (roughly once per second at 10Hz)
    static int debugCounter = 0;
    if (++debugCounter >= 10) {
        debugCounter = 0;
        Serial.print("Temp: ");
        Serial.print(tempC);
        Serial.print("C, CJ: ");
        Serial.print(coldJunctionC);
        Serial.print("C, ADC: ");
        Serial.print(raw_adc);
        Serial.print(", Flame: ");
        Serial.print(flame_voltage);
        Serial.println("V");
    }
    
    struct timeval tv;
    gettimeofday(&tv, NULL);
    unsigned long long time_ms = (unsigned long long)tv.tv_sec * 1000ULL + (unsigned long long)tv.tv_usec / 1000ULL;
    
    // Track packet stats (mutex protected)
    if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
        netMetrics.packetsSent++;
        xSemaphoreGive(metricsMutex);
    }

    // Use fixed buffer to avoid heap fragmentation (runs at 10Hz)
    char sensorPayload[200];
    snprintf(sensorPayload, sizeof(sensorPayload),
        "{\"furnace_temp\":%.2f,\"cold_junction\":%.2f,\"flame_voltage\":%.3f,\"timestamp\":%llu}",
        tempC, coldJunctionC, flame_voltage, time_ms);

    mqttClient.beginMessage("furnace/data", false, 0);
    mqttClient.print(sensorPayload);
    if (!mqttClient.endMessage()) {
        Serial.println("MQTT publish failed!");
        if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
            netMetrics.packetsLost++;
            xSemaphoreGive(metricsMutex);
        }
    }
    
    // Network metrics (every 5 seconds)
    unsigned long currentMillis = millis();
    if (currentMillis - lastNetworkMetricsTime >= networkMetricsInterval) {
        publishNetworkMetrics();
        lastNetworkMetricsTime = currentMillis;
    }
}

void publishNetworkMetrics() {
    updateNetworkMetrics();

    // Copy metrics in single critical section (minimize lock time)
    NetworkMetrics snapshot;
    if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
        snapshot = netMetrics;
        xSemaphoreGive(metricsMutex);
    } else {
        return;  // Failed to get mutex, skip this publish
    }

    // Calculate packet loss from snapshot
    float packetLoss = 0.0f;
    if (snapshot.packetsSent > 0) {
        packetLoss = ((float)snapshot.packetsLost / (float)snapshot.packetsSent) * 100.0f;
    }

    // Use fixed buffer to avoid heap fragmentation
    char networkPayload[400];
    snprintf(networkPayload, sizeof(networkPayload),
        "{\"wifi_rssi\":%d,\"connection_uptime_ms\":%lu,\"mqtt_reconnects\":%lu,"
        "\"wifi_reconnects\":%lu,\"packets_sent\":%lu,\"packets_lost\":%lu,"
        "\"packet_loss_rate\":%.2f,\"network_latency_ms\":%lu,"
        "\"connection_state\":\"%s\",\"state_changes\":%lu}",
        snapshot.rssi, snapshot.connectionUptime, snapshot.mqttReconnectCount,
        snapshot.wifiReconnectCount, snapshot.packetsSent, snapshot.packetsLost,
        packetLoss, snapshot.lastLatencyMs,
        snapshot.lastConnectionState, snapshot.stateChangeCount);

    mqttClient.beginMessage("furnace/network_metrics", false, 0);
    mqttClient.print(networkPayload);
    mqttClient.endMessage();
    
    // Ping test for latency
    performLatencyTest();
}

void updateNetworkMetrics() {
    // Gather data outside critical section
    int rssi = WiFi.RSSI();
    wl_status_t currentStatus = WiFi.status();
    unsigned long currentTime = millis();

    static wl_status_t lastStatus = WL_DISCONNECTED;
    bool stateChanged = (currentStatus != lastStatus);

    // Update metrics in critical section
    if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
        // WiFi RSSI
        netMetrics.rssi = rssi;

        // Connection uptime
        if (currentStatus == WL_CONNECTED && netMetrics.lastConnectTime > 0) {
            netMetrics.connectionUptime = currentTime - netMetrics.lastConnectTime;
        }

        // Connection state tracking
        if (stateChanged) {
            lastStatus = currentStatus;

            // Get state string literal (no heap allocation)
            const char* stateStr = getWiFiStatusString();
            strncpy(netMetrics.lastConnectionState, stateStr,
                    sizeof(netMetrics.lastConnectionState) - 1);
            netMetrics.lastConnectionState[sizeof(netMetrics.lastConnectionState) - 1] = '\0';

            netMetrics.stateChangeCount++;

            if (currentStatus == WL_CONNECTED) {
                netMetrics.lastConnectTime = currentTime;
            }
        }

        xSemaphoreGive(metricsMutex);
    }
}

const char* getWiFiStatusString() {
    switch(WiFi.status()) {
        case WL_CONNECTED:       return "CONNECTED";
        case WL_DISCONNECTED:    return "DISCONNECTED";
        case WL_CONNECTION_LOST: return "CONNECTION_LOST";
        case WL_CONNECT_FAILED:  return "CONNECT_FAILED";
        case WL_NO_SSID_AVAIL:   return "NO_SSID_AVAIL";
        default:                 return "UNKNOWN";
    }
}


void performLatencyTest() {
    // Reset if pong timeout exceeded (5 seconds)
    const unsigned long PONG_TIMEOUT_MS = 5000;
    if (awaitingPong && (millis() - pingStartTime > PONG_TIMEOUT_MS)) {
        consecutivePongFailures++;
        Serial.print("Pong timeout - resetting latency test (failure ");
        Serial.print(consecutivePongFailures);
        Serial.print("/");
        Serial.print(MAX_PONG_FAILURES);
        Serial.println(")");
        awaitingPong = false;
        
        if (xSemaphoreTake(metricsMutex, portMAX_DELAY) == pdTRUE) {
            netMetrics.lastLatencyMs = 0;  // Indicate timeout
            xSemaphoreGive(metricsMutex);
        }
    }

    if (!awaitingPong) {
        pingStartTime = millis();
        awaitingPong = true;

        // Send ping message
        mqttClient.beginMessage("furnace/ping", false, 0);
        mqttClient.print("{\"ping\":" + String(pingStartTime) + "}");
        if (!mqttClient.endMessage()) {
            Serial.println("Failed to send ping!");
        }
    }
}
