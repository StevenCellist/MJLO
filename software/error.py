import machine
import pycom
from lib.SSD1306 import SSD1306

def reboot_or_blink(R, G, B):
    color = (R << 16) + (G << 8) + B

    # if we land here from a working state, reboot to try and solve error
    if not pycom.nvs_get("error"):
        pycom.nvs_set("error", 1)   # set in NVRAM that we encountered an error
        pycom.rgbled(color)
        machine.sleep(2000)
        pycom.rgbled(0)
        machine.reset()
        
    # if rebooting did not solve the error, send '999' as firmware version through LoRa to indicate error
    import network
    import socket
    import secret
    from LoRa_frame import make_frame
    LORA_DR = 12 - pycom.nvs_get('sf_h')
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)                              # create a LoRa socket (blocking)
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_DR)                            # set the LoRaWAN data rate to high
    s.bind(4)                                                   # set the type of message used for decoding the packet
    mode = network.LoRa.OTAA if pycom.nvs_get('lora') == 0 else network.LoRa.ABP    # get LoRa mode (OTAA / ABP)
    lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)   # create LoRa object
    lora.join(activation = mode, auth = secret.auth(), dr = LORA_DR)                # perform join
    frame = make_frame({'fw' : 999})                                                # make a frame with just 999 as fw version
    while not lora.has_joined():
        machine.sleep(500)                                                          # wait for LoRa join
    s.send(frame)                                                                   # send frame

    # just loop now forever while blinking onboard LED
    while True:
        pycom.rgbled(color)
        machine.sleep(500)
        pycom.rgbled(0)
        machine.sleep(1500)

i2c = machine.I2C(0)

# try to initialize the display - if this throws an error, blink blue
try:
    display = SSD1306(128, 64, i2c)
    display.text("Error!", 1, 1)
    display.show()
except:
    reboot_or_blink(0, 0, 255)

# try to initialize the sensors - if one or more throw an error, write their names to display
addresses = i2c.scan()
sensors = { 41 : "TSL2591", 56 : "VEML6070", 119 : "BME680" }
i = 11
for key in sensors:
    if key not in addresses:
        display.text(sensors[key], 1, i)
        display.show()
        i += 10

# if one or more sensors failed to initialize, blink yellow - else, blink red
if i != 11:
    reboot_or_blink(180, 180, 0)
else:
    display.text("I2C ok", 1, 11)
    display.show()
    reboot_or_blink(255, 0, 0)