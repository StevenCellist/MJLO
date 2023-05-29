# Adaptation of Pimoroni library by Steven Boonstoppel
import math
import time

POLL_PERIOD_MS = 10
SOFT_RESET_CMD = 0xb6
SOFT_RESET_ADDR = 0xe0

ADDR_RES_HEAT_VAL_ADDR = 0x00
ADDR_RES_HEAT_RANGE_ADDR = 0x02
ADDR_RANGE_SW_ERR_ADDR = 0x04

FIELD0_ADDR = 0x1d
RES_HEAT0_ADDR = 0x5a
GAS_WAIT0_ADDR = 0x64

CONF_ODR_RUN_GAS_NBC_ADDR = 0x71
CONF_OS_H_ADDR = 0x72
CONF_T_P_MODE_ADDR = 0x74
CONF_ODR_FILT_ADDR = 0x75

COEFF_ADDR1 = 0x89
COEFF_ADDR2 = 0xe1

ENABLE_GAS_MEAS_LOW = 0x01

# Over-sampling settings
OS_NONE = 0
OS_1X = 1
OS_2X = 2
OS_4X = 3
OS_8X = 4
OS_16X = 5

# IIR filter settings
FILTER_SIZE_0 = 0
FILTER_SIZE_1 = 1
FILTER_SIZE_3 = 2
FILTER_SIZE_7 = 3
FILTER_SIZE_15 = 4
FILTER_SIZE_31 = 5
FILTER_SIZE_63 = 6
FILTER_SIZE_127 = 7

# Power mode settings
SLEEP_MODE = 0
FORCED_MODE = 1

# Mask definitions
NBCONV_MSK = 0X0F
FILTER_MSK = 0X1C
OST_MSK = 0XE0
OSP_MSK = 0X1C
OSH_MSK = 0X07
HCTRL_MSK = 0x08
RUN_GAS_MSK = 0x30
MODE_MSK = 0x03
RHRANGE_MSK = 0x30
RSERROR_MSK = 0xf0
NEW_DATA_MSK = 0x80
GAS_INDEX_MSK = 0x0f
GAS_RANGE_MSK = 0x0f
GASM_VALID_MSK = 0x20
HEAT_STAB_MSK = 0x10
BIT_H1_DATA_MSK = 0x0F

# Bit position definitions for sensor settings
FILTER_POS = 2
OST_POS = 5
OSP_POS = 2
OSH_POS = 0
RUN_GAS_POS = 4
MODE_POS = 0
NBCONV_POS = 0

# Look up tables for the possible gas range values
lookupTable1 = [2147483647, 2147483647, 2147483647, 2147483647,
                2147483647, 2126008810, 2147483647, 2130303777, 2147483647,
                2147483647, 2143188679, 2136746228, 2147483647, 2126008810,
                2147483647, 2147483647]

lookupTable2 = [4096000000, 2048000000, 1024000000, 512000000,
                255744255, 127110228, 64000000, 32258064,
                16016016, 8000000, 4000000, 2000000,
                1000000, 500000, 250000, 125000]

def bytes_to_word(msb, lsb, bits = 16, signed = True):
    """Convert a most and least significant byte into a word."""
    word = (msb << 8) | lsb
    if signed:
        word = twos_comp(word, bits)
    return word

def twos_comp(val, bits = 8):
    """Convert two bytes into a two's compliment signed word."""
    if val & (1 << (bits - 1)) != 0:
        val = val - (1 << bits)
    return val

class CalibrationData:
    """Structure for storing BME680 calibration data."""

    def set_from_array(self, cal):
        # Temperature related coefficients
        self.par_t1 = bytes_to_word(cal[34], cal[33], signed = False)
        self.par_t2 = bytes_to_word(cal[2], cal[1])
        self.par_t3 = twos_comp(cal[3])

        # Pressure related coefficients
        self.par_p1 = bytes_to_word(cal[6], cal[5], signed = False)
        self.par_p2 = bytes_to_word(cal[8], cal[7])
        self.par_p3 = twos_comp(cal[9])
        self.par_p4 = bytes_to_word(cal[12], cal[11])
        self.par_p5 = bytes_to_word(cal[14], cal[13])
        self.par_p6 = twos_comp(cal[16])
        self.par_p7 = twos_comp(cal[15])
        self.par_p8 = bytes_to_word(cal[20], cal[19])
        self.par_p9 = bytes_to_word(cal[22], cal[21])
        self.par_p10 = cal[23]

        # Humidity related coefficients
        self.par_h1 = (cal[27] << 4) | (cal[26] & BIT_H1_DATA_MSK)
        self.par_h2 = (cal[25] << 4) | (cal[26] >> 4)
        self.par_h3 = twos_comp(cal[28])
        self.par_h4 = twos_comp(cal[29])
        self.par_h5 = twos_comp(cal[30])
        self.par_h6 = cal[31]
        self.par_h7 = twos_comp(cal[32])

        # Gas heater related coefficients
        self.par_gh1 = twos_comp(cal[37])
        self.par_gh2 = bytes_to_word(cal[36], cal[35])
        self.par_gh3 = twos_comp(cal[38])

    def set_other(self, heat_range, heat_value, sw_error):
        """Set other values."""
        self.res_heat_range = (heat_range & RHRANGE_MSK) // 16
        self.res_heat_val = heat_value
        self.range_sw_err = (sw_error & RSERROR_MSK) // 16

class BME680:

    def __init__(self, i2c, address):

        self.address = address
        self.i2c = i2c

        self.power_mode = None
        self.calibration = CalibrationData()

        self.soft_reset()
        self.set_power_mode(SLEEP_MODE)

        self._get_calibration_data()

        self.set_humidity_oversample(OS_8X)
        self.set_pressure_oversample(OS_8X)
        self.set_temperature_oversample(OS_8X)
        self.set_filter(FILTER_SIZE_3)
        self.set_gas_status(ENABLE_GAS_MEAS_LOW)
        self.set_temp_offset(0)
        self.get_sensor_data()

    def _get_calibration_data(self):
        """Retrieve the sensor calibration data and store it in .calibration_data."""
        calibration = self._read(COEFF_ADDR1, 25)
        calibration += self._read(COEFF_ADDR2, 16)

        heat_range = self._read(ADDR_RES_HEAT_RANGE_ADDR, 1)
        heat_value = twos_comp(self._read(ADDR_RES_HEAT_VAL_ADDR, 1))
        sw_error = twos_comp(self._read(ADDR_RANGE_SW_ERR_ADDR, 1))

        self.calibration.set_from_array(calibration)
        self.calibration.set_other(heat_range, heat_value, sw_error)

    def soft_reset(self):
        """Trigger a soft reset."""
        self._write(SOFT_RESET_ADDR, SOFT_RESET_CMD)
        time.sleep(POLL_PERIOD_MS / 1000.0)

    def set_temp_offset(self, value):
        """Set temperature offset in celsius."""
        if value == 0:
            self.offset_temp_in_t_fine = 0
        else:
            self.offset_temp_in_t_fine = int(math.copysign((((int(abs(value) * 100)) << 8) - 128) / 5, value))

    def set_humidity_oversample(self, value):
        self._set_bits(CONF_OS_H_ADDR, OSH_MSK, OSH_POS, value)

    def set_pressure_oversample(self, value):
        self._set_bits(CONF_T_P_MODE_ADDR, OSP_MSK, OSP_POS, value)

    def set_temperature_oversample(self, value):
        self._set_bits(CONF_T_P_MODE_ADDR, OST_MSK, OST_POS, value)

    def set_filter(self, value):
        """Set IIR filter size. 
        Removes short term fluctuations from the temperature and pressure readings.
        Enabling the IIR filter does not slow down the time a reading takes, but will slow
        down the BME680s response to changes in temperature and pressure.
        """
        self._set_bits(CONF_ODR_FILT_ADDR, FILTER_MSK, FILTER_POS, value)

    def get_filter(self):
        return (self._read(CONF_ODR_FILT_ADDR, 1) & FILTER_MSK) >> FILTER_POS

    def select_gas_heater_profile(self, value):
        """Set current gas sensor conversion profile.
        Select one of the 10 configured heating durations/set points (0 to 9).
        """
        self._set_bits(CONF_ODR_RUN_GAS_NBC_ADDR, NBCONV_MSK, NBCONV_POS, value)

    def set_gas_status(self, value):
        """Enable/disable gas sensor."""
        self._set_bits(CONF_ODR_RUN_GAS_NBC_ADDR, RUN_GAS_MSK, RUN_GAS_POS, value)

    def set_gas_heater_temperature(self, value, nb_profile=0):
        """Set gas sensor heater temperature (degrees celsius, between 200 and 400)."""
        temp = int(self._calc_heater_resistance(value))
        self._write(RES_HEAT0_ADDR + nb_profile, temp)

    def set_gas_heater_duration(self, value, nb_profile=0):
        """Set gas sensor heater duration (in milliseconds between 1 ms and 4032 (typical 20~30 ms)."""
        temp = self._calc_heater_duration(value)
        self._write(GAS_WAIT0_ADDR + nb_profile, temp)

    def set_power_mode(self, value, blocking=True):
        """Set power mode."""
        if value not in (SLEEP_MODE, FORCED_MODE):
            raise ValueError('Power mode should be one of SLEEP_MODE or FORCED_MODE')

        self.power_mode = value

        self._set_bits(CONF_T_P_MODE_ADDR, MODE_MSK, MODE_POS, value)

        while blocking and self.get_power_mode() != self.power_mode:
            time.sleep(POLL_PERIOD_MS / 1000.0)

    def get_power_mode(self):
        """Get power mode."""
        self.power_mode = self._read(CONF_T_P_MODE_ADDR, 1)
        return self.power_mode

    def get_sensor_data(self):
        """Get sensor data"""
        self.set_power_mode(FORCED_MODE)

        for _ in range(10):
            status = self._read(FIELD0_ADDR, 1)

            if (status & NEW_DATA_MSK) == 0:
                time.sleep(POLL_PERIOD_MS / 1000.0)
                continue

            regs = self._read(FIELD0_ADDR, 17)

            self.status = regs[0] & NEW_DATA_MSK
            # Contains the nb_profile used to obtain the current measurement
            self.gas_index = regs[0] & GAS_INDEX_MSK
            self.meas_index = regs[1]

            self.adc_pres = (regs[2] << 12) | (regs[3] << 4) | (regs[4] >> 4)
            self.adc_temp = (regs[5] << 12) | (regs[6] << 4) | (regs[7] >> 4)
            self.adc_hum = (regs[8] << 8) | regs[9]
            self.adc_gas_res_low = (regs[13] << 2) | (regs[14] >> 6)
            self.gas_range_l = regs[14] & GAS_RANGE_MSK

            self.status |= regs[14] & GASM_VALID_MSK
            self.status |= regs[14] & HEAT_STAB_MSK

            self.heat_stable = (self.status & HEAT_STAB_MSK) > 0

            self.ambient_temperature = self.temperature

            return True

        return False

    def _set_bits(self, register, mask, position, value):
        """Mask out and set one or more bits in a register."""
        temp = self._read(register, 1)
        temp &= ~mask
        temp |= value << position
        self._write(register, temp)

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

    @property
    def temperature(self):
        """Convert the raw temperature to degrees C using calibration_data."""
        var1 = (self.adc_temp >> 3) - (self.calibration.par_t1 << 1)
        var2 = (var1 * self.calibration.par_t2) >> 11
        var3 = ((var1 >> 1) * (var1 >> 1)) >> 12
        var3 = ((var3) * (self.calibration.par_t3 << 4)) >> 14

        # Save teperature data for pressure calculations
        self.calibration.t_fine = (var2 + var3) + self.offset_temp_in_t_fine
        calc_temp = (((self.calibration.t_fine * 5) + 128) >> 8)

        return calc_temp / 100

    @property
    def pressure(self):
        """Convert the raw pressure using calibration data."""
        var1 = ((self.calibration.t_fine) >> 1) - 64000
        var2 = ((((var1 >> 2) * (var1 >> 2)) >> 11) * self.calibration.par_p6) >> 2
        var2 = var2 + ((var1 * self.calibration.par_p5) << 1)
        var2 = (var2 >> 2) + (self.calibration.par_p4 << 16)
        var1 = (((((var1 >> 2) * (var1 >> 2)) >> 13) *
                ((self.calibration.par_p3 << 5)) >> 3) +
                ((self.calibration.par_p2 * var1) >> 1))
        var1 = var1 >> 18

        var1 = ((32768 + var1) * self.calibration.par_p1) >> 15
        calc_pressure = 1048576 - self.adc_pres
        calc_pressure = ((calc_pressure - (var2 >> 12)) * (3125))

        if calc_pressure >= (1 << 31):
            calc_pressure = ((calc_pressure // var1) << 1)
        else:
            calc_pressure = ((calc_pressure << 1) // var1)

        var1 = (self.calibration.par_p9 * (((calc_pressure >> 3) *
                (calc_pressure >> 3)) >> 13)) >> 12
        var2 = ((calc_pressure >> 2) *
                self.calibration.par_p8) >> 13
        var3 = ((calc_pressure >> 8) * (calc_pressure >> 8) *
                (calc_pressure >> 8) *
                self.calibration.par_p10) >> 17

        calc_pressure = (calc_pressure) + ((var1 + var2 + var3 +
                                           (self.calibration.par_p7 << 7)) >> 4)

        return calc_pressure / 100

    @property
    def humidity(self):
        """Convert the raw humidity using calibration data."""
        temp_scaled = ((self.calibration.t_fine * 5) + 128) >> 8
        var1 = (self.adc_hum - ((self.calibration.par_h1 * 16))) -\
               (((temp_scaled * self.calibration.par_h3) // (100)) >> 1)
        var2 = (self.calibration.par_h2 *
                (((temp_scaled * self.calibration.par_h4) // (100)) +
                 (((temp_scaled * ((temp_scaled * self.calibration.par_h5) // (100))) >> 6) //
                 (100)) + (1 * 16384))) >> 10
        var3 = var1 * var2
        var4 = self.calibration.par_h6 << 7
        var4 = ((var4) + ((temp_scaled * self.calibration.par_h7) // (100))) >> 4
        var5 = ((var3 >> 14) * (var3 >> 14)) >> 10
        var6 = (var4 * var5) >> 1
        calc_hum = (((var3 + var6) >> 10) * (1000)) >> 12

        return min(max(calc_hum, 0), 100000) / 1000

    @property
    def gas(self):
        """Convert the raw gas resistance using calibration data."""
        var1 = ((1340 + (5 * self.calibration.range_sw_err)) * (lookupTable1[self.gas_range_l])) >> 16
        var2 = (((self.adc_gas_res_low << 15) - (16777216)) + var1)
        var3 = ((lookupTable2[self.gas_range_l] * var1) >> 9)
        calc_gas_res = ((var3 + (var2 >> 1)) / var2)

        if calc_gas_res < 0:
            calc_gas_res = (1 << 32) + calc_gas_res

        return calc_gas_res

    def _calc_heater_resistance(self, temperature):
        """Convert raw heater resistance using calibration data."""
        temperature = min(max(temperature, 200), 400)

        var1 = ((self.ambient_temperature * self.calibration.par_gh3) / 1000) * 256
        var2 = (self.calibration.par_gh1 + 784) * (((((self.calibration.par_gh2 + 154009) * temperature * 5) / 100) + 3276800) / 10)
        var3 = var1 + (var2 / 2)
        var4 = (var3 / (self.calibration.res_heat_range + 4))
        var5 = (131 * self.calibration.res_heat_val) + 65536
        heatr_res_x100 = (((var4 / var5) - 250) * 34)
        heatr_res = ((heatr_res_x100 + 50) / 100)

        return heatr_res

    def _calc_heater_duration(self, duration):
        """Calculate correct value for heater duration setting from milliseconds."""
        if duration < 0xfc0:
            factor = 0

            while duration > 0x3f:
                duration /= 4
                factor += 1

            return int(duration + (factor * 64))

        return 0xff