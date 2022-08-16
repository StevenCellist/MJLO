# TSL2591 lux sensor interface modified by Steven Boonstoppel
import time

VISIBLE = 2
INFRARED = 1
FULLSPECTRUM = 0

ADDR = 0x29
READBIT = 0x01
COMMAND_BIT = 0xA0
CLEAR_BIT = 0x40
WORD_BIT = 0x20
BLOCK_BIT = 0x10
ENABLE_POWERON = 0x01
ENABLE_POWEROFF = 0x00
ENABLE_AEN = 0x02
ENABLE_AIEN = 0x10
CONTROL_RESET = 0x80
LUX_DF = 408.0
LUX_COEFB = 1.64
LUX_COEFC = 0.59
LUX_COEFD = 0.86

REGISTER_ENABLE = 0x00
REGISTER_CONTROL = 0x01
REGISTER_THRESHHOLDL_LOW = 0x02
REGISTER_THRESHHOLDL_HIGH = 0x03
REGISTER_THRESHHOLDH_LOW = 0x04
REGISTER_THRESHHOLDH_HIGH = 0x05
REGISTER_INTERRUPT = 0x06
REGISTER_CRC = 0x08
REGISTER_ID = 0x0A
REGISTER_CHAN0_LOW = 0x14
REGISTER_CHAN0_HIGH = 0x15
REGISTER_CHAN1_LOW = 0x16
REGISTER_CHAN1_HIGH = 0x17
INTEGRATIONTIME_100MS = 0x00
INTEGRATIONTIME_200MS = 0x01
INTEGRATIONTIME_300MS = 0x02
INTEGRATIONTIME_400MS = 0x03
INTEGRATIONTIME_500MS = 0x04
INTEGRATIONTIME_600MS = 0x05

GAIN_LOW = 0x00
GAIN_MED = 0x10
GAIN_HIGH = 0x20
GAIN_MAX = 0x30

class TSL2591:
    def __init__(
                 self,
                 i2c,
                 address,
                 sensor_id = 0x50,
                 integration=INTEGRATIONTIME_100MS,
                 gain=GAIN_LOW
                 ):
        self.sensor_id = sensor_id
        self.address = address
        self.i2c = i2c
        self.integration_time = integration
        self.gain = gain
        self.set_timing(self.integration_time)
        self.set_gain(self.gain)

    def _write(self, register, value):
        buffer = bytearray(2)
        buffer[0] = register
        buffer[1] = value
        self.i2c.writeto(self.address, buffer)

    def _read(self, register, length):
        self.i2c.writeto(self.address, bytes([register & 0xFF]))
        result = self.i2c.readfrom(self.address, length)
        if length <= 2:
            return int.from_bytes(result, 'little')
        return result

    def set_timing(self, integration):
        self.integration_time = integration
        self._write(
                    COMMAND_BIT | REGISTER_CONTROL,
                    self.integration_time | self.gain
                    )

    def set_gain(self, gain):
        self.gain = gain
        self._write(
                    COMMAND_BIT | REGISTER_CONTROL,
                    self.integration_time | self.gain
                    )

    @property
    def lux(self):
        full, ir = self.get_full_luminosity()
        if (full == 0xFFFF) | (ir == 0xFFFF):
            return 0
            
        case_integ = {
            INTEGRATIONTIME_100MS: 100.,
            INTEGRATIONTIME_200MS: 200.,
            INTEGRATIONTIME_300MS: 300.,
            INTEGRATIONTIME_400MS: 400.,
            INTEGRATIONTIME_500MS: 500.,
            INTEGRATIONTIME_600MS: 600.,
            }
        if self.integration_time in case_integ.keys():
            atime = case_integ[self.integration_time]
        else:
            atime = 100.

        case_gain = {
            GAIN_LOW: 1.,
            GAIN_MED: 25.,
            GAIN_HIGH: 428.,
            GAIN_MAX: 9876.,
            }

        if self.gain in case_gain.keys():
            again = case_gain[self.gain]
        else:
            again = 1.

        cpl = (atime * again) / LUX_DF
        lux1 = (full - (LUX_COEFB * ir)) / cpl

        lux2 = ((LUX_COEFC * full) - (LUX_COEFD * ir)) / cpl

        return max([lux1, lux2])

    def wake(self):
        self._write(
                    COMMAND_BIT | REGISTER_ENABLE,
                    ENABLE_POWERON | ENABLE_AEN | ENABLE_AIEN
                    )

    def sleep(self):
        self._write(
                    COMMAND_BIT | REGISTER_ENABLE,
                    ENABLE_POWEROFF
                    )

    def get_full_luminosity(self):
        time.sleep(0.12 * self.integration_time)
        full = self._read(
                    COMMAND_BIT | REGISTER_CHAN0_LOW, 2
                    )
        ir = self._read(
                    COMMAND_BIT | REGISTER_CHAN1_LOW, 2
                    )                    
        return full, ir

    def get_luminosity(self, channel):
        full, ir = self.get_full_luminosity()
        if channel == FULLSPECTRUM:
            return full
        elif channel == INFRARED:
            return ir
        elif channel == VISIBLE:
            return full - ir
        else:
            return 0

    def sample(self):
        full, ir = self.get_full_luminosity()
        return self.calculate_lux(full, ir)
