import machine
import time
import pins
from lib.micropyGPS import MicropyGPS

def run_gps(timeout = 120):    
    gps_en = machine.Pin(pins.GPS, mode = machine.Pin.OUT)      # 2N2907 (PNP) gate pin
    gps_en.hold(False)                                          # disable hold from deepsleep
    gps_en.value(0)                                             # enable GPS power
    gps = MicropyGPS()                                          # create GPS object

    uart2 = machine.UART(2, pins = (pins.TX2, pins.RX2), baudrate = 9600)     # GPS communication

    comm = False                                                # flag for incoming data

    t = time.time()
    while not gps.valid and time.time() - t < timeout:          # timeout if no fix after ..
        while uart2.any():                                      # wait for incoming communication
            comm = True                                         # got incoming data
            my_sentence = uart2.readline()                      # read NMEA sentence
            for x in my_sentence:
                gps.update(chr(x))                              # decode it through micropyGPS

    gps_en.value(1)
    gps_en.hold(True)

    if not comm:                                                # raise error if there was no GPS communication
        import pycom
        pycom.nvs_set("error", 2)
        raise ModuleNotFoundError

    if not gps.valid:
        return None
    
    return (gps.latitude, gps.longitude, gps.altitude, gps.hdop)
