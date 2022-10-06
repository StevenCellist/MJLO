#_main.py -- frozen into the firmware along all other modules
version_str = "v2.6.4"
version_int = int(version_str.replace('v', '').replace('.', ''))

import time
import pycom
import machine
import pins

start_time = time.ticks_ms()                            # save current boot time
wake_reason = machine.wake_reason()[0]                  # tuple of (wake_reason, GPIO_list)

from lib.SSD1306 import SSD1306
i2c = machine.I2C(0, pins = (pins.SDA, pins.SCL))       # create I2C object
display = SSD1306(128, 64, i2c)                         # initialize display (4.4 / 0.0 mA)

# on first boot, disable integrated LED and WiFi, set firmware version and check for SD card updates
if wake_reason == machine.PWRON_WAKE:
    pycom.heartbeat_on_boot(False)
    pycom.wifi_on_boot(False)
    pycom.nvs_set("fwversion", version_int)

    from lib.updateFW import check_SD
    reboot = check_SD(display)
    if reboot:
        machine.reset()                                 # in case of an update, reboot the device

# if woken up from deepsleep, there was no error on the previous boot, so make sure to set register to 0
else:
    if pycom.nvs_get("error") == 1:
        pycom.nvs_set("error", 0)

display.fill(0)
display.text("MJLO-{:>02}".format(pycom.nvs_get('node')), 1, 1)
display.text("FW {}".format(version_str), 1, 11)
display.show()

""" This part is only executed if debug is set to 1 """
if pycom.nvs_get('debug') == 1:
    
    if wake_reason == machine.PIN_WAKE:                 # if button is pressed in DEBUG mode, enable GPS
        from collect_gps import run_gps
        loc = run_gps(timeout = 120)                    # try to find a GPS fix within 120 seconds
        print("NB", loc['lat'], "OL", loc['long'], "H", loc['alt'])

    from collect_sensors import run_collection
    values = run_collection(i2c = i2c, all_sensors = True, t_wake = pycom.nvs_get('t_wake'))

    print("Temp: "   + str(values['temp']) + " C")
    print("Druk: "   + str(values['pres']) + " hPa")
    print("Vocht: "  + str(values['humi']) + " %")
    print("Licht: "  + str(values[  'lx']) + " lx")
    print("UV: "     + str(values[  'uv']))
    print("Accu: "   + str(values['perc']) + " %")
    print("Volume: " + str(values['volu']) + " dB")
    print("VOC: "    + str(values[ 'voc']) + " Ohm")
    print("CO2: "    + str(values[ 'co2']) + " ppm")
    print("PM2.5: "  + str(values['pm25']) + " ppm")
    print("PM10: "   + str(values['pm10']) + " ppm")

    push_button = machine.Pin(pins.Wake, mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
    machine.pin_sleep_wakeup([pins.Wake], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
    machine.deepsleep((pycom.nvs_get('t_debug') - 30) * 1000)   # deepsleep for remainder of the interval time

""" This part is only executed if debug is set to 0 """
import network
import socket

lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)   # create LoRa object
LORA_FCNT = 0                                           # default LoRa frame count
if wake_reason != machine.PWRON_WAKE:                   # if woken up from deepsleep (timer or button)..
    lora.nvram_restore()                                # ..restore LoRa information from nvRAM
    LORA_FCNT = pycom.nvs_get('fcnt')                   # ..restore LoRa frame count from nvRAM

LORA_FPORT = 1                                          # default LoRa packet decoding type

# every ADR'th message or if the button was pushed, use all sensors (overrules FPORT = 1)
if LORA_FCNT % pycom.nvs_get('adr') == 0 or wake_reason == machine.PIN_WAKE:
    LORA_FPORT = 2                                      # LoRa packet decoding type 2 (use all sensors)

# every second message of the day, enable GPS (but not if the button was pressed) (overrules FPORT = 1 and 2)
if LORA_FCNT % int(86400 / pycom.nvs_get('t_int')) == 1 and wake_reason != machine.PIN_WAKE:
    LORA_FPORT = 3                                      # LoRa packet decoding type 3 (use GPS)

# if GPS or all sensors are used, send on high SF (don't let precious power go to waste)
if LORA_FPORT > 1:
    LORA_SF = pycom.nvs_get('sf_h')
else:
    LORA_SF = pycom.nvs_get('sf_l')

lora.sf(LORA_SF)                                        # set SF for this uplink
LORA_DR = 12 - LORA_SF                                  # calculate DR for this SF

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)      # create a LoRa socket (blocking)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_DR)    # set the LoRaWAN data rate
s.bind(LORA_FPORT)                                      # set the type of message used for decoding the packet

# join the network upon first-time wake
if LORA_FCNT == 0:
    import secret

    if pycom.nvs_get('lora') == 0:  # OTAA
        mode = network.LoRa.OTAA
    else:                           # ABP
        mode = network.LoRa.ABP

    lora.join(activation = mode, auth = secret.auth(), dr = LORA_DR)
    # don't wait for has_joined() here: sensors will take ~25 seconds first anyway

# run sensor routine
from collect_sensors import run_collection
values = run_collection(i2c = i2c, all_sensors = (LORA_FPORT == 2), t_wake = pycom.nvs_get('t_wake'))

def pack(value, precision, size = 2):
    value = int(value / precision)                      # round to precision
    value = max(0, min(value, 2**(8*size) - 1))         # stay in range 0 .. int.max_size - 1
    return value.to_bytes(size, 'big')                  # pack to bytes

# create a dataframe with sensor values that are always measured (15 bytes)
frame = pack(values['volt'], 0.001) + pack(values['temp'] + 25, 0.01) + pack(values['pres'], 0.1) \
        + pack(values['humi'], 0.5, size = 1) + pack(values['volu'], 0.5, size = 1) \
        + pack(values['lx'], 1) + pack(values['uv'], 1) + pack(values['voc'], 1, size = 3)

if LORA_FPORT == 2:
    # add extra sensor values (frame is now 15 + 6 = 21 bytes)
    frame += pack(values['co2'], 1) + pack(values['pm25'], 0.1) + pack(values['pm10'], 0.1)

if LORA_FPORT == 3:
    # run gps routine
    from collect_gps import run_gps
    loc = run_gps(timeout = 120)                        # try to find a GPS fix within 120 seconds

    # add gps values and current firmware version (frame is now 15 + 9 + 1 = 25 bytes)
    frame += pack(loc['lat'] + 90, 0.0000001, size = 4) + pack(loc['long'] + 180, 0.0000001, size = 4) \
            + pack(loc['alt'], 0.1, size = 1) + pack(pycom.nvs_get("fwversion"), 1, size = 1)

if lora.has_joined():
    # send LoRa message and store LoRa context + frame count in NVRAM
    s.send(frame)
    lora.nvram_save()
    pycom.nvs_set('fcnt', LORA_FCNT + 1)

    # write all values to display in two series
    display.fill(0)
    display.text("Temp: "   + str(round(values['temp'], 1)) + " C",   1,  1),
    display.text("Druk: "   + str(round(values['pres'], 1)) + " hPa", 1, 11),
    display.text("Vocht: "  + str(round(values['humi'], 1)) + " %",   1, 21),
    display.text("Licht: "  + str(round(values[  'lx']   )) + " lx",  1, 31),
    display.text("UV: "     + str(round(values[  'uv']   )),          1, 41),
    display.text("Accu: "   + str(round(values['perc']   )) + " %",   1, 54),
    display.show()
    machine.sleep(pycom.nvs_get('t_disp') * 1000)
    display.fill(0)
    display.text("Volume: " + str(round(values['volu']   )) + " dB",  1,  1),
    display.text("VOC: "    + str(round(values[ 'voc']   )) + " Ohm", 1, 11),
    if LORA_FPORT == 2:
        display.text("CO2: "   + str(round(values[ 'co2'])) + " ppm", 1, 21),
        display.text("PM2.5: " + str(round(values['pm25'])) + " ppm", 1, 31),
        display.text("PM10: "  + str(round(values['pm10'])) + " ppm", 1, 41),
    display.text("Accu: "      + str(round(values['perc'])) + " %",   1, 54),
    display.show()
    machine.sleep(pycom.nvs_get('t_disp') * 1000)
    display.poweroff()
else:
    display.fill(0)
    display.text("Geen verbinding", 1, 1)
    display.show()

# set up for deepsleep
awake_time = time.ticks_diff(time.ticks_ms(), start_time) - 2800    # time in milliseconds the program has been running
push_button = machine.Pin(pins.Wake, mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
machine.pin_sleep_wakeup([pins.Wake], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
machine.deepsleep(pycom.nvs_get('t_int') * 1000 - awake_time)       # deepsleep for remainder of the interval time