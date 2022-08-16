# Integration Time dictionary. [0] is the byte setting; [1] is the risk
# level divisor.
_VEML6070_INTEGRATION_TIME = {
    "VEML6070_HALF_T": [0x00, 0],
    "VEML6070_1_T": [0x01, 1],
    "VEML6070_2_T": [0x02, 2],
    "VEML6070_4_T": [0x03, 4],
}

# UV Risk Level dictionary. [0],[1] are the lower and uppper bounds of the range
_VEML6070_RISK_LEVEL = {
    "LOW": [0, 560],
    "MODERATE": [561, 1120],
    "HIGH": [1121, 1494],
    "VERY HIGH": [1495, 2054],
    "EXTREME": [2055, 9999],
}

class VEML6070:
    def __init__(self, i2c, address, ack = False):

        # Passed checks; set self values
        self._ack = int(ack)
        self._ack_thd = 0x00
        self._it = "VEML6070_1_T"

        # Latch the I2C addresses
        self.i2c = i2c
        self.address_cmd = address
        self.address_l = address
        self.address_h = address + 1

        self.buf = bytearray(1)
        self.buf[0] = (
            self._ack << 5 | _VEML6070_INTEGRATION_TIME[self._it][0] << 2 | 0x02
        )

        self._write(self.buf)

    def _write(self, buffer):
        self.i2c.writeto(self.address_cmd, buffer)

    def _read(self, address, length):
        return self.i2c.readfrom(address, length)

    @property
    def uv_raw(self):
        buflow = self._read(self.address_l, 1)
        bufhigh = self._read(self.address_h, 1)

        # poll a second time: this looks like BS but it is necessary? :(
        buflow = self._read(self.address_l, 1)
        bufhigh = self._read(self.address_h, 1)

        return bufhigh[0] << 8 | buflow[0]

    @property
    def integration_time(self):
        return self._it

    @integration_time.setter
    def integration_time(self, new_it):
        if new_it not in _VEML6070_INTEGRATION_TIME:
            raise ValueError(
                "Integration Time invalid. Valid values are: ",
                _VEML6070_INTEGRATION_TIME.keys(),
            )

        self._it = new_it
        self.buf[0] = (
            self._ack << 5
            | self._ack_thd << 4
            | _VEML6070_INTEGRATION_TIME[new_it][0] << 2
            | 0x02
        )
        self._write(self.buf)

    def sleep(self):
        """
        Puts the VEML6070 into sleep ('shutdown') mode. Datasheet claims a current draw
        of 1uA while in shutdown.
        """
        self.buf[0] = 0x03
        self._write(self.buf)

    def wake(self):
        """
        Wakes the VEML6070 from sleep. :class:`VEML6070.uv_raw` will also wake from sleep.
        """
        self.buf[0] = (
            self._ack << 5
            | self._ack_thd << 4
            | _VEML6070_INTEGRATION_TIME[self._it][0] << 2
            | 0x02
        )
        self._write(self.buf)

    def get_index(self, buf):
        adjusted = int(buf/1)
        for levels in _VEML6070_RISK_LEVEL:
            tmp_range = range(_VEML6070_RISK_LEVEL[levels][0],
                              _VEML6070_RISK_LEVEL[levels][1])
            if adjusted in tmp_range:
                risk = levels
                break

        return risk