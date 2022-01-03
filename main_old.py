# MicroPython imports.
import socket
from time import sleep, ticks_ms
import ubinascii
from machine import UART, Pin, ADC, deepsleep
from network import LoRa
import machine

# own imports.
from lib.MAX4466 import MAX4466
from lib.cayenneLPP import CayenneLPP
from lib.SDS011 import SDS011
from lib.VEML6070 import VEML6070
from lib.TSL2591 import TSL2591
from lib.BME680 import BME680
from lib.MQ135 import MQ135

import settings

i2c_bus = i2c_bus
display = display
gps = gps

# as these sensors take 30 seconds to stabilize, start them as very first thing!
com = UART(1, pins=("P20", "P19"), baudrate=9600)   # UART communication to SDS011
sds011 = SDS011(com)                                # fine particle sensor
sds011.wake()                                       # active: 66 mA, sleep: 3.1 mA

mq135_en = Pin('P12', mode=Pin.OUT)                 # MQ135 VIN pin
mq135_en.value(1)                                   # preheat
mq135 = MQ135('P17')                                # active: 40 mA, sleep: 0.0 mA

wake_time = ticks_ms()                              # save current time

#%% connect to LoRa
if settings.DEBUG_MODE == False:

    # create LoRa object
    lora = LoRa(mode = settings.LORA_MODE, region = settings.LORA_REGION)

    # get wake reason
    (wake_reason, gpio_list) = machine.wake_reason()

    # if we woke from deepsleep, restore the LoRa information from RAM
    if wake_reason == machine.DEEPSLEEP_RESET:
        lora.nvram_restore()

    # otherwise, join the network
    else:
        app_eui = ubinascii.unhexlify(settings.APP_EUI)
        app_key = ubinascii.unhexlify(settings.APP_KEY)
        
        lora.join(activation = settings.LORA_ACTIVATION, auth = (app_eui, app_key), timeout = 0)
        display.text("Verbinden...", 1, 1)
        display.show()

        while not lora.has_joined():
            print('Verbinden met LoRaWAN...')
            sleep(1)

    print('Verbonden!')
    display.fill(0)
    display.text("Verbonden!", 1, 1)

    # create a LoRa socket.
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    # set the LoRaWAN data rate.
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)          # TODO use at least SF9 as configured in TTN.. but rather SF12
    s.setblocking(True)
    lpp = CayenneLPP(size = 110, sock = s)

else:
    display.text("Debug modus...", 1, 1)


#%% start other sensors
display.text("Sensoren starten", 1, 11)
display.show()

bme680 =      BME680(i2c=i2c_bus, address=0x77)     # temp, pres, hum, VOC sensor
                                                    # active: 22 mA, sleep: 0.7 mA (forced query mode)

veml6070 = VEML6070(i2c=i2c_bus, address=56)        # UV sensor
veml6070.sleep()                                    # active: 0.0 mA, sleep: 0.0 mA

tsl2591 = TSL2591(i2c=i2c_bus, address=0x29)        # lux sensor
tsl2591.sleep()                                     # active: 0.0 mA, sleep: 0.0 mA

max4466 = MAX4466('P18')                            # analog loudness sensor
                                                    # active: 0.3 mA, sleep: 0.3 mA (always on)

adc = ADC()
volt_pin = adc.channel(pin = 'P15', attn=ADC.ATTN_11DB)  # analog voltage sensor

display.fill(0)
display.poweroff()                                  # active: ~5 mA, sleep: 0.0 mA

#%% process sensor values
def send_values(display_on = False):
    if settings.DEBUG_MODE == False:
        # create cayenne LPP packet
        lpp.add_analog_input(batt_volt, channel = 0) #Voltage measurement, 2 bites with fractions
        lpp.add_temperature(temperature, channel = 1) #temp
        lpp.add_barometric_pressure(pressure, channel = 2)
        lpp.add_relative_humidity(humidity, channel = 3) #humidity 0-100%   #see this url: https://www.thethingsnetwork.org/forum/t/cayenne-lpp-format-analog-data-wrong/14676
        lpp.add_luminosity(loudness, channel = 4)    #loudness 0-4096
        lpp.add_luminosity(light, channel = 5) #lux 2 bytes unsinged
        lpp.add_luminosity(uv_raw, channel = 6) #UV sensor2 byte unsigned
        lpp.add_luminosity(voc, channel = 7) #TVOC from 0 to 1187 ppb
        lpp.add_luminosity(ppm_co2, channel = 8) #CO2 in 400-8192 ppm
        lpp.add_barometric_pressure(pm_25, channel = 9) #pm25 0.0-999.9 ug/m3 (2 bytes unsigned) #TODO: Find out if it is better to use unsigned fields for these
        lpp.add_barometric_pressure(pm_100, channel = 10)   #pm 10
        lpp.add_gps(gps.latitude, gps.longitude, gps.altitude, channel = 11)
        lpp.send(reset_payload = True)
    else:
        # print all of the sensor values via REPL (serial)
        print("GPS: NB %f, OL %f, H %f" % (gps.latitude, gps.longitude, gps.altitude))
        print("Luchtdruk: %.2f"         % pressure)
        print("Temperatuur: %.2f "      % temperature)
        print("Luchtvochtigheid: %d"    % humidity)
        print("Fijnstof 2.5, 10: %.2f, %.2f" % (pm_25, pm_100))
        print("Volume: %d"              % loudness)
        print("VOC, CO2: %d %d"         % (voc, ppm_co2))
        print("UV index, risk: %d, %s"  % (uv_raw, uv_index))
        print("Lux: %d"                 % light)
        print("Voltage: %.3f, %d %%"    % (batt_volt, batt_perc))

    if display_on:
        # display all sensor data on display
        display.poweron()
        display.text("Temp: %.2f"     % temperature, 1,  1)
        display.text("Druk: %.2f "    % pressure,    1, 11)
        display.text("Vocht: %d %%"   % humidity,    1, 21)
        display.text("Lux: %d"        % light,       1, 31)
        display.text("UV index: %s"   % uv_index,    1, 41)
        display.text("Accu: ~ %d %%"  % batt_perc,   1, 54)
        display.show()
        sleep(settings.DISPLAY_TIME)
        display.fill(0)
        display.text("Stof 2.5: %.2f" % pm_25,     1,  1)
        display.text("Stof 10: %.2f"  % pm_100,    1, 11)
        display.text("VOC: %d"        % voc,       1, 21)
        display.text("CO2: %d"        % ppm_co2,   1, 31)
        display.text("Volume: %d"     % loudness,  1, 41)
        display.text("Accu: ~ %d %%"  % batt_perc, 1, 54)
        display.show()
        sleep(settings.DISPLAY_TIME)
        display.fill(0)
        display.poweroff()


#%% get sensor values and put sensors to sleep immediately after

while (ticks_ms() - wake_time) < settings.WAKE_TIME:
    sleep(0.5)

while not sds011.read():
    sleep(0.1)

pm_25 = sds011.pm25
pm_100 = sds011.pm10
sds011.sleep()

temperature = bme680.temperature
humidity =    bme680.relative_humidity
pressure =    bme680.pressure
voc =         bme680.gas

ppm_co2 = mq135.get_corrected_ppm(temperature, humidity)
mq135_en.value(0)

veml6070.wake()
sleep(0.1)
uv_raw = veml6070.uv_raw
uv_index = veml6070.get_index(uv_raw)
veml6070.sleep()

tsl2591.wake()
sleep(0.1)
light = tsl2591.calculate_lux()
tsl2591.sleep()

loudness = max4466.value()

batt_volt = volt_pin.voltage() * 2 / 1000
batt_perc = (batt_volt - 3.2) * 100         # calculate approx. battery percentage, assuming a range of 3.3 to 4.3 Volts on the battery

send_values(display_on=True)


#%% hibernate, but restart to GPS mode if push button is pressed
push_button = Pin('P23', mode=Pin.IN, pull=Pin.PULL_DOWN)
machine.pin_sleep_wakeup(['P23'], mode=machine.WAKEUP_ANY_HIGH, enable_pull=True)

lora.nvram_save()                           # save LoRa information to RAM
deepsleep(settings.SLEEP_TIME * 1000)