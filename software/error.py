import machine
import pycom
from lib.SSD1306 import SSD1306

def blink(R, G, B):
    color = (R << 16) + (G << 8) + B
    while True:
        pycom.rgbled(color)
        machine.sleep(500)
        pycom.rgbled(0)
        machine.sleep(1500)

i2c = machine.I2C(0)

try:
    display = SSD1306(128, 64, i2c)
    display.text("Error!", 1, 1)
    display.show()
except:
    blink(0, 0, 255)

addresses = i2c.scan()

sensors = { 41 : "TSL2591", 56 : "VEML6070", 119 : "BME680" }

i = 11
for key in sensors:
    if key not in addresses:
        display.text(sensors[key], 1, i)
        display.show()
        i += 10

if i == 11:
    display.text("I2C ok", 1, 11)
    display.show()
    blink(255, 0, 0)
else:
    blink(180, 180, 0)