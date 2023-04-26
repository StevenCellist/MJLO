import machine
import pycom
import time

import pins

sensors = { 41 : "TSL2591", 
            56 : "VEML6070", 
            60 : "SSD1306", 
            98 : "SCD41", 
            119: "BME680" }

i2c   = machine.I2C (0, pins = (pins.SDA, pins.SCL))
uart1 = machine.UART(1, pins = (pins.TX1, pins.RX1), baudrate = 9600)
uart2 = machine.UART(2, pins = (pins.TX2, pins.RX2), baudrate = 9600)

vr_en = machine.Pin(pins.VR, mode = machine.Pin.OUT)    # voltage regulator SHDN pin
vr_en.hold(False)                                       # disable hold from deepsleep
gps_en = machine.Pin(pins.GPS, mode = machine.Pin.OUT)  # 2N2907 (PNP) gate pin
gps_en.hold(False)                                      # disable hold from deepsleep

def find_error():
    addresses = i2c.scan()                          # check if I2C wires are OK
    if not addresses:
        return 1

    for key in sensors:                             # check if we can ping each I2C sensor
        if key not in addresses:
            return key

    vr_en.value(1)                                  # enable SDS011 power
    gps_en.value(0)                                 # enable GPS power
    uart1.write(b'\xaa\xb4\x06\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x06\xab')
    time.sleep(2)

    if not uart1.any():                             # check if SDS011 is present
        return 2
    
    if not uart2.any():                             # check if NEO-6M is present
        return 3

    return 999                                      # no clue

error = find_error()

vr_en.value(0)                                      # disable power & hold through deepsleep
vr_en.hold(True)
gps_en.value(1)                                     # disable power & hold through deepsleep
gps_en.hold(True)

from LoRa import LoRaWAN
lora = LoRaWAN()                                    # sort out all LoRa related settings (frame count, port, sf)
lora.fport = 4                                      # set port to error value

# if we land here from a working state, reboot to try and solve error
if not pycom.nvs_get('error'):
    pycom.nvs_set('error', 1)                       # set in NVRAM that we encountered an error
    
    lora.make_frame({'error' : error})              # make an error frame
    lora.send_frame()                               # send frame
    
    pycom.rgbled((255 << 16) + (255 << 8) + 255)    # bright white
    machine.sleep(2000)
    pycom.rgbled(0)                                 # off
    machine.deepsleep(1)                            # reboot (software only!)

# if rebooting did not solve the error, send a firmware error and blink white
lora.make_frame({'fw' : 999, 'error' : error})      # make an extended error frame
lora.send_frame()                                   # send frame

red = (128 << 16)
while True:
    pycom.rgbled(red)
    machine.sleep(500)
    pycom.rgbled(0)
    machine.sleep(4500)