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
from lib.display import SSD1306_I2C
from lib.max4466 import MAX4466
from lib.cayenneLPP import CayenneLPP
from lib.sds011 import SDS011
from lib.micropyGPS import MicropyGPS
from lib.ccs811 import CCS811
from lib.VEML6070 import VEML6070
from lib.tsl2591 import TSL2591
#import lib.bme280_float as bme280
from lib.bme280 import BME280_I2C

import settings

#setup I2C bus and display
bus_connection = I2C(0, I2C.MASTER)
display = SSD1306_I2C(128, 64, bus_connection)

if settings.DEBUG_MODE == False:
    # Make a connection to LoRa.
    app_eui = ubinascii.unhexlify(settings.APP_EUI)
    app_key = ubinascii.unhexlify(settings.APP_KEY)
    lora = LoRa(mode = settings.LORA_MODE, region = settings.LORA_REGION)
    lora.join(activation = LoRa.OTAA, auth = (app_eui, app_key), timeout = 0)
    display.text("Connecting...", 1, 1, 1)
    display.show()
    while not lora.has_joined():
        print('Connecting with LoRaWAN...')
        time.sleep(1)
    print('Joined LoRaWAN')
    display.fill(0)
    display.text("Connected!", 1, 1, 1)
    display.text("Setting up LoRa", 1, 11, 1)
    display.show()

    # Create a LoRa socket.
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    # Set the LoRaWAN data rate.
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
    s.setblocking(True)
    lpp = CayenneLPP(size = 110, sock = s)
    time.sleep(1)
else:
    display.text("Debug mode...", 1, 1, 1)
    display.show()
    time.sleep(1)

display.text("Starting sensors", 1, 41, 1)
display.show()

# Pre-initialize CCS811 nWAKE and GPS power pin
VOC_pin = Pin('P2', mode=Pin.OUT)
VOC_pin.value(0)
GPS_pin = Pin('P12', mode=Pin.OUT)
GPS_pin.value(0)
time.sleep(2)

com = UART(1,  pins=("P20",  "P19"),  baudrate=9600)    # fine particle sensor
dust_sensor = SDS011(com)
dust_sensor.wake()  # long wake time

com2 = UART(2,  pins=("P3",  "P4"),  baudrate=9600)     # GPS sensor
gps = MicropyGPS()

bme280 = BME280_I2C(i2c=bus_connection, address=0x76)   # temp, pres, hum sensor
bme280.mode = 0x00  # sleep

UV_sensor =  VEML6070(i2c=bus_connection, address=56)   # UV sensor
UV_sensor.sleep()   # sleep

lux_sensor = TSL2591(i2c=bus_connection, address=0x29)  # lux sensor
lux_sensor.sleep()  # sleep

VOC_sensor =   CCS811(i2c=bus_connection, address=90)   # VOC and CO2 sensor
#VOC_pin.value(1)    # sleep

MAX4466 = MAX4466('P18')                                # analog loudness sensor

adc = ADC()
volt_pin = adc.channel(pin = 'P16', attn=3)             # analog voltage sensor

time.sleep(1)
display.fill(0)
display.poweroff()

def update_GPS(display_on = False):
    # power up GPS and wait for it to start sending messages
    GPS_pin.value(1)
    valid = False
    while not valid:
        while not com2.any():
            time.sleep(0.1)

        print("data from gps")
        my_sentence = com2.readline()
        for x in my_sentence:
            gps.update(chr(x))

        if gps.latitude > 0 and gps.longitude > 0:
            valid = True
            GPS_pin.value(0)

def read_cycle(display_on = False):
    #this is the main function that reads all the sensors and transmits the results via LoRaWAN
    if display_on == True:
        display.poweron()
        display.text("Acquiring", 1, 1, 1)
        display.text("sensor data", 1, 15, 1)
        display.show()

    dust_sensor.read()
    VOC_sensor.data_ready()

    if settings.DEBUG_MODE == False:
        #create cayenne LPP packet
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
        #print all of the sensor values via REPL (serial)
        print("GPS " + ' ' + str(gps.latitude) + ' ' + str(gps.longitude) + ' ' + str(gps.altitude))
        print("Pressure: " + str(bme280.pressure))
        print("Temperature: " + str(bme280.temperature))
        print("Humidity: %f" % bme280.relative_humidity)
        print("Dust pm25, pm10: " + str(dust_sensor.pm25) + ', ' + str(dust_sensor.pm10))
        print("Loudness: " + str(MAX4466.value()))
        print("CO2, VOC: %d %d" % (VOC_sensor.eCO2, VOC_sensor.tVOC) )
        print("UV index,risk: %d %s" % (UV_sensor.uv_raw, UV_sensor.get_index(UV_sensor.uv_raw)))
        print("Lux: %d" % lux_sensor.calculate_lux())
        print("Voltage: %f" % (volt_pin.voltage()/1000*2))
    time.sleep(2)

    if display_on == True:
        #displaying all sensor data on screen
        display.fill(0)
        display.text("GPS lat lon alt", 1,1,1)
        display.text("%f" % gps.longitude, 1, 11,1)
        display.text("%f" % gps.latitude, 1, 21,1)
        display.text("%f" % gps.altitude, 1, 31,1)
        display.show()
        time.sleep(2)
        display.fill(0)
        display.text("Pressure: " + str(bme280.pressure), 1,1,1)
        display.text("Temperature: " , 1,13,1)
        display.text(str(bme280.temperature), 1,25,1)
        display.text("Humidity: %f" % bme280.relative_humidity, 1,35, 1)
        display.text("Voltage: %f" % (volt_pin.voltage()/1000*2), 1,45, 1)
        display.show()
        time.sleep(2)
        display.fill(0)
        display.text("Dust pm25,pm10: ", 1,1,1)
        display.text(str(dust_sensor.pm25) + ', ' + str(dust_sensor.pm10), 1,13,1)
        display.text("Loudness: " + str(MAX4466.value()), 1,25,1)
        display.show()
        time.sleep(2)
        display.fill(0)
        display.text("CO2, VOC: ", 1,1,1)
        display.text("%d %d" % (VOC_sensor.eCO2, VOC_sensor.tVOC), 1,13,1)
        display.text("UV index: %d" % UV_sensor.uv_raw, 1,25,1)
        display.text("Lux: %d" % lux_sensor.calculate_lux(), 1, 35, 1)
        display.show()
        time.sleep(2)
        display.fill(0)
        display.text("Sending", 1, 1, 2)
        display.text("sensor data", 1, 15, 2)
        display.show()
        time.sleep(2)
    # Sending the cayenne LPP packet via the LoRaWAN socket
    if settings.DEBUG_MODE == False:
        lpp.send(reset_payload = True)

    time.sleep(1)

    if display_on == True:
        display.fill(0)
        display.text("Data sent", 1, 1, 1)
        display.show()
        time.sleep(2)
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

#initialize the push button which activates a reader
push_button = Pin('P23', mode=Pin.IN, pull=Pin.PULL_UP)
#set the push button to trigger a read cycle when clicked
push_button.callback(Pin.IRQ_FALLING, update_GPS, arg=False)

while True:
    sensors_wake()
    time.sleep(5)
    read_cycle(display_on = True)
    sensors_sleep()

    if settings.MEASURE_INTERVAL > 25:
        dust_sensor.sleep()
        time.sleep(settings.MEASURE_INTERVAL-25)
        dust_sensor.wake()
        time.sleep(25)
    else:
        time.sleep(settings.MEASURE_INTERVAL-5)
