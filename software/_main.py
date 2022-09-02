#_main.py -- frozen into the firmware along all other modules except settings.py
import time
start_time = time.ticks_ms() + 2000             # save current boot time (+2s compensation offset)

import pycom
import machine
import settings
from lib.SSD1306 import SSD1306

wake_reason = machine.wake_reason()[0]          # tuple of (wake_reason, GPIO_list)

# on first boot, disable integrated LED and WiFi
if wake_reason == machine.PWRON_WAKE:
    pycom.heartbeat_on_boot(False)
    pycom.wifi_on_boot(False)

i2c_bus = machine.I2C(0)                        # create I2C object
display = SSD1306(128, 64, i2c_bus)             # initialize display (4.4 / 0.0 mA)

# if button was pressed, check for firmware update
if wake_reason == machine.PIN_WAKE:
    from lib.updateFW import check_update
    update = check_update(display)
    machine.sleep(1000)				# show update result for 1s on display
    if update:
        machine.reset()                         # in case of an update, reboot the device

display.fill(0)
display.text("MJLO-" + settings.NODE, 1, 1)
display.text("FW: v2.6", 1, 11)
display.show()

""" This part is only executed if DEBUG == True """
if settings.DEBUG == True:
    
    if wake_reason == machine.PIN_WAKE:         # if button is pressed in DEBUG mode, enable GPS
        from collect_gps import run_gps
        loc = run_gps(timeout = 120)
        print("NB", loc['lat'], "OL", loc['long'], "H", loc['alt'])

    from collect_sensors import run_collection
    values = run_collection(i2c_bus = i2c_bus, all_sensors = True, t_wake = settings.T_WAKE)

    print("Temp: " + str(values['temp']) + " C")
    print("Druk: " + str(values['pres']) + " hPa")
    print("Vocht: " + str(values['humi']) + " %")
    print("Licht: " + str(values['lx']) + " lx")
    print("UV: " + str(values['uv']))
    print("Accu: " + str(values['perc']) + " %")
    print("Volume: " + str(values['volu']) + " dB")
    print("VOC: " + str(values['voc']) + " Ohm")
    print("CO2: " + str(values['co2']) + " ppm")
    print("PM2.5: " + str(values['pm25']) + " ppm")
    print("PM10: " + str(values['pm10']) + " ppm")

    push_button = machine.Pin('P2', mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
    machine.pin_sleep_wakeup(['P2'], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
    machine.deepsleep((settings.T_DEBUG - 30) * 1000)   # deepsleep for remainder of the interval time

""" This part is only executed if DEBUG == False """
import network
import socket

lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)   # create LoRa object
LORA_FCNT = 0                                                                   # default LoRa frame count
if wake_reason == machine.RTC_WAKE or wake_reason == machine.PIN_WAKE:          # if woken up from deepsleep (timer or button)..
    lora.nvram_restore()                                                        # ..restore LoRa information from nvRAM
    LORA_FCNT = pycom.nvs_get('fcnt')                                           # ..restore LoRa frame count from nvRAM

frame = bytes([0])                                      # LoRa packet decoding type 0 (minimal)

all_sensors = False
# every FRACTION'th message or if the button was pushed, use all sensors (but not if GPS is used)
if LORA_FCNT % settings.FRACTION == 0 or wake_reason == machine.PIN_WAKE:
    all_sensors = True
    frame = bytes([1])                                  # LoRa packet decoding type 1 (all sensors)

use_gps = False
# once a day, enable GPS (but not if the button was pressed)
if LORA_FCNT % int(86400 / settings.T_INTERVAL) == 0 and wake_reason != machine.PIN_WAKE:
    use_gps = True
    all_sensors = False
    frame = bytes([2])                                  # LoRa packet decoding type 2 (use GPS)

LORA_SF = settings.SF_LOW
# if GPS or all sensors are used, send on high SF (don't let precious power go to waste)
if use_gps == True or all_sensors == True:
    LORA_SF = settings.SF_HIGH

lora.sf(LORA_SF)                                        # set SF for this uplink
LORA_DR = 12 - LORA_SF                                  # calculate DR for this SF

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)      # create a LoRa socket (blocking)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_DR)    # set the LoRaWAN data rate

# join the network upon first-time wake
if LORA_FCNT == 0:
    import secret

    if settings.LORA_MODE == 'OTAA':
        mode = network.LoRa.OTAA
    else: #settings.LORA_MODE == 'ABP'
        mode = network.LoRa.ABP

    lora.join(activation = mode, auth = secret.auth(settings.LORA_MODE, settings.NODE), dr = LORA_DR)
    # don't need to wait for has_joined(): GPS takes much longer to start

# run sensor routine
from collect_sensors import run_collection
values = run_collection(i2c_bus = i2c_bus, all_sensors = all_sensors, t_wake = settings.T_WAKE)

def pack(value, precision, size = 2):
    value = int(value / precision)                      # round to precision
    value = max(0, min(value, 2**(8*size)))             # stay in range 0 .. int.max_size
    return value.to_bytes(size, 'big')                  # pack to bytes

# add the sensor values that are always measured (frame is now 1 + 14 = 15 bytes)
frame += pack(values['volt'], 0.001) + pack(values['temp'] + 25, 0.01) + pack(values['pres'], 0.1) \
        + pack(values['humi'], 0.5, size = 1) + pack(values['volu'], 0.5, size = 1) \
        + pack(values['lx'], 1) + pack(values['uv'], 1) + pack(values['voc'], 1)

if all_sensors == True:
    # add extra sensor values (frame is now 1 + 14 + 6 = 21 bytes)
    frame += pack(values['co2'], 1) + pack(values['pm25'], 0.1) + pack(values['pm10'], 0.1)

if use_gps == True:
    # run gps routine
    from collect_gps import run_gps
    loc = run_gps()

    # add gps values (frame is now 1 + 14 + 9 = 24 bytes)
    frame += pack(loc['lat'] + 90, 0.0000001, size = 4) + pack(loc['long'] + 180, 0.0000001, size = 4) \
            + pack(loc['alt'], 0.1, size = 1)

# send LoRa message and store LoRa context + frame count in non-volatile RAM (should be using wear leveling)
s.send(frame)
lora.nvram_save()
pycom.nvs_set('fcnt', LORA_FCNT + 1)

# write all values to display in two series
display.fill(0)
display.text("Temp: " + str(round(values['temp'], 1)) + " C",   1,  1),
display.text("Druk: " + str(round(values['pres'], 1)) + " hPa", 1, 11),
display.text("Vocht: " + str(round(values['humi'], 1)) + " %",  1, 21),
display.text("Licht: " + str(int(values['lx'])) + " lx",        1, 31),
display.text("UV: " + str(int(values['uv'])),                   1, 41),
display.text("Accu: " + str(int(values['perc'])) + " %",        1, 54),
display.show()
machine.sleep(settings.T_DISPLAY * 1000)
display.fill(0)
display.text("Volume: " + str(int(values['volu'])) + " dB",     1,  1),
display.text("VOC: " + str(int(values['voc'])) + " Ohm",        1, 11),
if all_sensors == True:
    display.text("CO2: " + str(int(values['co2'])) + " ppm",    1, 21),
    display.text("PM2.5: " + str(values['pm25']) + " ppm",      1, 31),
    display.text("PM10: " + str(values['pm10']) + " ppm",       1, 41),
display.text("Accu: " + str(int(values['perc'])) + " %",        1, 54),
display.show()
machine.sleep(settings.T_DISPLAY * 1000)
display.poweroff()

# set up for deepsleep
awake_time = time.ticks_diff(time.ticks_ms(), start_time)       # time in milliseconds the program has been running
push_button = machine.Pin('P2', mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
machine.pin_sleep_wakeup(['P2'], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
machine.deepsleep(settings.T_INTERVAL * 1000 - awake_time)      # deepsleep for remainder of the interval time
