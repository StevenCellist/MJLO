import time
import lib.sds011

class PMSensor:
    """A class to handle the fine particle sensor.
    :param uart: The `UART` object to use.
    :param meas_dur: time duration of the FAN before the measure (in ms).
    """
    def __init__(self, uart, meas_dur):
        #Declare an SDS011 object
        self._sds011 = sds011.SDS011(uart)

        #Stop fan
        self._sds011.sleep()

        #True if fan is (supposed to be) ON, False otherwise
        self._fan_status = False
        self._fan_time_running = None

        #Timing for measure
        self._meas_dur = meas_dur
        self._last_meas_time = None

        #Attributes for PM25 and PM10
        self._pm25 = None
        self._pm10 = None

    def startFAN(self):
        #if sensors not enable => Enable it and start timer
        if(self._fan_status is False):
            self._sds011.wake()
            self._fan_time_running = time.ticks_ms()
            self._fan_status = True

    def work(self):
        """Checks the fan time and last_meas_time. Stops the FAN every
        meas_dur in miliseconds, then do a measurement.
        returns True or False
        """
        if(self._fan_status is False):
            self.startFAN()

        if( ((self._last_meas_time is None) or (time.ticks_diff(self._last_meas_time, time.ticks_ms()) >= self._meas_dur)) and (time.ticks_diff(self._fan_time_running, time.ticks_ms()) >= self._meas_dur)):

            #Do measurement of the other sensors
            self._last_meas_time = time.ticks_ms()
            self._sds011.read()
            self._pm25 = self._sds011.pm25
            self._pm10 = self._sds011.pm10

            #Stop FAN
            self._sds011.sleep()
            self._fan_status = False

            return True

        return False

    def get_pm25(self):
        """Return last read PM 2.5µm concentration (in ppm) or None if last reading
        failed.
        """
        ret_val = self._pm25
        return ret_val

    def get_pm10(self):
        """Return last read PM 10µm concentration (in ppm) different from zero, None if last reading
        failed.
        """
        ret_val = self._pm10
        return ret_val