import time
from machine import ADC

class MAX4466:
    def __init__(self, Pin):
        adc = ADC()
        self.adc_c = adc.channel(pin=Pin, attn = ADC.ATTN_11DB)

    def value(self):
        return self.adc_c.value()
