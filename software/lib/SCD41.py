# modified by Steven Boonstoppel
# from https://github.com/adafruit/Adafruit_CircuitPython_SCD4X/blob/main/adafruit_scd4x.py
# and https://github.com/Sensirion/arduino-i2c-scd4x/blob/master/src/SensirionI2CScd4x.cpp

import time
import struct

SCD4X_DEFAULT_ADDR = 0x62
_SCD4X_REINIT = 0x3646
_SCD4X_FACTORYRESET = 0x3632
_SCD4X_FORCEDRECAL = 0x362F
_SCD4X_DATAREADY = 0xE4B8
_SCD4X_STOPPERIODICMEAS = 0x3F86
_SCD4X_STARTPERIODICMEAS = 0x21B1
_SCD4X_STARTLOWPOWERPERIODICMEAS = 0x21AC
_SCD4X_READMEAS = 0xEC05
_SCD4X_SERIALNUMBER = 0x3682
_SCD4X_GETTEMPOFFSET = 0x2318
_SCD4X_SETTEMPOFFSET = 0x241D
_SCD4X_SETPRESSURE = 0xE000
_SCD4X_PERSISTSETTINGS = 0x3615
_SCD4X_GETASCE = 0x2313
_SCD4X_SETASCE = 0x2416

_SCD4X_MEASSINGLESHOT = 0x219D
_SCD4X_MEASSINGLESHOTRHT = 0x2196
_SCD4X_SLEEP = 0x36E0
_SCD4X_WAKE = 0x36F6


class SCD41:
    def __init__(self, i2c, address = SCD4X_DEFAULT_ADDR) -> None:
        self.i2c = i2c
        self.address = address
        self._buffer = bytearray(18)
        self._cmd = bytearray(2)
        self._crc_buffer = bytearray(2)

        # cached readings
        self._temperature = None
        self._relative_humidity = None
        self._co2 = None

        try:
            self.stop_periodic_measurement()
        except:
            pass

    @property
    def CO2(self) -> int:
        """Returns the CO2 concentration in PPM (parts per million)"""
        if self.data_ready:
            self._read_data()
        return self._co2

    @property
    def temperature(self) -> float:
        """Returns the current temperature in degrees Celsius"""
        if self.data_ready:
            self._read_data()
        return self._temperature

    @property
    def relative_humidity(self) -> float:
        """Returns the current relative humidity in %rH"""
        if self.data_ready:
            self._read_data()
        return self._relative_humidity

    def reinit(self) -> None:
        """Reinitializes the sensor by reloading user settings from EEPROM."""
        self.stop_periodic_measurement()
        self._send_command(_SCD4X_REINIT, cmd_delay=0.02)

    def factory_reset(self) -> None:
        """Resets all configuration settings stored in the EEPROM and erases the FRC and ASC algorithm history."""
        self.stop_periodic_measurement()
        self._send_command(_SCD4X_FACTORYRESET, cmd_delay=1.2)

    def force_calibration(self, target_co2: int) -> None:
        """Forces the sensor to recalibrate with a given current CO2"""
        self.stop_periodic_measurement()
        self._set_command_value(_SCD4X_FORCEDRECAL, target_co2, cmd_delay=0.5)
        self._read_reply(3)
        correction = struct.unpack_from(">h", self._buffer[0:2])[0]
        if correction == 0xFFFF:
            raise RuntimeError(
                "Forced recalibration failed.\
            Make sure sensor is active for 3 minutes first"
            )

    @property
    def self_calibration_enabled(self) -> bool:
        """Enables or disables automatic self calibration (ASC). To work correctly, the sensor must
        be on and active for 7 days after enabling ASC, and exposed to fresh air for at least 1 hour
        per day. 
        .. note: This value will NOT be saved unless saved with persist_settings()."""
        self._send_command(_SCD4X_GETASCE, cmd_delay=0.001)
        self._read_reply(3)
        return self._buffer[1] == 1

    @self_calibration_enabled.setter
    def self_calibration_enabled(self, enabled: bool) -> None:
        self._set_command_value(_SCD4X_SETASCE, enabled)

    def _read_data(self) -> None:
        """Reads the temp/hum/co2 from the sensor and caches it"""
        self._send_command(_SCD4X_READMEAS, cmd_delay=0.001)
        self._read_reply(9)
        self._co2 = (self._buffer[0] << 8) | self._buffer[1]
        temp = (self._buffer[3] << 8) | self._buffer[4]
        self._temperature = -45 + 175 * (temp / 2**16)
        humi = (self._buffer[6] << 8) | self._buffer[7]
        self._relative_humidity = 100 * (humi / 2**16)

    @property
    def data_ready(self) -> bool:
        """Check the sensor to see if new data is available"""
        self._send_command(_SCD4X_DATAREADY, cmd_delay=0.001)
        self._read_reply(3)
        return not ((self._buffer[0] & 0x07 == 0) and (self._buffer[1] == 0))

    @property
    def serial_number(self):
        """Request a 6-tuple containing the unique serial number for this sensor"""
        self._send_command(_SCD4X_SERIALNUMBER, cmd_delay=0.001)
        self._read_reply(9)
        return (
            self._buffer[0],
            self._buffer[1],
            self._buffer[3],
            self._buffer[4],
            self._buffer[6],
            self._buffer[7],
        )

    def stop_periodic_measurement(self) -> None:
        """Stop measurement mode"""
        self._send_command(_SCD4X_STOPPERIODICMEAS, cmd_delay=0.5)

    def start_periodic_measurement(self) -> None:
        """Put sensor into working mode, about 5s per measurement"""
        self._send_command(_SCD4X_STARTPERIODICMEAS)

    def start_low_periodic_measurement(self) -> None:
        """Put sensor into low power working mode, about 30s per measurement."""
        self._send_command(_SCD4X_STARTLOWPOWERPERIODICMEAS)

    def persist_settings(self) -> None:
        """Save temperature offset, altitude offset, and selfcal enable settings to EEPROM"""
        self._send_command(_SCD4X_PERSISTSETTINGS, cmd_delay=0.8)

    def set_ambient_pressure(self, ambient_pressure: int) -> None:
        """Set the ambient pressure in hPa at any time to adjust CO2 calculations"""
        if ambient_pressure < 0 or ambient_pressure > 65535:
            raise AttributeError("`ambient_pressure` must be from 0~65535 hPascals")
        self._set_command_value(_SCD4X_SETPRESSURE, ambient_pressure)

    @property
    def temperature_offset(self) -> float:
        """Specifies the offset to be added to the reported measurements to account for a bias in
        the measured signal. Value is in degrees Celsius with a resolution of 0.01 degrees
        .. note: This value will NOT be saved unless saved with persist_settings().
        """
        self._send_command(_SCD4X_GETTEMPOFFSET, cmd_delay=0.001)
        self._read_reply(3)
        temp = (self._buffer[0] << 8) | self._buffer[1]
        return 175.0 * temp / 2**16

    @temperature_offset.setter
    def temperature_offset(self, offset) -> None:
        if offset > 374:
            raise AttributeError(
                "Offset value must be less than or equal to 374 degrees Celsius"
            )
        temp = int(offset * 2**16 / 175)
        self._set_command_value(_SCD4X_SETTEMPOFFSET, temp)

    def _check_buffer_crc(self, buf: bytearray) -> bool:
        for i in range(0, len(buf), 3):
            self._crc_buffer[0] = buf[i]
            self._crc_buffer[1] = buf[i + 1]
            if self._crc8(self._crc_buffer) != buf[i + 2]:
                raise RuntimeError("CRC check failed while reading data")
        return True

    def _send_command(self, cmd, cmd_delay = 0) -> None:
        buffer = bytearray(2)
        buffer[0] = (cmd >> 8) & 0xFF
        buffer[1] = cmd & 0xFF
        self.i2c.writeto(self.address, buffer)
        time.sleep(cmd_delay)

    def _set_command_value(self, cmd, value, cmd_delay=0):
        self._buffer[0] = (cmd >> 8) & 0xFF
        self._buffer[1] = cmd & 0xFF
        self._crc_buffer[0] = self._buffer[2] = (value >> 8) & 0xFF
        self._crc_buffer[1] = self._buffer[3] = value & 0xFF
        self._buffer[4] = self._crc8(self._crc_buffer)
        self.i2c.writeto(self.address, self._buffer)
        time.sleep(cmd_delay)

    def _read_reply(self, num):
        self._buffer = self.i2c.readfrom(self.address, num)
        self._check_buffer_crc(self._buffer[0:num])

    @staticmethod
    def _crc8(buffer: bytearray) -> int:
        crc = 0xFF
        for byte in buffer:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc = crc << 1
        return crc & 0xFF  # return the bottom 8 bits

    def measure_single_shot(self) -> None:
        self._send_command(_SCD4X_MEASSINGLESHOT, cmd_delay=0.001)

    def measure_single_shot_rht(self) -> None:
        self._send_command(_SCD4X_MEASSINGLESHOTRHT, cmd_delay=0.05)

    def sleep(self) -> None:
        self._send_command(_SCD4X_SLEEP, cmd_delay=0.001)

    def wake(self) -> None:
        # sensor does not send an ACK on wake, so discard the error
        try: 
            self._send_command(_SCD4X_WAKE, cmd_delay=0.02)
        except:
            pass