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
import lib.bme280_float as bme280
import tsl2591

import settings

app_eui = ubinascii.unhexlify(settings.APP_EUI)
app_key = ubinascii.unhexlify(settings.APP_KEY)
lora = LoRa(mode = settings.LORA_MODE, region = settings.LORA_REGION)

#setup I2C bus and display
bus_connection = I2C(0, I2C.MASTER)
display = SSD1306_I2C(128, 64, bus_connection)

if settings.DEBUG_MODE == False:
# Make a connection to LoRa.
    lora.join(activation = LoRa.OTAA, auth = (app_eui, app_key), timeout = 0)
    while not lora.has_joined():
        display.fill(0)
        display.text("Connecting...", 1, 1, 1)
        print('Connecting with LoRaWAN...')
        time.sleep(1)

    print('Joined LoRaWAN')
    display.fill(0)
    display.text("Connected!", 1, 1, 1)

# Create a LoRa socket.
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
# Set the LoRaWAN data rate.
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
s.setblocking(True)

#initialize UART busses
com = UART(1,  pins=("P20",  "P19"),  baudrate=9600)    # fine particle sensor
com2 = UART(2,  pins=("P3",  "P4"),  baudrate=9600)     # GPS sensor

time.sleep(1)
#initialize sensor objects
dust_sensor = SDS011(com)
gps = MicropyGPS()
bme = bme280.BME280(i2c=bus_connection)
MAX4466 = MAX4466()
UV_sensor = VEML6070(i2c=bus_connection)
tsl = tsl2591.Tsl2591(i2c_bus = bus_connection)
VOC_sensor = CCS811(i2c=bus_connection, addr=90)
lpp = CayenneLPP(size = 110, sock = s)
time.sleep(3)

#setup voltage measuring
adc = ADC()
apin = adc.channel(attn=3, pin = 'P16')

def read_cycle(display_on = False):
    #this is the main function that reads all the sensors and transmits the results via LoRaWAN
    if display_on == True:
        display.text("Acquiring", 1, 1, 1)
        display.text("sensor data", 1, 15, 1)
        display.show()
    #updating all of the sensor values, dust sensor is done in main loop
    temperature, pressure, humidity = bme.read_compensated_data()
    UV_sensor.getMeasurement()
    UVindex = UV_sensor.UVindex
    UVrisk = UV_sensor.UVrisk
    full, ir = tsl.get_full_luminosity()  # read raw values (full spectrum and ir spectrum)
    lux = tsl.calculate_lux(full, ir)
    VOC_sensor.data_ready()
    voltage = apin.voltage()/1000*2

    #get GPS data
    if com2.any():
        print("data from gps")
        my_sentence = com2.readline()
        for x in my_sentence:
            gps.update(chr(x))

    if settings.DEBUG_MODE == False:
        #create cayenne LPP packet
        lpp.add_analog_input(voltage, channel = 0) #Voltage measurement, 2 bites with fractions
        lpp.add_temperature(temperature, channel = 1) #temp
        lpp.add_barometric_pressure(pressure/100, channel = 2)
        lpp.add_relative_humidity(humidity, channel = 3) #humidity 0-100%   #see this url: https://www.thethingsnetwork.org/forum/t/cayenne-lpp-format-analog-data-wrong/14676
        lpp.add_luminosity(MAX4466.value(), channel = 4)    #loudness 0-4096
        lpp.add_luminosity(lux, channel = 5) #lux 2 bytes unsinged
        lpp.add_luminosity(UVindex, channel = 6) #UV sensor2 byte unsigned
        lpp.add_luminosity(VOC_sensor.tVOC, channel = 7) #TVOC from 0 to 1187 ppb
        lpp.add_luminosity(VOC_sensor.eCO2, channel = 8) #eCO2 in 400-8192 ppm
        lpp.add_barometric_pressure(dust_sensor.pm25, channel = 9) #pm25 0.0-999.9 ug/m3 (2 bytes unsigned)# TODO: Find out if it is better to use unsigned fields for these
        lpp.add_barometric_pressure(dust_sensor.pm10, channel = 10)   #pm 10
        lpp.add_gps(gps.latitude, gps.longitude, gps.altitude, channel = 11)
    if settings.DEBUG_MODE == True:
        #print all of the sensor values via REPL (serial)
        print("GPS " + ' ' + str(gps.latitude) + ' ' + str(gps.longitude) + ' ' + str(gps.altitude))
        print("Pressure: " + str(pressure/100))
        print("Temperature: " + str(temperature))
        print("Humidity: %f" % humidity)
        print("Dust pm25, pm10: " + str(dust_sensor.pm25) + ', ' + str(dust_sensor.pm10))
        print("Loudness: " + str(MAX4466.value()))
        print("CO2, VOC: %d %d" % (VOC_sensor.eCO2, VOC_sensor.tVOC) )
        print("UV index,risk: %d %s" % (UVindex,UVrisk))
        print("Lux: %d" % lux)
        print("Voltage: %f" % voltage)
    time.sleep(5)

    if display_on == True:
        #displaying all sensor data on screen
        display.fill(0)
        display.text("Sending", 1, 1, 2)
        display.text("sensor data", 1, 15, 2)
        display.show()
        time.sleep(3)
        display.fill(0)
        display.text("GPS lat lon alt", 0,0,1)
        display.text("%f" % gps.longitude, 1, 11,1)
        display.text("%f" % gps.latitude, 1, 21,1)
        display.text("%f" % gps.altitude, 1, 31,1)
        display.show()
        time.sleep(3)
        display.fill(0)
        display.text("Pressure: " + str(pressure/100), 1,1,1)
        display.text("Temperature: " , 1,13,1)
        display.text(str(temperature), 1,25,1)
        display.text("Humidity: %f" % humidity, 1,35, 1)
        display.text("Voltage: %f" % voltage, 1,45, 1)
        display.show()
        time.sleep(3)
        display.fill(0)
        display.text("Dust pm25,pm10: ", 1,1,1)
        display.text(str(dust_sensor.pm25) + ', ' + str(dust_sensor.pm10), 1,13,1)
        display.text("Loudness: " + str(MAX4466.value()), 1,25,1)
        display.show()
        time.sleep(3)
        display.fill(0)
        display.text("CO2, VOC: ", 1,1,1)
        display.text("%d %d" % (VOC_sensor.eCO2, VOC_sensor.tVOC), 1,13,1)
        display.text("UV index: %d" % UVindex, 1,25,1)
        display.text("Lux: %d" % lux, 1, 35, 1)
        display.show()
        time.sleep(3)
    # Sending the cayenne LPP packet via the LoRaWAN socket
    if settings.DEBUG_MODE == False:
        lpp.send(reset_payload = True)

    time.sleep(1)

    if display_on == True:
        display.fill(0)
        display.text("Data sent", 1, 1, 1)
        display.show()
        time.sleep(1)
        display.fill(0)
        display.text("Going to sleep", 1, 1, 1)
        display.text("for 5 minutes", 1, 15, 1)
        display.show()
        time.sleep(1)
        display.poweroff() #reduce power consumption

#initialize the push button which activates a reader
push_button = Pin('P23', mode=Pin.IN, pull=Pin.PULL_UP)
#set the push button to trigger a read cycle when clicked
push_button.callback(Pin.IRQ_FALLING, read_cycle, arg = True)

dust_sensor.read()

while True:
    dust_sensor.sleep()
    read_cycle(display_on = True)
    #main loop sleep time
    time.sleep(settings.MEASURE_INTERVAL-30)

    dust_sensor.wake()
    time.sleep(30)
    x = 0
    while dust_sensor.read() == False and x <10:
        dust_sensor.read()
        x += 1
