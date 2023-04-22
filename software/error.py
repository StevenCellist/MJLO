import machine
import pycom

# if we land here from a working state, reboot to try and solve error
if not pycom.nvs_get("error"):
    pycom.nvs_set("error", 1)                       # set in NVRAM that we encountered an error
    pycom.rgbled((255 << 16) + (255 << 8) + 255)    # bright white
    machine.sleep(2000)
    pycom.rgbled(0)                                 # off
    machine.deepsleep(1)                            # reboot (software only!)

import network
import socket


# if rebooting did not solve the error, send '999' as firmware version through LoRa to indicate error

lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)   # create LoRa object
lora.nvram_restore()
LORA_DR = 12 - pycom.nvs_get('sf_h')
if not lora.has_joined():
    import secret
    mode = network.LoRa.OTAA if pycom.nvs_get('lora') == 0 else network.LoRa.ABP# get LoRa mode (OTAA / ABP)
    lora.join(activation = mode, auth = secret.auth(), dr = LORA_DR)            # perform join
    while not lora.has_joined():
        machine.sleep(500)                                                      # wait for LoRa join

from LoRa_frame import make_frame
frame = make_frame({"fw" : 999})                                                # make a frame with just 999 as fw version

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)                              # create a LoRa socket (blocking)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_DR)                            # set the LoRaWAN data rate to high
s.bind(4)                                                                       # set fport used for decoding the packet
s.send(frame)                                                                   # send frame

# function to loop indefinitely with a blinking onboard LED
def reboot_or_blink(R, G, B):
    color = (R << 16) + (G << 8) + B

    while True:
        pycom.rgbled(color)
        machine.sleep(500)
        pycom.rgbled(0)
        machine.sleep(4500)

# run some simple diagnostics

import pins
from lib.SSD1306 import SSD1306

i2c = machine.I2C(0, pins = (pins.SDA, pins.SCL))

# try to initialize the display - if this throws an error, blink blue
try:
    display = SSD1306(128, 64, i2c)
    display.text("Error!", 1, 1)
    display.show()
except:
    reboot_or_blink(0, 0, 255)

# if GPS did not initialize, error was set to '2' - blink green
if pycom.nvs_get("error") == 2:
    display.text("GPS", 1, 11)
    display.show()
    reboot_or_blink(0, 255, 0)

# try to initialize the sensors - if one or more throw an error, write their names to display, blink yellow
addresses = i2c.scan()
sensors = { 41 : "TSL2591", 
            56 : "VEML6070", 
            98 : "SCD41", 
            119: "BME680" }
i = 11
for key in sensors:
    if key not in addresses:
        display.text(sensors[key], 1, i)
        display.show()
        i += 10
if i != 11:
    reboot_or_blink(180, 180, 0)

# if we couldn't find anything, blink red
display.text("I2C ok", 1, 11)
display.show()
reboot_or_blink(255, 0, 0)