import pycom
import machine
from lib.SDS011 import SDS011
import time
pycom.heartbeat(False)
pycom.heartbeat_on_boot(False)
pycom.wifi_on_boot(False)

# get wake reason
(wake_reason, gpio_list) = machine.wake_reason()
boot = (wake_reason != machine.DEEPSLEEP_RESET and wake_reason != machine.PIN_WAKE)

# as these sensors take 30 seconds to stabilize, start them as very first thing!
com = machine.UART(1, pins=("P20", "P19"), baudrate=9600)   # UART communication to SDS011
sds011 = SDS011(com, boot)                                  # fine particle sensor

# on <5V, the UART communcation to SDS011 is slow to start
# but since this is the 'slowest' sensor, we just wait for it to start
# and then do other stuff in the meantime                     
while not sds011.wake():                                    # active: 66 mA, sleep: 3.1 mA
    pass

mq135_en = machine.Pin('P12', mode=machine.Pin.OUT)         # MQ135 VIN pin
mq135_en.value(1)                                           # preheat

wake_time = time.ticks_ms()                                 # save current time

"""
# setup I2C bus and display
i2c_bus = I2C(0, I2C.MASTER)
display = SSD1306(128, 64, i2c_bus)

#%% get GPS location if push button was pressed
gps = MicropyGPS()
def update_GPS(display_on = False):
    # power up GPS and wait for it to start sending messages
    valid = False
    if display_on:
        display.poweron()
        display.fill(0)
        display.text("GPS gestart!", 1, 1)
        display.show()
        sleep(settings.DISPLAY_TIME)
        display.poweroff()
    GPS_pin = Pin('P11', mode=Pin.OUT)
    GPS_pin.value(1)
    com2 = UART(2, pins=("P3", "P4"),  baudrate=9600)   # GPS sensor
    
    while not valid:
        while com2.any():                               # wait for incoming communication
            print("GPS locatie gevonden!")
            my_sentence = com2.readline()               # read NMEA sentence
            for x in my_sentence:
                gps.update(chr(x))                      # decode it through micropyGPS TODO: find out which sentence type is used and delete others

        if gps.latitude > 0 and gps.longitude > 0:      # wait for valid data
            valid = True                                # quit function
            GPS_pin.value(0)
            if display_on:                              # dump GPS data to display
                display.poweron()
                display.fill(0)
                display.text("GPS locatie:", 1,1)
                display.text("NB: %f" % gps.latitude, 1, 11)
                display.text("OL: %f" % gps.longitude, 1, 21)
                display.text("H: %f" % gps.altitude, 1, 31)
                display.show()
                sleep(settings.DISPLAY_TIME)
                display.poweroff()

# get wake reason
(wake_reason, gpio_list) = machine.wake_reason()
if wake_reason == machine.PIN_WAKE:
    update_GPS(display_on=True)

"""