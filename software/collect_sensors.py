import machine
import time
from ucollections import OrderedDict

import pins
from lib.VEML6070 import VEML6070
from lib.TSL2591 import TSL2591
from lib.BME680 import BME680
from lib.MAX4466 import MAX4466
from lib.KP26650 import KP26650

def run_collection(i2c, all_sensors, t_wake = 30):

    values = OrderedDict()                                          # collection of all values, to be returned

    bme680 = BME680(i2c = i2c, address = 119)
    bme680.set_gas_heater_temperature(400, nb_profile = 1)          # set VOC plate heating temperature
    bme680.set_gas_heater_duration(50, nb_profile = 1)              # set VOC plate heating duration
    bme680.select_gas_heater_profile(1)                             # select those settings
    while not bme680.get_sensor_data():
        time.sleep_ms(10)
    values['temp'] = bme680.temperature
    values['humi'] = bme680.humidity
    values['pres'] = bme680.pressure
    values['voc'] = bme680.gas
    bme680.set_power_mode(0)

    tsl2591 =  TSL2591(i2c = i2c, address = 41)                     # lux sensor (0.4 / 0.0 mA) (0x29)
    tsl2591.wake()
    values['lx'] = tsl2591.lux
    time.sleep(0.2)                                                 # sensor stabilization time (required!!)
    values['lx'] = tsl2591.lux
    tsl2591.sleep()
    
    veml6070 = VEML6070(i2c = i2c, address = 56)                    # UV sensor (0.4 / 0.0 mA) (0x38)
    veml6070.wake()
    values['uv'] = veml6070.uv_raw
    time.sleep(0.2)                                                 # sensor stabilization time (required!!)
    values['uv'] = veml6070.uv_raw                                  # first poll may fail so do it twice
    veml6070.sleep()

    max4466 =  MAX4466(pins.Vol, duration = 200)                    # analog loudness sensor (200ms measurement)
    values['volu'] = max4466.get_volume()                           # active: 0.3 mA, sleep: 0.3 mA (always on)
    
    battery = KP26650(pins.Batt, duration = 50, ratio = 2)          # battery voltage (50ms measurement, 1:1 voltage divider)
    values['volt'] = battery.get_voltage()
    perc = battery.get_percentage(values['volt'], lb = 3.3, ub = 4.2) # map voltage from 3.3..4.2 V to 0..100%

    if all_sensors == True:
        from lib.SDS011 import SDS011
        from lib.MQ135 import MQ135

        regulator = machine.Pin(pins.VR, mode = machine.Pin.OUT)    # voltage regulator SHDN pin
        regulator.hold(False)                                       # disable hold from deepsleep
        regulator.value(1)                                          # start SDS011 and MQ135

        com = machine.UART(1, pins=(pins.TX1, pins.RX1), baudrate = 9600) # UART communication to SDS011
        sds011 = SDS011(com)                                        # fine particle sensor (70 / 0.0 mA)

        mq135 = MQ135(pins.CO2, duration = 50)                      # CO2 sensor (200 / 0.0 mA)

        machine.sleep(t_wake * 1000)                                # wait for ~25 seconds

        values['co2'] = mq135.get_corrected_ppm(values['temp'], values['humi'])

        t1 = time.ticks_ms()
        while (not sds011.read() and time.ticks_ms() - t1 < 5000):  # try to get a response from SDS011 within 5 seconds
            time.sleep_ms(10)

        values['pm25'] = sds011.pm25
        values['pm10'] = sds011.pm10
        regulator.value(0)          # disable voltage regulator
        regulator.hold(True)        # hold pin low during deepsleep

    return values, perc