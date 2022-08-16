# Created by Steven Boonstoppel
import machine
import time
import math

class MAX4466:
    def __init__(self, pin, duration = 500):
        adc = machine.ADC()
        self.adc = adc.channel(pin = pin, attn = machine.ADC.ATTN_11DB) # 0 to 4095 accuracy
        self.duration = duration                    # integration time in milliseconds
        self.sens_dB = 44                           # factory sensitivity -44 dB re 1V/Pa (https://cdn-shop.adafruit.com/datasheets/CMA-4544PF-W.pdf)
        self.sens_v = 0.00631                       # equivalent of above in V/Pa
        self.gain = 25                              # amp gain (fully anticlockwise)

    def get_volume(self):
        # take large number of samples over 'duration' time to find largest sound pressure (>13000 samples per second measured)
        sigMin = 4095
        sigMax = 0
        t1 = time.ticks_ms()
        while time.ticks_ms() - t1 < self.duration:
            val = self.adc.voltage()                # get current voltage
            sigMin = min(sigMin, val)               # save lowest peak
            sigMax = max(sigMax, val)               # save highest peak

        # calculation from https://forums.adafruit.com/viewtopic.php?f=8&t=100462
        peakToPeak = sigMax - sigMin
        volts = peakToPeak / 1000 * 0.707           # divide to get voltage, calculate RMS voltage
        dB = 20 * (math.log(volts / self.sens_v) / math.log(10))    # this is pure physics (plus log_e conversion to log_10)
        dBspl = 1.5 * dB + 94 - self.sens_dB - self.gain - 15       # 94 is default offset, and 1.5 and -15 are abnormal physics but yield far better results
        return dBspl