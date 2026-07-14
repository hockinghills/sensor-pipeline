# MAX31856 MicroPython Library
# Adapted from alinbaltaru/max31856 for continuous mode and S-Type thermocouple
# MIT License

import time
import machine

class MAX31856:
    def __init__(self, cs_pin, miso_pin, mosi_pin, clk_pin, tc_type='S'):
        self.cs = machine.Pin(cs_pin, machine.Pin.OUT)
        self.miso = machine.Pin(miso_pin, machine.Pin.IN)
        self.mosi = machine.Pin(mosi_pin, machine.Pin.OUT)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)

        self.cs.value(1)
        self.clk.value(0)
        self.mosi.value(0)

        # Thermocouple type codes
        tc_types = {
            'B': 0x00, 'E': 0x01, 'J': 0x02, 'K': 0x03,
            'N': 0x04, 'R': 0x05, 'S': 0x06, 'T': 0x07
        }

        # Config Register 1: Continuous conversion mode
        # bit 7: 1 = Continuous conversion mode
        # bit 6: 0 = not used in continuous
        # bit 5-4: 00 = open-circuit detection off
        # bit 3: 0 = CJ sensor enabled
        # bit 2: 0 = normal fault mode
        # bit 1: 1 = clear faults
        # bit 0: 0 = 60Hz filter
        self.write_register(0, 0x82)  # Continuous mode + clear faults

        # Config Register 1: Set thermocouple type (default 1 sample averaging)
        tc_code = tc_types.get(tc_type.upper(), 0x06)  # Default to S-Type
        self.write_register(1, tc_code)

        time.sleep_ms(200)  # Allow initialization

    def read_thermocouple_temp(self):
        # Read 4 registers starting at 0x0C (thermocouple temp + fault)
        data = self.read_registers(0x0C, 4)

        # Combine 19-bit temperature value
        temp = ((data[0] << 16) | (data[1] << 8) | data[2]) >> 5

        # Handle negative temps (2's complement)
        if data[0] & 0x80:
            temp -= 0x80000

        temp_c = temp * 0.0078125

        # Check fault register
        fault = data[3]
        if fault:
            self._handle_fault(fault)

        return temp_c

    def read_cj_temp(self):
        # Read cold junction temperature (3 registers at 0x09)
        data = self.read_registers(0x09, 3)

        offset = data[0]
        temp = ((data[1] << 8) | data[2]) >> 2

        if data[1] & 0x80:
            temp -= 0x4000

        temp = offset + temp
        return temp * 0.015625

    def _handle_fault(self, fault):
        if fault & 0x80:
            raise FaultError("Cold Junction Out-of-Range")
        if fault & 0x40:
            raise FaultError("Thermocouple Out-of-Range")
        if fault & 0x20:
            raise FaultError("Cold-Junction High Fault")
        if fault & 0x10:
            raise FaultError("Cold-Junction Low Fault")
        if fault & 0x08:
            raise FaultError("Thermocouple High Fault")
        if fault & 0x04:
            raise FaultError("Thermocouple Low Fault")
        if fault & 0x02:
            raise FaultError("Overvoltage/Undervoltage Fault")
        if fault & 0x01:
            raise FaultError("Open-Circuit Fault")

    def write_register(self, reg_num, data_byte):
        self.cs.value(0)
        self.send_byte(0x80 | reg_num)  # Write command
        self.send_byte(data_byte)
        self.cs.value(1)

    def read_registers(self, start_reg, count):
        self.cs.value(0)
        self.send_byte(start_reg)  # Read command
        result = [self.recv_byte() for _ in range(count)]
        self.cs.value(1)
        return result

    def send_byte(self, byte):
        for _ in range(8):
            self.mosi.value(1 if byte & 0x80 else 0)
            byte <<= 1
            self.clk.value(1)
            self.clk.value(0)

    def recv_byte(self):
        byte = 0
        for _ in range(8):
            self.clk.value(1)
            byte = (byte << 1) | self.miso.value()
            self.clk.value(0)
        return byte


class FaultError(Exception):
    pass
