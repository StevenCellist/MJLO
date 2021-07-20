import time
from machine import ADC

class MAX4466:
    def __init__(self):
        adc = ADC()
        self.adc_c = adc.channel(pin='P18', attn = ADC.ATTN_11DB)

    def value(self):
        return self.adc_c.value()