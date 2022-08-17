#_main.py -- frozen into the firmware along all other modules except settings.py
import pycom

pycom.heartbeat(False)
pycom.heartbeat_on_boot(False)
pycom.wifi_on_boot(False)

import time
wake_time = time.ticks_ms()

import machine
wake_reason = machine.wake_reason()[0]                  # tuple of (wake_reason, GPIO_list)

import settings
from lib.SSD1306 import SSD1306

i2c_bus = machine.I2C(0)                                # create I2C object
display = SSD1306(128, 64, i2c_bus)                     # initialize display (4.4 / 0.0 mA)
display.text("MJLO-" + settings.NODE, 1, 1)
display.text("Hello world!", 1, 11)
display.show()

""" This part is only executed if DEBUG == True """
if settings.DEBUG == True:

    PRINT = {
        'volt' : lambda volt : print("Accu:", volt),
        'temp' : lambda temp : print("Temp:", temp),
        'pres' : lambda pres : print("Druk:", pres),
        'humi' : lambda humi : print("Vocht:", humi),
        'volu' : lambda volu : print("Volume:", volu),
        'lx'   : lambda lx   : print("Licht:", lx),
        'uv'   : lambda uv   : print("UV:", uv),
        'voc'  : lambda voc  : print("VOC:", voc),
        'co2'  : lambda co2  : print("CO2:", co2),
        'pm25' : lambda pm25 : print("PM2.5:", pm25),
        'pm10' : lambda pm10 : print("PM10:", pm10),
        'gps'  : lambda lat, long, alt : print("NB", lat, "OL", long, "H", alt),
        'perc' : lambda perc : print("Accu%:", perc)
    }
    
    if wake_reason == machine.PIN_WAKE:     # if button is pressed in DEBUG mode, enable GPS
        from collect_gps import run_gps
        loc = run_gps(timeout = 120)
        PRINT['GPS'](loc['lat'], loc['long'], loc['alt'])

    from collect_sensors import run_collection
    values = run_collection(i2c_bus = i2c_bus, all_sensors = True, t_wake = settings.T_WAKE)

    for key in values:
        PRINT[key](values[key])

    awake_time = time.ticks_ms() - wake_time                            # time in seconds the program has been running
    push_button = machine.Pin('P23', mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
    machine.pin_sleep_wakeup(['P23'], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
    machine.deepsleep(settings.T_DEBUG * 1000 - awake_time)             # deepsleep for remainder of the interval time

""" This part is only executed if DEBUG == False """
import network
import socket

from lib.cayenneLPP import CayenneLPP

lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)   # create LoRa object
LORA_CNT = 0                                                                    # default LoRa frame counter
if wake_reason == machine.RTC_WAKE or wake_reason == machine.PIN_WAKE:          # if woken up from deepsleep (timer or button)..
    lora.nvram_restore()                                                        # ..restore the LoRa information from nvRAM
    try:
        with open('/flash/counter.txt', 'r') as file:
            LORA_CNT = int(file.readline())                                     # try to restore LoRa frame counter from deepsleep
    except:
        print("Failed to read counter file, reset counter to 0")

use_gps = False
# once a day, enable GPS (when rest(no. of messages * interval) / day < interval) (but not if the button was pressed)
if (LORA_CNT * settings.T_INTERVAL) % 86400 < settings.T_INTERVAL and wake_reason != machine.PIN_WAKE:
    use_gps = True

all_sensors = False
# every FRACTION'th message or if the button was pushed, use all sensors (but not if GPS is used)
if (LORA_CNT % settings.FRACTION == 0 or wake_reason == machine.PIN_WAKE) and use_gps == False:
    all_sensors = True

LORA_SF = settings.SF_LOW
# if GPS or all sensors are used, send on high SF (don't let precious power go to waste)
if use_gps == True or all_sensors == True:
    LORA_SF = settings.SF_HIGH

lora.sf(LORA_SF)                                                # set SF for this uplink
LORA_DR = 12 - LORA_SF                                          # calculate DR for this SF

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)              # create a LoRa socket (blocking)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_DR)            # set the LoRaWAN data rate

# join the network upon first-time wake
if LORA_CNT == 0:
    import secret

    if settings.LORA_MODE == 'OTAA':
        mode = network.LoRa.OTAA
    else: #settings.LORA_MODE == 'ABP'
        mode = network.LoRa.ABP

    lora.join(activation = mode, auth = secret.auth(settings.LORA_MODE, settings.NODE), dr = LORA_DR)
    # don't need to wait for has_joined(): when joining the network, GPS is enabled next which takes much longer

# create Cayenne-formatted LoRa message (payload either 41 or 42 bytes so stick to 42 either way)
lpp = CayenneLPP(size = 42, sock = s)

LPP_ADD = {         # routine for adding data to Cayenne message
    'volt' : lambda volt : lpp.add_analog_input(volt, channel = 0),             # 4 (2) bits
    'temp' : lambda temp : lpp.add_temperature(temp, channel = 1),              # 4 (2) bits
    'pres' : lambda pres : lpp.add_barometric_pressure(pres, channel = 2),      # 4 (2) bits
    'humi' : lambda humi : lpp.add_relative_humidity(humi, channel = 3),        # 3 (1) bits
    'volu' : lambda volu : lpp.add_relative_humidity(volu, channel = 4),        # 3 (1) bits
    'lx'   : lambda lx   : lpp.add_luminosity(lx, channel = 5),                 # 4 (2) bits
    'uv'   : lambda uv   : lpp.add_luminosity(uv, channel = 6),                 # 4 (2) bits
    'voc'  : lambda voc  : lpp.add_luminosity(voc, channel = 7),                # 4 (2) bits
    'co2'  : lambda co2  : lpp.add_luminosity(co2, channel = 8),                # 4 (2) bits
    'pm25' : lambda pm25 : lpp.add_barometric_pressure(pm25, channel = 9),      # 4 (2) bits
    'pm10' : lambda pm10 : lpp.add_barometric_pressure(pm10, channel = 10),     # 4 (2) bits
    'gps'  : lambda lat, long, alt : lpp.add_gps(lat, long, alt, channel = 11), # 11 (3/3/3) bits
    'perc' : lambda perc : lora.set_battery_level(perc),                        # set level for MAC command
}

DISPLAY_TEXT = {    # routine for displaying text on OLED display
    'volt' : lambda volt : None,
    'temp' : lambda temp : display.text("Temp: " + str(round(temp, 1)) + " C",   1,  1),
    'pres' : lambda pres : display.text("Druk: " + str(round(pres, 1)) + " hPa", 1, 11),
    'humi' : lambda humi : display.text("Vocht: " + str(round(humi, 1)) + " %",  1, 21),
    'lx'   : lambda lx   : display.text("Licht: " + str(int(lx)) + " lx",        1, 31),
    'uv'   : lambda uv   : display.text("UV: " + str(int(uv)),                   1, 41),

    'volu' : lambda volu : display.text("Volume: " + str(int(volu)) + " dB",     1,  1),
    'voc'  : lambda voc  : display.text("VOC: " + str(int(voc)) + " Ohm",        1, 11),
    'co2'  : lambda co2  : display.text("CO2: " + str(int(co2)) + " ppm",        1, 21),
    'pm25' : lambda pm25 : display.text("PM2.5: " + str(pm25) + " ppm",          1, 31),
    'pm10' : lambda pm10 : display.text("PM10: " + str(pm10) + " ppm",           1, 41),
    
    'perc' : lambda perc : display.text("Accu: " + str(int(perc)) + " %",        1, 54),
}

display.poweroff()

# run gps routine if enabled and add values to Cayenne message
if use_gps:
    from collect_gps import run_gps
    loc = run_gps()
    LPP_ADD['gps'](loc['lat'], loc['long'], loc['alt'])

# run sensor routine and add values to Cayenne message
from collect_sensors import run_collection
values = run_collection(i2c_bus = i2c_bus, all_sensors = all_sensors, t_wake = settings.T_WAKE)
for key in values:
    LPP_ADD[key](values[key])

# send Cayenne message and reset payload
lpp.send(reset_payload = True)

# store LoRa context in non-volatile RAM (should be using wear leveling)
lora.nvram_save()

# store LoRa frame counter to flash (should be VERY r/w resistant >> RTC memory, millions of cycles)
with open('/flash/counter.txt', 'w') as file:
    file.write(str(LORA_CNT + 1))

# write all values to display in two series
display.poweron()
display.fill(0)
DISPLAY_TEXT['temp'](values['temp'])
DISPLAY_TEXT['pres'](values['pres'])
DISPLAY_TEXT['humi'](values['humi'])
DISPLAY_TEXT['lx'](values['lx'])
DISPLAY_TEXT['uv'](values['uv'])
DISPLAY_TEXT['perc'](values['perc'])
display.show()
machine.sleep(settings.T_DISPLAY * 1000)
display.fill(0)
DISPLAY_TEXT['volu'](values['volu'])
DISPLAY_TEXT['voc'](values['voc'])
DISPLAY_TEXT['perc'](values['perc'])
if all_sensors == True:
    DISPLAY_TEXT['co2'](values['co2'])
    DISPLAY_TEXT['pm25'](values['pm25'])
    DISPLAY_TEXT['pm10'](values['pm10'])
display.show()
machine.sleep(settings.T_DISPLAY * 1000)
display.poweroff()

# set up for deepsleep
awake_time = time.ticks_ms() - wake_time                        # time in seconds the program has been running
push_button = machine.Pin('P23', mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
machine.pin_sleep_wakeup(['P23'], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
machine.deepsleep(settings.T_INTERVAL * 1000 - awake_time)      # deepsleep for remainder of the interval time