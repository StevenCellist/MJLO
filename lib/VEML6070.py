from machine import I2C

class VEML6070(object):
    _VEML6070_RISK_LEVEL = { "LOW": [0, 560],
                             "MODERATE": [561, 1120],
                             "HIGH": [1121, 1494],
                             "VERY HIGH": [1495, 2054],
                             "EXTREME": [2055, 9999]
                           }
    def __init__(self, i2c=None):
        self.i2c = i2c
        self.UVindex = 0
        self.UVrisk = "LOW"
        devices = i2c.scan()
        address = 56
        if address not in devices:
            raise ValueError('VEML6070 not found. Please check wiring.')
        setup = bytearray(1)
        setup[0] = 0b00000110
        i2c.writeto(56, setup)
    def getMeasurement(self):
        buflow = self.i2c.readfrom(56,1)
        bufhigh = self.i2c.readfrom(57,1)
        buf = bufhigh[0] <<8
        buf |= buflow[0]
        self.UVindex = buf
        adjusted = int(buf/1)
        for levels in self._VEML6070_RISK_LEVEL:
            tmp_range = range(self._VEML6070_RISK_LEVEL[levels][0],
                              self._VEML6070_RISK_LEVEL[levels][1])
            if adjusted in tmp_range:
                self.UVrisk = levels
                break
