from micropython import const

# Set I2C addresses:
_VEML6070_ADDR_ARA = const(0x18 >> 1)
_VEML6070_ADDR_CMD = const(0x70 >> 1)

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

class I2CDevice:
    def __init__(self, i2c, device_address, probe=True):
        self.i2c = i2c
        self.device_address = device_address
        if probe:
            self.__probe_for_device()

    def readinto(self, buf):
        self.i2c.readfrom_into(self.device_address, buf)

    def write(self, buf):
        self.i2c.writeto(self.device_address, buf)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def __probe_for_device(self):
        try:
            self.i2c.writeto(self.device_address, b"")
        except OSError:
            # some OS's dont like writing an empty bytesting...
            # Retry by reading a byte
            try:
                result = bytearray(1)
                self.i2c.readfrom_into(self.device_address, result)
            except OSError:
                # pylint: disable=raise-missing-from
                raise ValueError("No I2C device at address: 0x%x" % self.device_address)
                # pylint: enable=raise-missing-from

class VEML6070:
    def __init__(self, i2c, address, _veml6070_it="VEML6070_1_T", ack=False):
        # Check if the IT is valid
        if _veml6070_it not in _VEML6070_INTEGRATION_TIME:
            raise ValueError(
                "Integration Time invalid. Valid values are: ",
                _VEML6070_INTEGRATION_TIME.keys(),
            )

        # Check if ACK is valid
        if ack not in (True, False):
            raise ValueError("ACK must be 'True' or 'False'.")

        # Passed checks; set self values
        self._ack = int(ack)
        self._ack_thd = 0x00
        self._it = _veml6070_it

        # Latch the I2C addresses
        self.i2c_cmd = I2CDevice(i2c, _VEML6070_ADDR_CMD)
        self.i2c = i2c
        self.address = address

        # Initialize the VEML6070
        ara_buf = bytearray(1)
        try:
            with I2CDevice(i2c, _VEML6070_ADDR_ARA) as ara:
                ara.readinto(ara_buf)
        except ValueError:  # the ARA address is never valid? datasheet error?
            pass
        self.buf = bytearray(1)
        self.buf[0] = (
            self._ack << 5 | _VEML6070_INTEGRATION_TIME[self._it][0] << 2 | 0x02
        )
        with self.i2c_cmd as i2c_cmd:
            i2c_cmd.write(self.buf)

    @property
    def uv_raw(self):
        buflow = self.i2c.readfrom(self.address,1)
        bufhigh = self.i2c.readfrom(self.address+1,1)
        buf = bufhigh[0] <<8
        buf |= buflow[0]

        return buf

    @property
    def integration_time(self):
        """
        The Integration Time of the sensor, which is the refresh interval of the
        sensor. The higher the refresh interval, the more accurate the reading is (at
        the cost of less sampling). The available settings are: :const:`VEML6070_HALF_T`,
        :const:`VEML6070_1_T`, :const:`VEML6070_2_T`, :const:`VEML6070_4_T`.
        """
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
        with self.i2c_cmd as i2c_cmd:
            i2c_cmd.write(self.buf)

    def sleep(self):
        """
        Puts the VEML6070 into sleep ('shutdown') mode. Datasheet claims a current draw
        of 1uA while in shutdown.
        """
        self.buf[0] = 0x03
        with self.i2c_cmd as i2c_cmd:
            i2c_cmd.write(self.buf)

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
        with self.i2c_cmd as i2c_cmd:
            i2c_cmd.write(self.buf)

    def get_index(self, buf):
        adjusted = int(buf/1)
        for levels in _VEML6070_RISK_LEVEL:
            tmp_range = range(_VEML6070_RISK_LEVEL[levels][0],
                              _VEML6070_RISK_LEVEL[levels][1])
            if adjusted in tmp_range:
                risk = levels
                break

        return risk