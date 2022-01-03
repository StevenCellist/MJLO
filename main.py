#%% imports
from time import sleep, ticks_ms
import ubinascii
from machine import Pin, ADC, RTC, I2C
from network import LoRa
import machine
import struct
import socket

from lib.cayenneLPP import CayenneLPP
from lib.VEML6070 import VEML6070
from lib.TSL2591 import TSL2591
from lib.BME680 import BME680
from lib.MQ135 import MQ135
from lib.SSD1306 import SSD1306
from lib.micropyGPS import MicropyGPS
import settings


sds011 = sds011
mq135_en = mq135_en
wake_time = wake_time

# set up display and GPS (TODO)
i2c_bus = I2C(0, I2C.MASTER)
display = SSD1306(128, 64, i2c_bus)                 # active: ~5 mA, sleep: 0.0 mA
gps = MicropyGPS()


#%% setup LoRa
lora = LoRa(mode = LoRa.LORAWAN, region = LoRa.EU868)       # create LoRa object
lora.nvram_restore()                                        # restore the LoRa information from nvRAM

if settings.DEBUG_MODE == False:

    # if LoRa was not (correctly) restored from nvRAM, try to connect
    if not lora.has_joined():
        app_eui = ubinascii.unhexlify(settings.APP_EUI)
        app_key = ubinascii.unhexlify(settings.APP_KEY)
            
        lora.join(activation = LoRa.OTAA, auth = (app_eui, app_key), timeout = 0)
        display.text("Verbinden...", 1, 1)
        display.show()

        print('Verbinden met LoRaWAN')
        while not lora.has_joined():
            print('.', end = '')
            sleep(0.2)

    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)      # # create a LoRa socket.
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)          # set the LoRaWAN data rate. TODO use at least SF9 as configured in TTN.. but rather SF12
    s.setblocking(True)
    lpp = CayenneLPP(size = 110, sock = s)                  # TODO size is 54 bytes in theory: evaluate SF12 (51 bytes)

    print('Verbonden met LoRa!')
    display.text("Verbonden!", 1, 11)

else:
    print("Debug mode")


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
        lpp.add_barometric_pressure(pm_25, channel = 9) #pm25 0.0-999.9 ug/m3 (2 bytes unsigned) TODO: Find out if it is better to use unsigned fields for these
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
        print("UV index, risk: %d, %s"  % (uv_raw, "LOW"))
        print("Lux: %d"                 % light)
        print("Voltage: %.3f, %d %%"    % (batt_volt, batt_perc))

    if display_on:
        # display all sensor data on display
        display.poweron()
        display.fill(0)
        display.text("Temp: %.2f"     % temperature, 1,  1)
        display.text("Druk: %.2f "    % pressure,    1, 11)
        display.text("Vocht: %d %%"   % humidity,    1, 21)
        display.text("Lux: %d"        % light,       1, 31)
        display.text("UV index: %s"   % "LOW",    1, 41)
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

#%% retrieve sensor values from RTC memory
# get access to RTC module for deepsleep memory
rtc = RTC()

delimiter = b'\x21\x21'  # TODO might need better delimiter, but this has never given any errors yet

# restore values of previous cycle from psRAM (returns None if not set) and process them
previous_values = rtc.memory()
if previous_values:
    previous_values = previous_values.split(delimiter)
    batt_volt = struct.unpack('f', previous_values[0])[0]
    temperature = struct.unpack('f', previous_values[1])[0]
    pressure  = struct.unpack('f', previous_values[2])[0]
    humidity = struct.unpack('f', previous_values[3])[0]
    loudness = struct.unpack('i', previous_values[4])[0]
    light = struct.unpack('i', previous_values[5])[0]
    uv_raw = struct.unpack('i', previous_values[6])[0]
    voc = struct.unpack('i', previous_values[7])[0]
    ppm_co2 = struct.unpack('i', previous_values[8])[0]
    pm_25 = struct.unpack('f', previous_values[9])[0]
    pm_100 = struct.unpack('f', previous_values[10])[0]

    # calculate approx. battery percentage, assuming a range of 3.25 to 4.25 Volts on the battery
    batt_perc = (batt_volt - 3.25) * 100

    send_values(display_on = True)

#%% start other sensors
bme680 =     BME680(i2c=i2c_bus, address=0x77)              # temp, pres, hum, VOC sensor
                                                            # active: 22 mA, sleep: 0.7 mA (forced query mode)
veml6070 = VEML6070(i2c=i2c_bus, address=56)                # UV sensor
veml6070.sleep()                                            # active: 0.0 mA, sleep: 0.0 mA
tsl2591 =  TSL2591(i2c=i2c_bus, address=0x29)               # lux sensor
tsl2591.sleep()                                             # active: 0.0 mA, sleep: 0.0 mA
mq135 = MQ135('P17')                                        # CO2 sensor
                                                            # active: 40 mA, sleep: 0.0 mA
volt_pin = ADC().channel(pin = 'P15', attn=ADC.ATTN_11DB)   # analog voltage sensor for battery level
max4466 =  ADC().channel(pin = 'P18', attn=ADC.ATTN_11DB)   # analog loudness sensor
                                                            # active: 0.3 mA, sleep: 0.3 mA (always on)


#%% get sensor values and put sensors to sleep immediately after
polls = 3   # poll every sensor multiple times for more reliable values

tsl2591.wake()
veml6070.wake()

batt_volt = sum([volt_pin.voltage() * 2 / 1000 for _ in range(polls)]) / polls
temperature = sum([bme680.temperature for _ in range(polls)]) / polls
humidity = sum([bme680.relative_humidity for _ in range(polls)]) / polls
pressure = sum([bme680.pressure for _ in range(polls)]) / polls
voc = sum([bme680.gas for _ in range(polls)]) / polls
loudness = sum([max4466.value() for _ in range(polls)]) / polls
light = sum([tsl2591.calculate_lux() for _ in range(polls)]) / polls
uv_raw = sum([veml6070.uv_raw for _ in range(polls)]) / polls
uv_index = veml6070.get_index(uv_raw)

tsl2591.sleep()
veml6070.sleep()

batt_perc = (batt_volt - 3.25) * 100

# by now, the LoRa message is definitely sent, so we save LoRa object to NVRAM and profit from machine.sleep's reduced power consumption
lora.nvram_save()                                   # save LoRa information to RAM

current_interval = ticks_ms() - wake_time           # calculate how long SDS011 has been running yet
machine.sleep(settings.WAKE_TIME * 1000 - current_interval)# sleep for the remaining time

while not sds011.read():                            # make sure we get response from SDS011
    pass

pm_25 = sds011.pm25
pm_100 = sds011.pm10
sds011.sleep()

ppm_co2 = sum([mq135.get_corrected_ppm(temperature, humidity) for _ in range(polls)]) / polls
mq135_en.value(0)


#%% hibernate, but restart to GPS mode if push button is pressed
push_button = Pin('P23', mode=Pin.IN, pull=Pin.PULL_DOWN)
machine.pin_sleep_wakeup(['P23'], mode=machine.WAKEUP_ANY_HIGH, enable_pull=True)

# write all values to psRAM to send during next wake
memory_string = ( struct.pack('f', float(batt_volt)) + delimiter
                + struct.pack('f', float(temperature)) + delimiter
                + struct.pack('f', float(pressure)) + delimiter
                + struct.pack('f', float(humidity)) + delimiter
                + struct.pack('i', int(loudness)) + delimiter
                + struct.pack('i', int(light)) + delimiter
                + struct.pack('i', int(uv_raw)) + delimiter
                + struct.pack('i', int(voc)) + delimiter
                + struct.pack('i', int(ppm_co2)) + delimiter
                + struct.pack('f', float(pm_25)) + delimiter
                + struct.pack('f', float(pm_100)))
rtc.memory(memory_string)

machine.deepsleep(settings.SLEEP_TIME * 1000)