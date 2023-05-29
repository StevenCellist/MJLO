#_main.py -- frozen into the firmware along all other modules
version_str = "v2.7.1"
version_int = int(version_str.replace('v', '').replace('.', ''))

import time
import pycom
import machine

t_boot = time.ticks_ms()                                # save current boot time

USE_SD   = machine.reset_cause() == machine.PWRON_RESET # check SD card if there was a reset / poweron
USE_GPS  = machine.reset_cause() == machine.PWRON_RESET # use GPS if there was a reset / poweron
USE_GPS |= machine.reset_cause() == machine.WDT_RESET   # use GPS if there was an update or error last time
USE_GPS |= machine.wake_reason()[0] == machine.PIN_WAKE # use GPS if the green button was pressed

import pins
from lib.SSD1306  import SSD1306
from lib.VEML6070 import VEML6070
from lib.TSL2591  import TSL2591
from lib.BME680   import BME680
from lib.MAX4466  import MAX4466
from lib.KP26650  import KP26650
from lib.SCD41    import SCD41
from lib.SDS011   import SDS011
from LoRa         import LoRaWAN

from ucollections import OrderedDict

i2c = machine.I2C(0, pins = (pins.SDA, pins.SCL))       # create I2C object
display = SSD1306(128, 64, i2c)                         # initialize display (4.4 / 0.0 mA)

# update firmware register if necessary, and check for SD card updates
if USE_SD:
    if pycom.nvs_get('fwversion') != version_int:
        pycom.nvs_set('fwversion', version_int)
    if pycom.nvs_get('error'):
        pycom.nvs_set('error', 0)

    from updateFW import check_SD
    reboot = check_SD(display)                          # check if an SD card is present and apply any changes
    if reboot:
        machine.reset()                                 # in case of an update, reboot the device

# enable power to the voltage regulator (and in turn SDS011) which requires most time
vr_en = machine.Pin(pins.VR, mode = machine.Pin.OUT)    # voltage regulator SHDN pin
vr_en.hold(False)                                       # disable hold from deepsleep
vr_en.value(1)                                          # enable power

uart1 = machine.UART(1, pins = (pins.TX1, pins.RX1), baudrate = 9600) # UART communication to SDS011
sds011 = SDS011(uart1)                                  # fine particle sensor (110 / 0.0 mA)
sds011.wake()

t_start = time.ticks_ms()                               # keep track of SDS011 wake time

lora = LoRaWAN()                                        # sort out all LoRa related settings (frame count, port, sf)

# if necessary, powerup GPS in advance (powered through voltage regulator)
if USE_GPS:
    gps_en = machine.Pin(pins.GPS, mode = machine.Pin.OUT)  # 2N2907 (PNP) gate pin
    gps_en.hold(False)                                  # disable hold from deepsleep
    gps_en.value(0)                                     # enable GPS power
    lora.fport = 2                                      # set LoRa decoding type 2 (includes GPS)
    lora.sf = pycom.nvs_get('sf_h')                     # send GPS on high SF

# show some stats on screen while sensors are busy
display.fill(0)
display.text("MJLO-{:>02}" .format(pycom.nvs_get('node')), 1,  1)
display.text("FW {}"       .format(version_str),           1, 11)
display.text("sf    {:> 4}".format(lora.sf),               1, 34)
display.text("fport {:> 4}".format(lora.fport),            1, 44)
display.text("fcnt {:> 5}" .format(lora.fcnt),             1, 54)
display.show()

# start collection of all sensor data
values = OrderedDict()                                  # ordered collection of all values

bme680 = BME680(i2c = i2c, address = 119)               # temp, hum, pres & voc sensor (12 / 0.0 mA) (0x77)
bme680.set_gas_heater_temperature(400, nb_profile = 1)  # set VOC plate heating temperature
bme680.set_gas_heater_duration(50, nb_profile = 1)      # set VOC plate heating duration
bme680.select_gas_heater_profile(1)                     # select those settings
while not bme680.get_sensor_data():
    machine.sleep(200)
values['temp'] = bme680.temperature
values['humi'] = bme680.humidity
values['pres'] = bme680.pressure
values['voc']  = bme680.gas / 10                        # TODO solve VOC (dirty hack /10)
bme680.set_power_mode(0)

tsl2591 =  TSL2591(i2c = i2c, address = 41)             # lux sensor (0.4 / 0.0 mA) (0x29)
tsl2591.wake()
values['lx'] = tsl2591.lux                              # don't ask why but this may do nothing, so poll twice
machine.sleep(200)                                      # sensor stabilization time
values['lx'] = tsl2591.lux
tsl2591.sleep()

veml6070 = VEML6070(i2c = i2c, address = 56)            # UV sensor (0.4 / 0.0 mA) (0x38)
veml6070.wake()
values['uv'] = veml6070.uv_raw                          # don't ask why but this may do nothing, so poll twice
machine.sleep(200)                                      # sensor stabilization time
values['uv'] = veml6070.uv_raw
veml6070.sleep()

max4466 =  MAX4466(pins.Vol, duration = 500)            # analog loudness sensor (500ms measurement)
values['volu'] = max4466.get_volume()                   # active: 0.3 mA, sleep: 0.3 mA (always on)

battery =  KP26650(pins.Batt, duration = 200, ratio = 2)# battery voltage (200ms measurement, 1:1 voltage divider)
values['batt'] = battery.get_voltage()
perc = battery.get_percentage(lb = 3.1, ub = 4.3)       # map voltage from 3.1..4.3 V to 0..100%

# write first set of values to display
display.fill(0)
display.text("Temp: {:> 6} C"   .format(round(values['temp'], 1)), 1,  1)
display.text("Druk:{:> 6} hPa"  .format(round(values['pres'], 1)), 1, 11)
display.text("Vocht: {:> 5} %"  .format(round(values['humi'], 1)), 1, 21)
display.text("Licht: {:> 5} lx" .format(round(values[  'lx']   )), 1, 31)
display.text("UV: {:> 8}"       .format(round(values[  'uv']   )), 1, 41)
display.text("Accu: {:> 6} %"   .format(round(        perc     )), 1, 54)
display.show()

scd41 =    SCD41(i2c = i2c, address = 98)               # CO2 sensor (50 / 0.2 mA) (0x62)
scd41.wake()
machine.sleep(200)                                      # apparently needs some extra time to wake
scd41.measure_single_shot()                             # start measurement, takes 5 seconds to complete
machine.sleep(5000)
values['co2'] = scd41.CO2
scd41.sleep()

# sleep for the remainder of 25 seconds
machine.sleep(25000 - time.ticks_diff(time.ticks_ms(), t_start)) 

# try to get a response from SDS011 within 5 seconds
while (not sds011.read() and time.ticks_diff(time.ticks_ms(), t_start) < 30000):
    machine.sleep(200)

values['pm25'] = sds011.pm25
values['pm10'] = sds011.pm10
sds011.sleep()

t_stop = time.ticks_ms()

# write second set of values to display
display.fill(0)
display.text("Volume: {:> 4} dB".format(round(values['volu']   )), 1,  1)
display.text("VOC: {:> 7}"      .format(round(values[ 'voc']   )), 1, 11)
display.text("CO2: {:> 7} ppm"  .format(round(values[ 'co2']   )), 1, 21)
display.text("PM2.5: {:> 5} ppm".format(round(values['pm25'], 1)), 1, 31)
display.text("PM10: {:> 6} ppm" .format(round(values['pm10'], 1)), 1, 41)
display.text("Accu: {:> 6} %"   .format(round(        perc     )), 1, 54)
display.show()

# if necessary, start reading GPS to get a location fix
if USE_GPS:
    
    # the GPS module has a pulling rate of 1Hz
    # therefore, if there is no data present within 2 seconds, raise an error
    uart2 = machine.UART(2, pins = (pins.TX2, pins.RX2), baudrate = 9600)
    time.sleep_ms(2000)
    if not uart2.any():
        raise ModuleNotFoundError

    from lib.micropyGPS import MicropyGPS
    gps = MicropyGPS()                                  # create GPS object

    t = time.ticks_ms()
    # THIS IS A BLOCKING CALL!! there MUST be a reasonable fix before sending data
    while not gps.valid or gps.hdop > 5:
        while uart2.any():                              # wait for incoming communication
            my_sentence = uart2.readline()              # read NMEA sentence
            for x in my_sentence:
                gps.update(chr(x))                      # decode it through micropyGPS

            # every two seconds, update some stats on the display
            if (time.ticks_ms() - t) > 2000:
                display.fill(0)
                display.text("GPS stats:",                                          1,  1)
                display.text("fix:  {:> 4}"  .format("yes" if gps.valid else "no"), 1, 11)
                display.text("hdop: {:> 4}"  .format(round(gps.hdop, 1)),           1, 21)
                display.text("sats: {:> 4}"  .format(gps.satellites),               1, 31)
                display.text("time: {:> 4} s".format(round(t/1000)),                1, 41)
                display.show()
                t = time.ticks_ms()

    gps_en.value(1)                                     # disable power to GPS module
    gps_en.hold(True)                                   # hold through deepsleep

    values['lat'] = gps.latitude
    values['long'] = gps.longitude
    values['alt'] = gps.altitude
    values['hdop'] = gps.hdop

    values['fw'] = pycom.nvs_get('fwversion') % 100     # add current firmware version to values (two trailing numbers)

vr_en.value(0)                                          # disable voltage regulator
vr_en.hold(True)                                        # hold pin low during deepsleep

# if LoRa failed to join, perform a reset which causes the device to restart from the top
if not lora.has_joined:
    machine.reset()

lora.make_frame(values)
lora.send_frame()

# show values on display for the remainder of 10 seconds
machine.sleep(10000 - time.ticks_diff(time.ticks_ms(), t_stop))
display.poweroff()

# if there was an error last time, but we got here now, set register to 0
if pycom.nvs_get("error"):
    pycom.nvs_set("error", 0)

# set up for deepsleep
awake_time = time.ticks_diff(time.ticks_ms(), t_boot) - 3000                    # time in milliseconds the program has been running
machine.Pin(pins.Wake, mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)     # initialize wake-up pin
machine.pin_sleep_wakeup([pins.Wake], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
machine.deepsleep(pycom.nvs_get('t_int') * 1000 - awake_time)                   # deepsleep for remainder of the interval time