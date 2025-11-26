"""
Unified Furnace Monitoring System
==================================

Combines flame dynamics monitoring and 4-20mA control signal monitoring
with WiFi connectivity for MicroPython on ESP32-S3.

Hardware:
- ADS1115 #1 (0x48): I2C0 on GPIO 17/18 - Flame sensor
- ADS1115 #2 (0x49): I2C1 on GPIO 41/42 - Control signal

Usage:
    from furnace_monitor import FurnaceMonitor

    # With WiFi and UDP output to Vector
    fm = FurnaceMonitor(
        ssid="YOUR_SSID",
        password="YOUR_PASSWORD",
        vector_host="192.168.1.100",  # Pi IP address
        vector_port=9000
    )
    fm.init()
    fm.monitor(duration_sec=300)

    # Without UDP (console output only)
    fm = FurnaceMonitor()
    fm.init()
    fm.monitor()
"""

import time
import math
import network
import socket
import json
from machine import Pin, I2C
from ads1115 import ADS1115


def setup_wifi(ssid, password):
    """
    Connect to WiFi with brownout prevention.

    Args:
        ssid: Network SSID
        password: Network password

    Returns:
        bool: True if connected
    """
    print(f"\n--- Connecting to {ssid} (Anti-Brownout Mode) ---")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)

    # THE MAGIC FIX
    # 8.5 dBm is plenty for a house.
    try:
        wlan.config(txpower=8.5)
        actual_power = wlan.config("txpower")
        print(f"TX Power capped at: {actual_power} dBm")
    except Exception as e:
        print(f"Power setting failed: {e}")

    try:
        print("Handshaking...")
        wlan.connect(ssid, password)

        # Wait for connection
        timeout = 10
        while timeout > 0:
            if wlan.isconnected():
                break
            time.sleep(1)
            timeout -= 1

        if not wlan.isconnected():
            print("\nFAILURE: Connection timeout")
            return False

        print("\nSUCCESS! Connected.")
        ip_info = wlan.ifconfig()
        print(f"IP Address: {ip_info[0]}")
        print(f"Signal Strength: {wlan.status('rssi')} dBm")

        # Test internet connectivity
        print("Testing internet...")
        try:
            s = socket.socket()
            s.settimeout(3.0)
            start = time.ticks_ms()
            try:
                s.connect(('8.8.8.8', 53))
                ping_time = time.ticks_diff(time.ticks_ms(), start)
                print(f"Internet OK: {ping_time} ms to Google DNS")
            finally:
                s.close()
        except Exception as e:
            print(f"Internet test failed: {e}")

        return True

    except Exception as e:
        print(f"\nFAILURE: {e}")
        return False


class FurnaceMonitor:
    """
    Combined flame and control signal monitoring system.

    Monitors:
    - Flame dynamics (UV sensor via ADS1115 #1)
    - Control signal 4-20mA (via ADS1115 #2)
    """

    # Pin assignments
    FLAME_I2C_BUS = 0
    FLAME_SDA = 17
    FLAME_SCL = 18
    FLAME_ADDR = 0x48
    FLAME_CHANNEL = 0

    CONTROL_I2C_BUS = 1
    CONTROL_SDA = 41
    CONTROL_SCL = 42
    CONTROL_ADDR = 0x49

    # Flame analysis parameters
    SAMPLE_RATE = 860
    FLICKER_FREQ_MIN = 1
    FLICKER_FREQ_MAX = 20
    FLICKER_PEAK_NOMINAL = 10
    THERMOACOUSTIC_FREQ_MIN = 30
    THERMOACOUSTIC_FREQ_MAX = 400

    # Signal validation
    MIN_SIGNAL_RMS = 0.001  # Minimum RMS to consider valid signal (not noise)

    # Control signal parameters
    SENSE_RESISTANCE = 100.0
    MA_MIN = 4.0
    MA_MAX = 20.0

    def __init__(self, ssid=None, password=None, vector_host=None, vector_port=9000):
        """
        Initialize furnace monitor.

        Args:
            ssid: WiFi SSID (optional)
            password: WiFi password (optional)
            vector_host: Vector server IP address for UDP output (optional)
            vector_port: Vector UDP port (default 9000)
        """
        self.ssid = ssid
        self.password = password
        self.vector_host = vector_host
        self.vector_port = vector_port

        self.flame_i2c = None
        self.flame_adc = None
        self.control_i2c = None
        self.control_adc = None

        self.wifi_connected = False
        self.udp_sock = None
        self.last_wifi_check = 0  # Track when we last attempted WiFi reconnection

    def init(self, max_retries=3):
        """
        Initialize all hardware with retry logic.

        Args:
            max_retries: Maximum initialization attempts per component
        """
        print("\n=== Furnace Monitor Initialization ===")

        # WiFi setup with retry
        if self.ssid and self.password:
            for attempt in range(max_retries):
                try:
                    self.wifi_connected = setup_wifi(self.ssid, self.password)
                    if self.wifi_connected:
                        break
                except Exception as e:
                    print(f"WiFi setup attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
        else:
            print("No WiFi credentials provided, skipping WiFi setup")

        print("\n--- Hardware Setup ---")

        # Initialize flame sensor I2C and ADC with retry
        print(f"Flame sensor (0x{self.FLAME_ADDR:02X} on GPIO {self.FLAME_SDA}/{self.FLAME_SCL})...")
        for attempt in range(max_retries):
            try:
                self.flame_i2c = I2C(self.FLAME_I2C_BUS,
                                    scl=Pin(self.FLAME_SCL),
                                    sda=Pin(self.FLAME_SDA),
                                    freq=400000)

                # Verify device presence
                devices = self.flame_i2c.scan()
                if self.FLAME_ADDR not in devices:
                    raise RuntimeError(f"Flame ADC not found at 0x{self.FLAME_ADDR:02X}, found: {[hex(d) for d in devices]}")

                self.flame_adc = ADS1115(self.flame_i2c, address=self.FLAME_ADDR)
                self.flame_adc.init(gain=ADS1115.GAIN_4096, rate=ADS1115.RATE_860)
                print("  Flame sensor initialized")
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Failed to initialize flame sensor after {max_retries} attempts") from e

        # Initialize control signal I2C and ADC with retry
        print(f"Control signal (0x{self.CONTROL_ADDR:02X} on GPIO {self.CONTROL_SDA}/{self.CONTROL_SCL})...")
        for attempt in range(max_retries):
            try:
                self.control_i2c = I2C(self.CONTROL_I2C_BUS,
                                      scl=Pin(self.CONTROL_SCL),
                                      sda=Pin(self.CONTROL_SDA),
                                      freq=400000)

                # Verify device presence
                devices = self.control_i2c.scan()
                if self.CONTROL_ADDR not in devices:
                    raise RuntimeError(f"Control ADC not found at 0x{self.CONTROL_ADDR:02X}, found: {[hex(d) for d in devices]}")

                self.control_adc = ADS1115(self.control_i2c, address=self.CONTROL_ADDR)
                self.control_adc.init(gain=ADS1115.GAIN_2048, rate=ADS1115.RATE_128)
                print("  Control signal initialized")
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Failed to initialize control signal after {max_retries} attempts") from e

        # Setup UDP socket for data transmission with retry
        if self.wifi_connected and self.vector_host:
            for attempt in range(max_retries):
                try:
                    self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    print(f"UDP output enabled: {self.vector_host}:{self.vector_port}")
                    break
                except Exception as e:
                    print(f"UDP socket attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)

        print("\n=== Initialization Complete ===\n")

    def cleanup(self):
        """
        Clean up resources before restart.
        """
        print("Cleaning up resources...")

        # Close UDP socket
        if self.udp_sock:
            try:
                self.udp_sock.close()
                print("  UDP socket closed")
            except Exception as e:
                print(f"  UDP socket close failed: {e}")
            self.udp_sock = None

        # Deinit I2C buses
        if self.flame_i2c:
            try:
                self.flame_i2c.deinit()
                print("  Flame I2C deinitialized")
            except Exception as e:
                print(f"  Flame I2C deinit failed: {e}")
            self.flame_i2c = None
            self.flame_adc = None

        if self.control_i2c:
            try:
                self.control_i2c.deinit()
                print("  Control I2C deinitialized")
            except Exception as e:
                print(f"  Control I2C deinit failed: {e}")
            self.control_i2c = None
            self.control_adc = None

        # Disconnect WiFi
        if self.wifi_connected:
            try:
                wlan = network.WLAN(network.STA_IF)
                wlan.disconnect()
                wlan.active(False)
                print("  WiFi disconnected")
            except Exception as e:
                print(f"  WiFi disconnect failed: {e}")
            self.wifi_connected = False

        print("Cleanup complete")

    def read_flame_spectrum(self, samples=512):
        """
        Capture flame spectrum.

        Args:
            samples: Number of samples (power of 2)

        Returns:
            tuple: (frequencies, magnitudes)
        """
        # Capture data
        data = self.flame_adc.capture(samples=samples, channel=self.FLAME_CHANNEL)

        # Remove DC offset
        mean = sum(data) / len(data)
        data = [x - mean for x in data]

        # Hanning window
        n = len(data)
        for i in range(n):
            window = 0.5 * (1 - math.cos(2 * math.pi * i / (n - 1)))
            data[i] *= window

        # FFT
        real, imag = self._fft(data)

        # Magnitude spectrum
        n_freq = n // 2
        magnitudes = []
        frequencies = []
        freq_resolution = self.SAMPLE_RATE / n

        for i in range(n_freq):
            mag = math.sqrt(real[i]**2 + imag[i]**2) / n
            magnitudes.append(mag)
            frequencies.append(i * freq_resolution)

        return frequencies, magnitudes

    def analyze_flame(self, frequencies, magnitudes):
        """
        Analyze flame spectrum.

        Returns:
            dict: Analysis results
        """
        results = {
            'flicker_peak_freq': 0,
            'flicker_peak_mag': 0,
            'thermoacoustic_peak_freq': 0,
            'thermoacoustic_peak_mag': 0,
            'rms_amplitude': 0,
            'status': 'unknown',
            'warnings': []
        }

        # Find flicker peak (1-20 Hz)
        for f, m in zip(frequencies, magnitudes):
            if self.FLICKER_FREQ_MIN <= f <= self.FLICKER_FREQ_MAX:
                if m > results['flicker_peak_mag']:
                    results['flicker_peak_mag'] = m
                    results['flicker_peak_freq'] = f

        # Find thermoacoustic peak (30-400 Hz)
        for f, m in zip(frequencies, magnitudes):
            if self.THERMOACOUSTIC_FREQ_MIN <= f <= self.THERMOACOUSTIC_FREQ_MAX:
                if m > results['thermoacoustic_peak_mag']:
                    results['thermoacoustic_peak_mag'] = m
                    results['thermoacoustic_peak_freq'] = f

        # RMS amplitude
        rms = math.sqrt(sum(m**2 for m in magnitudes) / len(magnitudes)) if magnitudes else 0.0
        results['rms_amplitude'] = rms

        # Check for minimum signal threshold (reject noise on floating inputs)
        if rms < self.MIN_SIGNAL_RMS:
            results['status'] = 'no_signal'
            results['warnings'].append(f'Signal too weak (RMS={rms:.6f}) - no flame or sensor disconnected')
            return results

        # Status determination
        flicker_freq = results['flicker_peak_freq']
        if flicker_freq > 0:
            if 8 <= flicker_freq <= 12:
                results['status'] = 'normal'
            elif flicker_freq < 5:
                results['status'] = 'unstable'
                results['warnings'].append('Low flicker - possible flame lift')
            else:
                results['status'] = 'check'
        else:
            results['status'] = 'no_signal'
            results['warnings'].append('No flicker detected')

        # Check thermoacoustic
        if results['thermoacoustic_peak_mag'] > results['flicker_peak_mag'] * 0.5:
            results['warnings'].append(f"Thermoacoustic at {results['thermoacoustic_peak_freq']:.1f} Hz")

        return results

    def read_control_signal(self):
        """
        Read 4-20mA control signal with range validation.

        Returns:
            tuple: (voltage, percent, milliamps)

        Raises:
            ValueError: If voltage reading is out of expected range
        """
        voltage = self.control_adc.read_differential(pos=0, neg=1)

        # Validate reading - 4-20mA across 100Ω = 0.4V-2.0V expected
        # Allow small margin for ADC tolerance
        if voltage < -0.1 or voltage > 2.5:
            raise ValueError(f"Control signal out of range: {voltage:.3f}V (expect 0.4-2.0V)")

        ma = (voltage / self.SENSE_RESISTANCE) * 1000.0

        if ma < self.MA_MIN:
            percent = 0.0
        elif ma > self.MA_MAX:
            percent = 100.0
        else:
            percent = ((ma - self.MA_MIN) / (self.MA_MAX - self.MA_MIN)) * 100.0

        return voltage, percent, ma

    def send_data(self, timestamp, flame_analysis, ctrl_voltage, ctrl_percent, ctrl_ma):
        """
        Send data via UDP to Vector (non-blocking).

        Args:
            timestamp: Unix timestamp
            flame_analysis: Flame analysis dict
            ctrl_voltage: Control signal voltage
            ctrl_percent: Control signal percent
            ctrl_ma: Control signal milliamps
        """
        if not self.udp_sock:
            return

        # Check WiFi status without blocking reconnection
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            self.wifi_connected = False
            return  # Skip send, reconnection will happen in monitor loop

        try:
            # JSON format for Vector
            data = {
                "timestamp": timestamp,
                "flame": {
                    "status": flame_analysis['status'],
                    "flicker_freq": flame_analysis['flicker_peak_freq'],
                    "flicker_mag": flame_analysis['flicker_peak_mag'],
                    "thermo_freq": flame_analysis['thermoacoustic_peak_freq'],
                    "thermo_mag": flame_analysis['thermoacoustic_peak_mag'],
                    "rms": flame_analysis['rms_amplitude']
                },
                "control": {
                    "voltage": ctrl_voltage,
                    "percent": ctrl_percent,
                    "milliamps": ctrl_ma
                }
            }

            # Convert to JSON string
            payload = json.dumps(data)

            # Send UDP packet
            self.udp_sock.sendto(payload.encode(), (self.vector_host, self.vector_port))

        except Exception as e:
            print(f"UDP send failed: {e}")

    def monitor(self, duration_sec=60, interval_sec=1, watchdog=None):
        """
        Continuous monitoring of both systems.

        Args:
            duration_sec: Total monitoring duration
            interval_sec: Time between readings
            watchdog: Optional WDT object to feed during monitoring
        """
        print(f"\n=== Monitoring for {duration_sec} seconds ===")
        print("-" * 80)

        start_time = time.time()
        error_count = 0
        consecutive_errors = 0

        try:
            while (time.time() - start_time) < duration_sec:
                timestamp = time.time()
                elapsed = timestamp - start_time

                # Feed watchdog at start of each loop iteration
                if watchdog:
                    try:
                        watchdog.feed()
                    except Exception as e:
                        print(f"! Watchdog feed failed: {e}")

                # Check WiFi and attempt reconnection if needed (outside sensor read path)
                if not self.wifi_connected and self.ssid:
                    # Limit reconnection attempts (every 10 seconds)
                    if timestamp - self.last_wifi_check > 10:
                        self.last_wifi_check = timestamp
                        print("WiFi disconnected, attempting reconnect...")
                        try:
                            self.wifi_connected = setup_wifi(self.ssid, self.password)
                        except Exception as e:
                            print(f"! WiFi reconnect failed: {e}")

                # Initialize default values in case of errors
                ctrl_voltage, ctrl_percent, ctrl_ma = 0.0, 0.0, 0.0
                flame_analysis = {
                    'status': 'error',
                    'flicker_peak_freq': 0,
                    'flicker_peak_mag': 0,
                    'thermoacoustic_peak_freq': 0,
                    'thermoacoustic_peak_mag': 0,
                    'rms_amplitude': 0,
                    'warnings': ['Sensor read failed']
                }

                loop_success = True

                # Read control signal with error handling
                try:
                    ctrl_voltage, ctrl_percent, ctrl_ma = self.read_control_signal()
                except Exception as e:
                    print(f"! Control signal read failed: {e}")
                    error_count += 1
                    loop_success = False

                # Read flame spectrum with error handling
                try:
                    freqs, mags = self.read_flame_spectrum(samples=512)
                    flame_analysis = self.analyze_flame(freqs, mags)
                except Exception as e:
                    print(f"! Flame sensor read failed: {e}")
                    error_count += 1
                    loop_success = False

                # Send data via UDP with error handling
                try:
                    self.send_data(timestamp, flame_analysis, ctrl_voltage, ctrl_percent, ctrl_ma)
                except Exception as e:
                    print(f"! UDP send failed: {e}")
                    error_count += 1
                    loop_success = False

                # Track consecutive errors and attempt recovery
                if loop_success:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 10:
                        print(f"! WARNING: {consecutive_errors} consecutive errors - attempting hardware recovery")
                        try:
                            # Re-initialize I2C buses to clear potential lockup
                            self.init(max_retries=1)
                            consecutive_errors = 0
                            print("  Hardware recovery successful")
                        except Exception as e:
                            print(f"! Hardware recovery failed: {e}")

                # Display results
                status = flame_analysis['status'].upper()
                flicker = flame_analysis['flicker_peak_freq']
                thermo = flame_analysis['thermoacoustic_peak_freq']

                indicator = '+' if flame_analysis['status'] == 'normal' else '!'

                print(f"[{elapsed:6.1f}s] {indicator} {status:10s} | "
                      f"Flicker: {flicker:5.1f}Hz | "
                      f"Thermo: {thermo:5.1f}Hz | "
                      f"Demand: {ctrl_percent:5.1f}% ({ctrl_ma:.2f}mA)")

                # Warnings
                for warning in flame_analysis['warnings']:
                    print(f"         ! {warning}")

                # Sleep in small increments to feed watchdog
                sleep_remaining = interval_sec
                while sleep_remaining > 0:
                    sleep_chunk = min(sleep_remaining, 0.5)  # 500ms max between feeds
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                    if watchdog:
                        try:
                            watchdog.feed()
                        except Exception:
                            pass

        except KeyboardInterrupt:
            print("\nMonitoring stopped")

        print("-" * 80)
        print(f"=== Monitoring Complete (total errors: {error_count}) ===\n")

    def _fft(self, x):
        """Cooley-Tukey FFT."""
        n = len(x)

        if n & (n - 1) != 0:
            raise ValueError("FFT length must be power of 2")

        real = list(x)
        imag = [0.0] * n

        # Bit-reversal
        j = 0
        for i in range(1, n):
            bit = n >> 1
            while j >= bit:
                j -= bit
                bit >>= 1
            j += bit
            if i < j:
                real[i], real[j] = real[j], real[i]

        # Cooley-Tukey
        length = 2
        while length <= n:
            angle = -2 * math.pi / length
            wpr = math.cos(angle)
            wpi = math.sin(angle)

            for start in range(0, n, length):
                wr = 1.0
                wi = 0.0

                for j in range(length // 2):
                    i1 = start + j
                    i2 = i1 + length // 2

                    tr = wr * real[i2] - wi * imag[i2]
                    ti = wr * imag[i2] + wi * real[i2]

                    real[i2] = real[i1] - tr
                    imag[i2] = imag[i1] - ti
                    real[i1] = real[i1] + tr
                    imag[i1] = imag[i1] + ti

                    wr_new = wr * wpr - wi * wpi
                    wi = wr * wpi + wi * wpr
                    wr = wr_new

            length *= 2

        return real, imag


def quick_test():
    """Quick test without WiFi."""
    print("=== Quick Test ===")

    fm = FurnaceMonitor()
    fm.init()

    print("\nTesting control signal...")
    v, p, ma = fm.read_control_signal()
    print(f"  {v:.3f}V = {ma:.2f}mA = {p:.1f}%")

    print("\nTesting flame sensor...")
    freqs, mags = fm.read_flame_spectrum(samples=512)
    analysis = fm.analyze_flame(freqs, mags)
    print(f"  Status: {analysis['status']}")
    print(f"  Flicker: {analysis['flicker_peak_freq']:.1f} Hz")
    print(f"  Thermoacoustic: {analysis['thermoacoustic_peak_freq']:.1f} Hz")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    quick_test()
