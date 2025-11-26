"""
ADS1115 16-Bit ADC Driver for MicroPython
==========================================

For ESP32-S3 with standard ADS1115 breakout boards.

Usage:
    from machine import I2C, Pin
    from ads1115 import ADS1115
    
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400000)
    adc = ADS1115(i2c)
    
    # Single-ended read
    voltage = adc.read_voltage(channel=0)
    
    # Differential read
    voltage = adc.read_differential(pos=0, neg=1)
    
    # Continuous capture for FFT
    data = adc.capture(samples=512)

Author: Claude + Willie (Lyon's Pyre Glasswerks)
License: Do whatever you want with it
Version: 1.0
"""

import time
from micropython import const

# Register addresses
_REG_CONVERSION = const(0x00)
_REG_CONFIG = const(0x01)
_REG_LO_THRESH = const(0x02)
_REG_HI_THRESH = const(0x03)

# Config register bits
_OS_START = const(0x8000)      # Start single conversion
_OS_BUSY = const(0x0000)       # Conversion in progress
_OS_READY = const(0x8000)      # Conversion complete

# MUX settings (bits 14:12)
_MUX_DIFF_01 = const(0x0000)   # AIN0 - AIN1
_MUX_DIFF_03 = const(0x1000)   # AIN0 - AIN3
_MUX_DIFF_13 = const(0x2000)   # AIN1 - AIN3
_MUX_DIFF_23 = const(0x3000)   # AIN2 - AIN3
_MUX_SINGLE_0 = const(0x4000)  # AIN0 vs GND
_MUX_SINGLE_1 = const(0x5000)  # AIN1 vs GND
_MUX_SINGLE_2 = const(0x6000)  # AIN2 vs GND
_MUX_SINGLE_3 = const(0x7000)  # AIN3 vs GND

# PGA settings (bits 11:9)
_PGA_6144 = const(0x0000)      # ±6.144V (LSB = 187.5µV)
_PGA_4096 = const(0x0200)      # ±4.096V (LSB = 125µV)
_PGA_2048 = const(0x0400)      # ±2.048V (LSB = 62.5µV) - default
_PGA_1024 = const(0x0600)      # ±1.024V (LSB = 31.25µV)
_PGA_512 = const(0x0800)       # ±0.512V (LSB = 15.625µV)
_PGA_256 = const(0x0A00)       # ±0.256V (LSB = 7.8125µV)

# Mode (bit 8)
_MODE_CONTINUOUS = const(0x0000)
_MODE_SINGLE = const(0x0100)

# Data rate settings (bits 7:5)
_DR_8 = const(0x0000)          # 8 SPS
_DR_16 = const(0x0020)         # 16 SPS
_DR_32 = const(0x0040)         # 32 SPS
_DR_64 = const(0x0060)         # 64 SPS
_DR_128 = const(0x0080)        # 128 SPS - default
_DR_250 = const(0x00A0)        # 250 SPS
_DR_475 = const(0x00C0)        # 475 SPS
_DR_860 = const(0x00E0)        # 860 SPS

# Comparator disable
_COMP_DISABLE = const(0x0003)


class ADS1115:
    """
    ADS1115 16-bit ADC driver.
    
    Attributes:
        address: I2C address (0x48-0x4B)
        gain: Current PGA setting as FSR voltage
        data_rate: Current sample rate in SPS
    """
    
    # Public constants for configuration
    GAIN_6144 = _PGA_6144
    GAIN_4096 = _PGA_4096
    GAIN_2048 = _PGA_2048
    GAIN_1024 = _PGA_1024
    GAIN_512 = _PGA_512
    GAIN_256 = _PGA_256
    
    RATE_8 = _DR_8
    RATE_16 = _DR_16
    RATE_32 = _DR_32
    RATE_64 = _DR_64
    RATE_128 = _DR_128
    RATE_250 = _DR_250
    RATE_475 = _DR_475
    RATE_860 = _DR_860
    
    # FSR values for voltage conversion
    _FSR_MAP = {
        _PGA_6144: 6.144,
        _PGA_4096: 4.096,
        _PGA_2048: 2.048,
        _PGA_1024: 1.024,
        _PGA_512: 0.512,
        _PGA_256: 0.256,
    }
    
    # Conversion times in ms (plus margin)
    _RATE_MS = {
        _DR_8: 130,
        _DR_16: 65,
        _DR_32: 33,
        _DR_64: 17,
        _DR_128: 9,
        _DR_250: 5,
        _DR_475: 3,
        _DR_860: 2,
    }
    
    def __init__(self, i2c, address=0x48):
        """
        Initialize ADS1115 driver.
        
        Args:
            i2c: Configured I2C object
            address: 7-bit I2C address (0x48-0x4B)
        """
        self.i2c = i2c
        self.address = address
        self._gain = _PGA_4096
        self._rate = _DR_860
        self._buf2 = bytearray(2)
        
    def init(self, gain=None, rate=None):
        """
        Initialize and verify the ADS1115.
        
        Args:
            gain: PGA setting (default GAIN_4096)
            rate: Data rate (default RATE_860)
        
        Raises:
            RuntimeError: If device not found
        """
        if gain is not None:
            self._gain = gain
        if rate is not None:
            self._rate = rate
            
        # Verify device is present
        devices = self.i2c.scan()
        if self.address not in devices:
            raise RuntimeError(f"ADS1115 not found at 0x{self.address:02X}")
        
        # Do a test read to verify communication
        try:
            self._read_config()
        except OSError as e:
            raise RuntimeError(f"ADS1115 communication failed: {e}") from e
        
        print(f"ADS1115 initialized at 0x{self.address:02X}")
        print(f"  FSR: ±{self._FSR_MAP[self._gain]}V")
        print(f"  Rate: {self._get_rate_sps()} SPS")
    
    def _get_rate_sps(self):
        """Get current rate in SPS."""
        rate_map = {
            _DR_8: 8, _DR_16: 16, _DR_32: 32, _DR_64: 64,
            _DR_128: 128, _DR_250: 250, _DR_475: 475, _DR_860: 860
        }
        return rate_map.get(self._rate, 0)
    
    def _write_config(self, config):
        """Write config register."""
        self._buf2[0] = (config >> 8) & 0xFF
        self._buf2[1] = config & 0xFF
        try:
            self.i2c.writeto_mem(self.address, _REG_CONFIG, self._buf2)
        except OSError as e:
            raise RuntimeError(f"ADS1115 I2C write failed: {e}") from e
    
    def _read_config(self):
        """Read config register."""
        try:
            self.i2c.readfrom_mem_into(self.address, _REG_CONFIG, self._buf2)
        except OSError as e:
            raise RuntimeError(f"ADS1115 I2C read failed: {e}") from e
        return (self._buf2[0] << 8) | self._buf2[1]
    
    def _read_conversion(self):
        """Read conversion register as signed 16-bit."""
        try:
            self.i2c.readfrom_mem_into(self.address, _REG_CONVERSION, self._buf2)
        except OSError as e:
            raise RuntimeError(f"ADS1115 I2C read failed: {e}") from e
        value = (self._buf2[0] << 8) | self._buf2[1]
        if value >= 0x8000:
            value -= 0x10000
        return value
    
    def _wait_ready(self, timeout_ms=200):
        """Wait for conversion to complete."""
        start = time.ticks_ms()
        while True:
            config = self._read_config()
            if config & _OS_READY:
                return True
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise RuntimeError("ADS1115 conversion timeout")
            time.sleep_ms(1)
    
    def read_raw(self, channel=0):
        """
        Read raw ADC value from single-ended channel.
        
        Args:
            channel: Channel 0-3
        
        Returns:
            int: Signed 16-bit value
        """
        mux = (_MUX_SINGLE_0 + (channel << 12))
        config = (_OS_START | mux | self._gain | 
                  _MODE_SINGLE | self._rate | _COMP_DISABLE)
        
        self._write_config(config)
        self._wait_ready()
        return self._read_conversion()
    
    def read_voltage(self, channel=0):
        """
        Read voltage from single-ended channel.
        
        Args:
            channel: Channel 0-3
        
        Returns:
            float: Voltage in volts
        """
        raw = self.read_raw(channel)
        fsr = self._FSR_MAP[self._gain]
        return (raw / 32768.0) * fsr
    
    def read_differential_raw(self, pos=0, neg=1):
        """
        Read raw ADC value from differential inputs.
        
        Args:
            pos: Positive input (0, 1, 2, or 3)
            neg: Negative input (1 or 3 depending on pos)
        
        Returns:
            int: Signed 16-bit value
        """
        # Determine MUX setting based on pos/neg combination
        if pos == 0 and neg == 1:
            mux = _MUX_DIFF_01
        elif pos == 0 and neg == 3:
            mux = _MUX_DIFF_03
        elif pos == 1 and neg == 3:
            mux = _MUX_DIFF_13
        elif pos == 2 and neg == 3:
            mux = _MUX_DIFF_23
        else:
            raise ValueError(f"Invalid differential pair: AIN{pos}-AIN{neg}")
        
        config = (_OS_START | mux | self._gain |
                  _MODE_SINGLE | self._rate | _COMP_DISABLE)
        
        self._write_config(config)
        self._wait_ready()
        return self._read_conversion()
    
    def read_differential(self, pos=0, neg=1):
        """
        Read voltage from differential inputs.
        
        Args:
            pos: Positive input (0, 1, 2, or 3)
            neg: Negative input (1 or 3 depending on pos)
        
        Returns:
            float: Voltage in volts
        """
        raw = self.read_differential_raw(pos, neg)
        fsr = self._FSR_MAP[self._gain]
        return (raw / 32768.0) * fsr
    
    def set_gain(self, gain):
        """Set PGA gain."""
        self._gain = gain
    
    def set_rate(self, rate):
        """Set data rate."""
        self._rate = rate
    
    def capture(self, samples, channel=0):
        """
        Capture multiple samples using continuous mode.

        Optimized for high-speed acquisition (FFT, etc.)

        Args:
            samples: Number of samples to capture
            channel: Single-ended channel (0-3)

        Returns:
            list: Voltage values

        Raises:
            RuntimeError: If too many consecutive I2C errors occur
        """
        # Set up continuous mode
        mux = (_MUX_SINGLE_0 + (channel << 12))
        config = (mux | self._gain | _MODE_CONTINUOUS |
                  self._rate | _COMP_DISABLE)

        try:
            self._write_config(config)
        except OSError as e:
            raise RuntimeError(f"ADS1115 config write failed: {e}") from e

        # Calculate delay based on actual sample rate
        rate_sps = self._get_rate_sps()
        conv_time_us = (1000000 // rate_sps) + 100
        time.sleep_us(conv_time_us)

        # Capture samples
        fsr = self._FSR_MAP[self._gain]
        scale = fsr / 32768.0
        results = [0.0] * samples

        buf = self._buf2
        i2c = self.i2c
        addr = self.address

        consecutive_errors = 0
        last_good_value = 0.0

        for i in range(samples):
            try:
                i2c.readfrom_mem_into(addr, _REG_CONVERSION, buf)
                value = (buf[0] << 8) | buf[1]
                if value >= 0x8000:
                    value -= 0x10000
                results[i] = value * scale
                last_good_value = results[i]
                consecutive_errors = 0

            except OSError as e:
                # I2C error - use last good value and track errors
                results[i] = last_good_value
                consecutive_errors += 1

                if consecutive_errors >= 10:
                    raise RuntimeError(f"ADS1115 I2C failed after {consecutive_errors} consecutive errors: {e}") from e

            # Pace reads to match conversion rate
            time.sleep_us(1000000 // rate_sps)

        # Return to single-shot mode (lower power)
        config = (mux | self._gain | _MODE_SINGLE |
                  self._rate | _COMP_DISABLE)
        try:
            self._write_config(config)
        except OSError as e:
            # Non-fatal - just log it
            print(f"Warning: Failed to return to single-shot mode: {e}")

        return results


def test():
    """Quick test of ADS1115."""
    from machine import I2C, Pin
    
    print("Initializing I2C...")
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400000)
    
    print("Scanning bus...")
    devices = i2c.scan()
    print(f"  Found: {[hex(d) for d in devices]}")
    
    print("\nInitializing ADS1115...")
    adc = ADS1115(i2c, address=0x48)
    adc.init(gain=ADS1115.GAIN_4096, rate=ADS1115.RATE_860)
    
    print("\nReading channels...")
    for ch in range(4):
        try:
            v = adc.read_voltage(channel=ch)
            print(f"  Channel {ch}: {v:.4f} V")
        except Exception as e:
            print(f"  Channel {ch}: Error - {e}")
    
    print("\nCapturing 100 samples...")
    data = adc.capture(samples=100, channel=0)
    avg = sum(data) / len(data)
    min_v = min(data)
    max_v = max(data)
    print(f"  Avg: {avg:.4f} V")
    print(f"  Min: {min_v:.4f} V")
    print(f"  Max: {max_v:.4f} V")
    print(f"  P-P: {(max_v - min_v) * 1000:.2f} mV")
    
    print("\nDone!")


if __name__ == "__main__":
    test()
