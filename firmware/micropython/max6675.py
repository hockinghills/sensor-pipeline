# max6675.py - MicroPython driver for MAX6675 Type-K thermocouple
#
# Wiring (3.3V):
#   VCC  -> 3V3
#   GND  -> GND
#   SCK  -> GPIO 12 (shared)
#   SO   -> GPIO 13 (shared, aka MISO)
#   CS   -> GPIO 14 (bottom) or GPIO 15 (top)

from machine import Pin, SPI
import time


class MAX6675:
    """
    MAX6675 Type-K thermocouple interface.

    SPI Requirements:
    - Mode 0 (CPOL=0, CPHA=0)
    - Frequency: 1-4 MHz typical
    - MSB first (default)

    Temperature range: 0-1024°C (32-1875°F)
    Resolution: 0.25°C

    Detects open/disconnected thermocouple.
    """

    def __init__(self, spi, cs_pin):
        """
        Initialize MAX6675.

        Args:
            spi: Initialized SPI bus object (shared between sensors)
                 MUST be configured to mode 0 (CPOL=0, CPHA=0)
            cs_pin: GPIO number for chip select (unique per sensor)

        Note:
            MAX6675 requires SPI mode 0, different from MAX31856 (mode 1/3).
            Configure SPI before passing to this constructor.

        Raises:
            RuntimeError: If SPI communication fails during init test
        """
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT)
        self.cs.value(1)  # Deselect (active low)
        self._last_read = 0

        # Test communication - MAX6675 powers up ready to read
        try:
            time.sleep_ms(250)  # Wait for first conversion
            _ = self.read_raw()
        except Exception as e:
            raise RuntimeError(f"MAX6675 initialization failed: {e}") from e

    def read_raw(self):
        """
        Read raw 16-bit value from MAX6675.

        MAX6675 requires 220ms between conversions.
        """
        # Enforce minimum delay between reads (250ms with safety margin)
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._last_read)
        if elapsed < 250:
            time.sleep_ms(250 - elapsed)

        try:
            self.cs.value(0)
            time.sleep_us(10)
            data = self.spi.read(2)
            self.cs.value(1)
        except Exception as e:
            self.cs.value(1)  # Ensure CS released on error
            raise RuntimeError(f"SPI read failed: {e}") from e

        self._last_read = time.ticks_ms()
        return (data[0] << 8) | data[1]

    def read(self):
        """
        Read temperature in Celsius.

        Returns:
            float: Temperature in °C

        Raises:
            RuntimeError: If thermocouple is disconnected or data invalid
        """
        raw = self.read_raw()

        # Bit 15 = dummy bit (should be 0)
        if raw & 0x8000:
            raise RuntimeError("Invalid MAX6675 data (bit 15 set)")

        # Bit 2 = thermocouple open detection
        if raw & 0x04:
            raise RuntimeError("Thermocouple disconnected")

        # Bit 1 = device ID (should be 0 for MAX6675, bit 0 is undefined/tri-state)
        if raw & 0x02:
            raise RuntimeError("Invalid MAX6675 device ID")

        # Bits 14-3 = temperature, 0.25°C per LSB
        temp_c = (raw >> 3) * 0.25
        return temp_c

    def read_f(self):
        """
        Read temperature in Fahrenheit.

        Returns:
            float: Temperature in °F

        Raises:
            RuntimeError: If thermocouple is disconnected
        """
        return self.read() * 9.0 / 5.0 + 32.0

    def read_safe(self):
        """
        Read temperature with error handling.

        Returns:
            tuple: (temp_c, temp_f, connected)
                - temp_c: Temperature in °C (0.0 if disconnected)
                - temp_f: Temperature in °F (0.0 if disconnected)
                - connected: True if thermocouple is connected
        """
        try:
            temp_c = self.read()
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return (temp_c, temp_f, True)
        except Exception:
            return (0.0, 0.0, False)
