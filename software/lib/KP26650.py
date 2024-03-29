# Created by Steven Boonstoppel
import machine
import time

class KP26650:
    def __init__(self, pin, duration = 50, ratio = 2):
        adc = machine.ADC()
        self.adc = adc.channel(pin = pin, attn = machine.ADC.ATTN_11DB) # 0 to 4095 accuracy
        self.duration = duration                                        # integration time in milliseconds
        self.ratio = ratio
        self.avg_volt = 0

    def get_voltage(self):
        # take 'n' samples over 'duration' time to find average voltage across divider
        val = 0
        n = 0
        t1 = time.ticks_ms()
        while time.ticks_ms() - t1 < self.duration:
            val += self.adc.voltage()
            n += 1
        
        avg_val = val / n                           # find average measured value
        self.avg_volt = avg_val / 1000 * self.ratio # convert mV -> V, multiply by certain ratio due to voltage divider
        return self.avg_volt

    def get_percentage(self, lb, ub):
        # return a value between 0..100% from lower bound to upper bound
        return max(0, min(100, (self.avg_volt - lb) / (ub - lb) * 100))