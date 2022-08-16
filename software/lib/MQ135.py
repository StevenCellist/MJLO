import machine
import time

class MQ135(object):
    RLOAD = 10.0    # The load resistance on the board
    RZERO = 76.63   # Calibration resistance at atmospheric CO2 level

    # Parameters for calculating ppm of CO2 from sensor resistance
    PARA = 116.6020682  
    PARB = 2.769034857

    # Parameters to model temperature and humidity dependence
    CORA = 0.00035
    CORB = 0.02718
    CORC = 1.39538
    CORD = 0.0018
    CORE = -0.003333333
    CORF = -0.001923077
    CORG = 1.130128205
    
    ATMOCO2 = 397.13    # Atmospheric CO2 level for calibration purposes

    def __init__(self, pin, duration = 50):
        adc = machine.ADC()
        self.adc = adc.channel(pin = pin, attn = machine.ADC.ATTN_11DB) # 0 to 4095 accuracy
        self.duration = duration                                        # integration time in milliseconds

    def get_correction_factor(self, temperature, humidity):
        """Calculates the correction factor for ambient air temperature and relative humidity
        Based on the linearization of the temperature dependency curve
        under and above 20 degrees Celsius, asuming a linear dependency on humidity,
        provided by Balk77 https://github.com/GeorgK/MQ135/pull/6/files
        """
        if temperature < 20:
            return self.CORA * temperature * temperature - self.CORB * temperature + self.CORC - (humidity - 33.) * self.CORD
        else:
            return self.CORE * temperature + self.CORF * humidity + self.CORG

    def get_resistance(self):
        """Returns the resistance of the sensor in kOhms // -1 if not value got in pin"""
        val = 0
        n = 0
        t1 = time.ticks_ms()
        while time.ticks_ms() - t1 < self.duration:
            val += self.adc.value()
            n += 1
        
        avg_val = val / n                       # find average measured value
        if avg_val == 0:
            return -1

        return (4095./avg_val - 1.) * self.RLOAD

    def get_corrected_resistance(self, temperature, humidity):
        """Gets the resistance of the sensor corrected for temperature/humidity"""
        return self.get_resistance()/ self.get_correction_factor(temperature, humidity)

    def get_corrected_ppm(self, temperature, humidity):
        """Returns the ppm of CO2 sensed (assuming only CO2 in the air)
        corrected for temperature/humidity"""
        g_cr = self.get_corrected_resistance(temperature, humidity)
        try:
            return self.PARA * ((g_cr / self.RZERO)**-self.PARB)
        except:
            return 0

    def get_rzero(self):
        """Returns the resistance RZero of the sensor (in kOhms) for calibration purposes"""
        return self.get_resistance() * (self.ATMOCO2/self.PARA)**(1./self.PARB)

    def get_corrected_rzero(self, temperature, humidity):
        """Returns the resistance RZero of the sensor (in kOhms) for calibration purposes
        corrected for temperature/humidity"""
        return self.get_corrected_resistance(temperature, humidity) * (self.ATMOCO2/self.PARA)**(1./self.PARB)