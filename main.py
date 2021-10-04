#MicroPython imports.
import socket
import time
import ubinascii
import array

#Pycom imports.
from machine import I2C
from machine import UART
from network import LoRa
from machine import Pin
from machine import ADC

#Own imports.
from lib.display import SSD1306
from lib.max4466 import MAX4466
from lib.cayenneLPP import CayenneLPP
from lib.sds011 import SDS011
from lib.micropyGPS import MicropyGPS
from lib.ccs811 import CCS811
from lib.VEML6070 import VEML6070
from lib.tsl2591 import TSL2591
from lib.bme280 import BME280

import settings

#setup I2C bus and display
i2c_bus = I2C(0, I2C.MASTER)
display = SSD1306(128, 64, i2c_bus)

if settings.DEBUG_MODE == False:
    # Make a connection to LoRa.
    app_eui = ubinascii.unhexlify(settings.APP_EUI)
    app_key = ubinascii.unhexlify(settings.APP_KEY)
    lora = LoRa(mode = settings.LORA_MODE, region = settings.LORA_REGION)
    lora.join(activation = settings.LORA_ACTIVATION, auth = (app_eui, app_key), timeout = 0)
    display.text("Verbinden...", 1, 1)
    display.show()

    while not lora.has_joined():
        print('Verbinden met LoRaWAN...')
        time.sleep(1)

    print('Verbonden!')
    display.fill(0)
    display.text("Verbonden!", 1, 1)
    display.show()

    # Create a LoRa socket.
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    # Set the LoRaWAN data rate.
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
    s.setblocking(True)
    lpp = CayenneLPP(size = 110, sock = s)
else:
    display.text("Debug modus...", 1, 1)

display.text("Sensoren starten", 1, 11)
display.show()

# Pre-initialize CCS811 nWAKE and GPS power pin
VOC_pin = Pin('P2', mode=Pin.OUT)
VOC_pin.value(0)
GPS_pin = Pin('P12', mode=Pin.OUT)
GPS_pin.value(0)
time.sleep(settings.WAKE_TIME)   # CCS811 wake time

com = UART(1, pins=("P20", "P19"), baudrate=9600)    # fine particle sensor
dust_sensor = SDS011(com)
if settings.SLEEP_TIME > settings.SDS011_WAKE_TIME:
    dust_sensor.sleep()  # otherwise it will never wake

com2 = UART(2, pins=("P3", "P4"),  baudrate=9600)     # GPS sensor
gps = MicropyGPS()

bme280 =      BME280(i2c=i2c_bus, address=0x76)  # temp, pres, hum sensor
bme280.mode = 0x00  # sleep

UV_sensor = VEML6070(i2c=i2c_bus, address=56)    # UV sensor
UV_sensor.sleep()   # sleep

lux_sensor = TSL2591(i2c=i2c_bus, address=0x29)  # lux sensor
lux_sensor.sleep()  # sleep

VOC_sensor =  CCS811(i2c=i2c_bus, address=90)    # VOC and CO2 sensor
#VOC_pin.value(1)    # sending to sleep here seems to result in instability

MAX4466 = MAX4466('P18')                         # analog loudness sensor

adc = ADC()
volt_pin = adc.channel(pin = 'P16', attn=3)      # analog voltage sensor

time.sleep(1)
display.fill(0)
display.poweroff()

def update_GPS(display_on = False):
    # power up GPS and wait for it to start sending messages
    GPS_pin.value(1)
    valid = False
    if display_on:
        display.poweron()
        display.fill(0)
        display.text("GPS gestart!", 1, 1)
        display.show()
        time.sleep(settings.DISPLAY_TIME)
        display.poweroff()

    while not valid:
        while com2.any():                   # wait for incoming communication
            print("GPS locatie gevonden!")
            my_sentence = com2.readline()   # read NMEA sentence
            for x in my_sentence:
                gps.update(chr(x))          # decode it through micropyGPS

        if gps.latitude > 0 and gps.longitude > 0:  # wait for valid data
            GPS_pin.value(0)    # poweroff GPS to reduce power consumption
            valid = True        # quit function
            if display_on:      # dump GPS data to display
                display.poweron()
                display.fill(0)
                display.text("GPS locatie:", 1,1)
                display.text("NB: %f" % gps.latitude, 1, 11)
                display.text("OL: %f" % gps.longitude, 1, 21)
                display.text("H: %f" % gps.altitude, 1, 31)
                display.show()
                time.sleep(settings.DISPLAY_TIME)
                display.poweroff()

def read_cycle(display_on = False):
    #this is the main function that reads all the sensors and transmits the results via LoRaWAN
    if display_on:
        display.poweron()
        display.text("Sensor-error :(", 1, 1)
        display.text("Herstarten svp!", 1, 11)
        display.show()

    dust_sensor.read()
    VOC_sensor.data_ready()

    # calculate an approximate battery percentage
    battery_voltage = volt_pin.voltage()/1000*2
    battery_percentage = (battery_voltage - 3.3) / 1.5 * 100 # assuming a range of 3.3 to 4.8 Volts on the battery

    if settings.DEBUG_MODE == False:
        # create cayenne LPP packet
        lpp.add_analog_input(volt_pin.voltage()/1000*2, channel = 0) #Voltage measurement, 2 bites with fractions
        lpp.add_temperature(bme280.temperature, channel = 1) #temp
        lpp.add_barometric_pressure(bme280.pressure, channel = 2)
        lpp.add_relative_humidity(bme280.relative_humidity, channel = 3) #humidity 0-100%   #see this url: https://www.thethingsnetwork.org/forum/t/cayenne-lpp-format-analog-data-wrong/14676
        lpp.add_luminosity(MAX4466.value(), channel = 4)    #loudness 0-4096
        lpp.add_luminosity(lux_sensor.calculate_lux(), channel = 5) #lux 2 bytes unsinged
        lpp.add_luminosity(UV_sensor.uv_raw, channel = 6) #UV sensor2 byte unsigned
        lpp.add_luminosity(VOC_sensor.tVOC, channel = 7) #TVOC from 0 to 1187 ppb
        lpp.add_luminosity(VOC_sensor.eCO2, channel = 8) #eCO2 in 400-8192 ppm
        lpp.add_barometric_pressure(dust_sensor.pm25, channel = 9) #pm25 0.0-999.9 ug/m3 (2 bytes unsigned)# TODO: Find out if it is better to use unsigned fields for these
        lpp.add_barometric_pressure(dust_sensor.pm10, channel = 10)   #pm 10
        lpp.add_gps(gps.latitude, gps.longitude, gps.altitude, channel = 11)
    if settings.DEBUG_MODE == True:
        # print all of the sensor values via REPL (serial)
        print("GPS: NB %f, OL %f, H %f" % (gps.latitude, gps.longitude, gps.altitude))
        print("Luchtdruk: %.2f"         % bme280.pressure)
        print("Temperatuur: %.2f "      % bme280.temperature)
        print("Luchtvochtigheid: %d"    % bme280.relative_humidity)
        print("Fijnstof 2.5, 10: %.2f, %.2f" % (dust_sensor.pm25, dust_sensor.pm10))
        print("Volume: %d"              % MAX4466.value())
        print("CO2, VOC: %d %d"         % (VOC_sensor.eCO2, VOC_sensor.tVOC))
        print("UV index, risk: %d, %s"  % (UV_sensor.uv_raw, UV_sensor.get_index(UV_sensor.uv_raw)))
        print("Lux: %d"                 % lux_sensor.calculate_lux())
        print("Voltage: %.3f, %d %%"    % (volt_pin.voltage()/1000*2, battery_percentage))

    if display_on:
        # display all sensor data on display
        display.fill(0)
        display.text("Temp: %.2f"    % bme280.temperature,         1,  1)
        display.text("Druk: %.2f "   % bme280.pressure,            1, 11)
        display.text("Vocht: %d %%"  % bme280.relative_humidity,   1, 21)
        display.text("Lux: %d"       % lux_sensor.calculate_lux(), 1, 31)
        display.text("UV index: %s"  % UV_sensor.get_index(UV_sensor.uv_raw), 1,41)
        display.text("Accu: ~ %d %%" % battery_percentage,         1, 54)
        display.show()
        time.sleep(settings.DISPLAY_TIME)
        display.fill(0)
        display.text("Stof 2.5: %.2f"  % dust_sensor.pm25,   1,  1)
        display.text("Stof 10: %.2f"   % dust_sensor.pm10,   1, 11)
        display.text("VOC-gehalte: %d" % VOC_sensor.tVOC,    1, 21)
        display.text("CO2-gehalte: %d" % VOC_sensor.eCO2,    1, 31)
        display.text("Volume: %d"      % MAX4466.value(),    1, 41)
        display.text("Accu: ~ %d %%"   % battery_percentage, 1, 54)
        display.show()
        time.sleep(settings.DISPLAY_TIME)

    if settings.DEBUG_MODE == False:
        # send the cayenne LPP packet via the LoRaWAN socket
        lpp.send(reset_payload = True)

    if display_on:
        display.fill(0)
        display.text("Data verzonden", 1, 1)
        display.text("Accu: ~ %d %%" % battery_percentage, 1, 54)
        display.show()
        time.sleep(settings.DISPLAY_TIME)
        display.fill(0)
        display.poweroff()

def sensors_wake():
    VOC_pin.value(0)
    UV_sensor.wake()
    lux_sensor.wake()
    bme280.mode = 0x03

def sensors_sleep():
    VOC_pin.value(1)
    UV_sensor.sleep()
    lux_sensor.sleep()
    bme280.mode = 0x00

# initialize the push button which activates a reader
push_button = Pin('P23', mode=Pin.IN, pull=Pin.PULL_UP)
# set the push button to trigger GPS positioning when clicked
push_button.callback(Pin.IRQ_FALLING, update_GPS, arg=False)

while True:
    sensors_wake()
    time.sleep(settings.WAKE_TIME)
    read_cycle(display_on = True)
    sensors_sleep()

    # based on measuring interval, send particulate matter sensor to bed
    if settings.SLEEP_TIME > settings.SDS011_WAKE_TIME:
        dust_sensor.sleep()
        time.sleep(settings.SLEEP_TIME - settings.SDS011_WAKE_TIME)
        dust_sensor.wake()
        time.sleep(settings.SDS011_WAKE_TIME)
    else:
        time.sleep(settings.SLEEP_TIME)
