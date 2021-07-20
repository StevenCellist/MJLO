import socket
import time
import ubinascii
import array


#Pycom imports.
from machine import I2C
from machine import UART
from network import LoRa
from machine import Pin
#Own imports.
from lib.cayenneLPP import CayenneLPP

import settings


app_eui = ubinascii.unhexlify(settings.APP_EUI)
app_key = ubinascii.unhexlify(settings.APP_KEY)

lora = LoRa(mode = settings.LORA_MODE, region = settings.LORA_REGION)

# Make a connection to LoRa.

lora.join(activation = LoRa.OTAA, auth = (app_eui, app_key), timeout = 0)

while not lora.has_joined():
    time.sleep(1)
    print('Connecting with LoRaWAN...')

print('Joined LoRaWAN')

    # Create a LoRa socket.
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
# Set the LoRaWAN data rate.
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
s.setblocking(True)



#setup I2C bus

time.sleep(1)

lpp = CayenneLPP(size = 100, sock = s)
time.sleep(5)

def read_cycle(display_on = False):

    lpp.add_gps(0.0000, 0.0000, 0.0000, channel = 9)
    lpp.add_barometric_pressure(50000, channel = 2)
    lpp.add_temperature(20.4, channel = 3) #temp
    lpp.add_barometric_pressure(2.1, channel = 4) #pm25 0.0-999.9 ug/m3 (2 bytes unsigned)# TODO: Find out if it is better to use unsigned fields for these
    lpp.add_barometric_pressure(5.5, channel=5)   #pm 10
    lpp.add_luminosity(4000, channel=6)    #loudness 0-4096
    lpp.add_luminosity(40000, channel = 7) #eCO2 in 400-8192 ppm
    lpp.add_luminosity(30000, channel = 8) #TVOC from 0 to 1187 ppb
    lpp.add_luminosity(200, channel = 1) #UV sensor2 byte unsigned
    lpp.add_luminosity(35000, channel = 10) #Lux sensor 2 byte unsigned            #see this url: https://www.thethingsnetwork.org/forum/t/cayenne-lpp-format-analog-data-wrong/14676

    time.sleep(1)


    lpp.send(reset_payload = True)




while True:
    read_cycle(display_on = False)
    #main loop sleep time
    time.sleep(5)
