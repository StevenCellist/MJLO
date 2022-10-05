import machine
import time
import pins
from lib.micropyGPS import MicropyGPS

def run_gps(timeout = 120):    
    values = {}

    gps_en = machine.Pin(pins.GPS, mode = machine.Pin.OUT)      # 2N2907 (PNP) gate pin
    gps_en.hold(False)                                          # disable hold from deepsleep
    gps_en.value(0)                                             # enable GPS power
    gps = MicropyGPS()                                          # create GPS object

    com = machine.UART(2, pins = (pins.TX2, pins.RX2), baudrate = 9600)         # GPS communication

    t1 = time.time()
    while gps.latitude == gps.longitude == 0 and time.time() - t1 < timeout:    # timeout if no fix after ..
        while com.any():                                        # wait for incoming communication
            my_sentence = com.readline()                        # read NMEA sentence
            for x in my_sentence:
                gps.update(chr(x))                              # decode it through micropyGPS

    gps_en.value(1)
    gps_en.hold(True)

    values["lat"]  = gps.latitude
    values["long"] = gps.longitude
    values["alt"]  = gps.alt
    return values
