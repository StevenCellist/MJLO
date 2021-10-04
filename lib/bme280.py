# SPDX-FileCopyrightText: 2017 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_bme280.basic`
=========================================================================================

CircuitPython driver from BME280 Temperature, Humidity and Barometric
Pressure sensor

* Author(s): ladyada, Jose David M.

Implementation Notes
--------------------

**Hardware:**

* `Adafruit BME280 Temperature, Humidity and Barometric Pressure sensor
  <https://www.adafruit.com/product/2652>`_ (Product ID: 2652)


**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

"""
import math
from time import sleep
from micropython import const

try:
    import struct
except ImportError:
    import ustruct as struct


#    I2C ADDRESS/BITS/SETTINGS
#    -----------------------------------------------------------------------

"""General Information"""
_BME280_ADDRESS = const(0x76)
_BME280_CHIPID = const(0x60)
_BME280_REGISTER_CHIPID = const(0xD0)
"""overscan values for temperature, pressure, and humidity"""
OVERSCAN_X1 = const(0x01)
OVERSCAN_X16 = const(0x05)
"""mode values"""
_BME280_MODES = (0x00, 0x01, 0x03)
"""iir_filter values"""
IIR_FILTER_DISABLE = const(0)
"""
standby timeconstant values
TC_X[_Y] where X=milliseconds and Y=tenths of a millisecond
"""
STANDBY_TC_125 = const(0x02)  # 125ms
"""mode values"""
MODE_SLEEP = const(0x00)
MODE_FORCE = const(0x01)
MODE_NORMAL = const(0x03)
"""Other Registers"""
_BME280_REGISTER_SOFTRESET = const(0xE0)
_BME280_REGISTER_CTRL_HUM = const(0xF2)
_BME280_REGISTER_STATUS = const(0xF3)
_BME280_REGISTER_CTRL_MEAS = const(0xF4)
_BME280_REGISTER_CONFIG = const(0xF5)
_BME280_REGISTER_TEMPDATA = const(0xFA)
_BME280_REGISTER_HUMIDDATA = const(0xFD)

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

    # pylint: disable-msg=too-many-arguments
    def write_then_readinto(
        self,
        out_buffer,
        in_buffer,
        *,
        out_start=0,
        out_end=None,
        in_start=0,
        in_end=None
    ):

        if out_end is None:
            out_end = len(out_buffer)
        if in_end is None:
            in_end = len(in_buffer)

        self.i2c.writeto_then_readfrom(
            self.device_address,
            out_buffer,
            in_buffer,
            out_start=out_start,
            out_end=out_end,
            in_start=in_start,
            in_end=in_end,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def __probe_for_device(self):
        """
        Try to read a byte from an address,
        if you get an OSError it means the device is not there
        or that the device does not support these means of probing
        """
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

class Adafruit_BME280:
    """Driver from BME280 Temperature, Humidity and Barometric Pressure sensor"""

    def __init__(self):
        """Read the coefficients and enable the sensor"""
        # Set some reasonable defaults.
        self._iir_filter = IIR_FILTER_DISABLE
        self.overscan_humidity = OVERSCAN_X1
        self.overscan_temperature = OVERSCAN_X1
        self.overscan_pressure = OVERSCAN_X16
        self._t_standby = STANDBY_TC_125
        self._mode = MODE_SLEEP
        self._reset()
        self._read_coefficients()
        self._write_ctrl_meas()
        self._write_config()
        self.sea_level_pressure = 1013.25
        """Pressure in hectoPascals at sea level. Used to calibrate `altitude`."""
        self._t_fine = None

    def _read_temperature(self):
        # perform one measurement
        if self.mode != MODE_NORMAL:
            self.mode = MODE_FORCE
            # Wait for conversion to complete
            while self._get_status() & 0x08:
                sleep(0.002)
        raw_temperature = (
            self._read24(_BME280_REGISTER_TEMPDATA) / 16
        )  # lowest 4 bits get dropped

        var1 = (
            raw_temperature / 16384.0 - self._temp_calib[0] / 1024.0
        ) * self._temp_calib[1]

        var2 = (
            (raw_temperature / 131072.0 - self._temp_calib[0] / 8192.0)
            * (raw_temperature / 131072.0 - self._temp_calib[0] / 8192.0)
        ) * self._temp_calib[2]

        self._t_fine = int(var1 + var2)

    def _reset(self):
        """Soft reset the sensor"""
        self._write_register_byte(_BME280_REGISTER_SOFTRESET, 0xB6)
        sleep(0.004)  # Datasheet says 2ms.  Using 4ms just to be safe

    def _write_ctrl_meas(self):
        """
        Write the values to the ctrl_meas and ctrl_hum registers in the device
        ctrl_meas sets the pressure and temperature data acquisition options
        ctrl_hum sets the humidity oversampling and must be written to first
        """
        self._write_register_byte(_BME280_REGISTER_CTRL_HUM, self.overscan_humidity)
        self._write_register_byte(_BME280_REGISTER_CTRL_MEAS, self._ctrl_meas)

    def _get_status(self):
        """Get the value from the status register in the device """
        return self._read_byte(_BME280_REGISTER_STATUS)

    def _read_config(self):
        """Read the value from the config register in the device """
        return self._read_byte(_BME280_REGISTER_CONFIG)

    def _write_config(self):
        """Write the value to the config register in the device """
        normal_flag = False
        if self._mode == MODE_NORMAL:
            # Writes to the config register may be ignored while in Normal mode
            normal_flag = True
            self.mode = MODE_SLEEP  # So we switch to Sleep mode first
        self._write_register_byte(_BME280_REGISTER_CONFIG, self._config)
        if normal_flag:
            self.mode = MODE_NORMAL

    @property
    def mode(self):
        """
        Operation mode
        Allowed values are the constants MODE_*
        """
        return self._mode

    @mode.setter
    def mode(self, value):
        if not value in _BME280_MODES:
            raise ValueError("Mode '%s' not supported" % (value))
        self._mode = value
        self._write_ctrl_meas()

    @property
    def _config(self):
        """Value to be written to the device's config register """
        config = 0
        if self.mode == 0x03:  # MODE_NORMAL
            config += self._t_standby << 5
        if self._iir_filter:
            config += self._iir_filter << 2
        return config

    @property
    def _ctrl_meas(self):
        """Value to be written to the device's ctrl_meas register """
        ctrl_meas = self.overscan_temperature << 5
        ctrl_meas += self.overscan_pressure << 2
        ctrl_meas += self.mode
        return ctrl_meas

    @property
    def temperature(self):
        """The compensated temperature in degrees Celsius."""
        self._read_temperature()
        return self._t_fine / 5120.0

    @property
    def pressure(self):
        """
        The compensated pressure in hectoPascals.
        returns None if pressure measurement is disabled
        """
        self._read_temperature()

        # Algorithm from the BME280 driver
        # https://github.com/BoschSensortec/BME280_driver/blob/master/bme280.c
        adc = (
            self._read24(0xF7) / 16  # BME280_REGISTER_PRESSUREDATA
        )  # lowest 4 bits get dropped
        var1 = float(self._t_fine) / 2.0 - 64000.0
        var2 = var1 * var1 * self._pressure_calib[5] / 32768.0
        var2 = var2 + var1 * self._pressure_calib[4] * 2.0
        var2 = var2 / 4.0 + self._pressure_calib[3] * 65536.0
        var3 = self._pressure_calib[2] * var1 * var1 / 524288.0
        var1 = (var3 + self._pressure_calib[1] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self._pressure_calib[0]
        if not var1:  # avoid exception caused by division by zero
            raise ArithmeticError(
                "Invalid result possibly related to error while reading the calibration registers"
            )
        pressure = 1048576.0 - adc
        pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
        var1 = self._pressure_calib[8] * pressure * pressure / 2147483648.0
        var2 = pressure * self._pressure_calib[7] / 32768.0
        pressure = pressure + (var1 + var2 + self._pressure_calib[6]) / 16.0

        pressure /= 100
        return pressure

    @property
    def relative_humidity(self):
        """
        The relative humidity in RH %
        returns None if humidity measurement is disabled
        """
        return self.humidity

    @property
    def humidity(self):
        """
        The relative humidity in RH %
        returns None if humidity measurement is disabled
        """
        self._read_temperature()
        hum = self._read_register(0xFD, 2)  # BME280_REGISTER_HUMIDDATA
        adc = float(hum[0] << 8 | hum[1])

        # Algorithm from the BME280 driver
        # https://github.com/BoschSensortec/BME280_driver/blob/master/bme280.c
        var1 = float(self._t_fine) - 76800.0
        var2 = (
            self._humidity_calib[3] * 64.0 + (self._humidity_calib[4] / 16384.0) * var1
        )
        var3 = adc - var2
        var4 = self._humidity_calib[1] / 65536.0
        var5 = 1.0 + (self._humidity_calib[2] / 67108864.0) * var1
        var6 = 1.0 + (self._humidity_calib[5] / 67108864.0) * var1 * var5
        var6 = var3 * var4 * (var5 * var6)
        humidity = var6 * (1.0 - self._humidity_calib[0] * var6 / 524288.0)

        if humidity > 100:
            return 100
        if humidity < 0:
            return 0
        # else...
        return humidity

    @property
    def altitude(self):
        """The altitude based on current :attr:`pressure` versus the sea level pressure
        (``sea_level_pressure``) - which you must enter ahead of time)"""
        pressure = self.pressure  # in Si units for hPascal
        return 44330 * (1.0 - math.pow(pressure / self.sea_level_pressure, 0.1903))

    def _read_coefficients(self):
        """Read & save the calibration coefficients"""
        coeff = self._read_register(0x88, 24)  # BME280_REGISTER_DIG_T1
        coeff = list(struct.unpack("<HhhHhhhhhhhh", bytes(coeff)))
        coeff = [float(i) for i in coeff]
        self._temp_calib = coeff[:3]
        self._pressure_calib = coeff[3:]

        self._humidity_calib = [0] * 6
        self._humidity_calib[0] = self._read_byte(0xA1)  # BME280_REGISTER_DIG_H1
        coeff = self._read_register(0xE1, 7)  # BME280_REGISTER_DIG_H2
        coeff = list(struct.unpack("<hBbBbb", bytes(coeff)))
        self._humidity_calib[1] = float(coeff[0])
        self._humidity_calib[2] = float(coeff[1])
        self._humidity_calib[3] = float((coeff[2] << 4) | (coeff[3] & 0xF))
        self._humidity_calib[4] = float((coeff[4] << 4) | (coeff[3] >> 4))
        self._humidity_calib[5] = float(coeff[5])

    def _read_byte(self, register):
        """Read a byte register value and return it"""
        return self._read_register(register, 1)[0]

    def _read24(self, register):
        """Read an unsigned 24-bit value as a floating point and return it."""
        ret = 0.0
        for b in self._read_register(register, 3):
            ret *= 256.0
            ret += float(b & 0xFF)
        return ret

    def _read_register(self, register, length):
        raise NotImplementedError()

    def _write_register_byte(self, register, value):
        raise NotImplementedError()


class BME280_I2C(Adafruit_BME280):

    def __init__(self, i2c, address=0x77):

        self._i2c = I2CDevice(i2c, address)
        super().__init__()

    def _read_register(self, register, length):
        with self._i2c as i2c:
            i2c.write(bytes([register & 0xFF]))
            result = bytearray(length)
            i2c.readinto(result)
            return result

    def _write_register_byte(self, register, value):
        with self._i2c as i2c:
            i2c.write(bytes([register & 0xFF, value & 0xFF]))
