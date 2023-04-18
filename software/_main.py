#_main.py -- frozen into the firmware along all other modules
version_str = "v2.7"
version_int = int(version_str.replace('v', '').replace('.', ''))

import time
import pycom
import machine
import network
import socket
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

lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)   # create LoRa object
LORA_FCNT = 0                                           # default LoRa frame count
if wake_reason != machine.PWRON_WAKE:                   # if woken up from deepsleep (timer or button)..
    lora.nvram_restore()                                # ..restore LoRa information from nvRAM
    LORA_FCNT = pycom.nvs_get('fcnt')                   # ..restore LoRa frame count from nvRAM

LORA_FPORT = 1                                          # default LoRa packet decoding type 1
# every second message of the day, enable GPS (but not if the button was pressed)
if LORA_FCNT % int(86400 / pycom.nvs_get('t_int')) == 1 and wake_reason != machine.PIN_WAKE:
    LORA_FPORT = 2                                      # LoRa packet decoding type 2

LORA_SF = pycom.nvs_get('sf_l')                         # default SF (low)
# every adr'th message, or if GPS is used, send on high SF
if LORA_FCNT % pycom.nvs_get('adr') == 0 or LORA_FPORT == 2:
    LORA_SF = pycom.nvs_get('sf_h')

lora.sf(LORA_SF)                                        # set SF for this uplink
LORA_DR = 12 - LORA_SF                                  # calculate DR for this SF

sckt = socket.socket(socket.AF_LORA, socket.SOCK_RAW)   # create a LoRa socket (blocking)
sckt.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_DR) # set the LoRaWAN data rate
sckt.bind(LORA_FPORT)                                   # set the type of message used for decoding the packet

# join the network upon first-time wake
if LORA_FCNT == 0:
    import secret

    mode = network.LoRa.OTAA if pycom.nvs_get('lora') == 0 else network.LoRa.ABP
    lora.join(activation = mode, auth = secret.auth(), dr = LORA_DR)
    # don't wait for has_joined() here: sensors will take ~30 seconds first anyway

display.fill(0)
display.text("MJLO-{:>02}" .format(pycom.nvs_get('node')), 1,  1)
display.text("FW {}"       .format(version_str),           1, 11)
display.text("SF    {:> 2}".format(LORA_SF),               1, 34)
display.text("fport  {}"   .format(LORA_FPORT),            1, 44)
display.text("fcnt {:> 4}" .format(LORA_FCNT),             1, 54)
display.show()

# run sensor routine
from collect_sensors import run_collection
from LoRa_frame import make_frame
values, perc = run_collection(i2c = i2c, t_wake = pycom.nvs_get('t_wake'))

if LORA_FPORT == 2:
    values['fw'] = pycom.nvs_get('fwversion')           # add current firmware version to values

    # run gps routine
    from collect_gps import run_gps
    gps = run_gps(timeout = 120)                        # try to find a GPS fix within 120 seconds
    if gps:
        values['lat'], values['long'], values['alt'], values['hdop'] = gps  # save values in dict

if lora.has_joined():
    # send LoRa message and store LoRa context + frame count in NVRAM
    frame = make_frame(values)                          # pack OrderedDict to LoRa frame
    sckt.send(frame)
    lora.nvram_save()
    pycom.nvs_set('fcnt', LORA_FCNT + 1)
else:
    # if LoRa failed to join, don't save LoRa context + frame count to NVRAM
    # this way, it will retry to join on the next wakeup
    display.fill(0)
    display.text("Geen verbinding", 1, 1)
    display.show()
    machine.sleep(pycom.nvs_get('t_disp') * 1000)
sckt.close()

# write all values to display in two sets
display.fill(0)
display.text("Temp: {:> 6} C"   .format(round(values['temp'], 1)), 1,  1)
display.text("Druk: {:> 6} hPa" .format(round(values['pres'], 1)), 1, 11)
display.text("Vocht: {:> 5} %"  .format(round(values['humi'], 1)), 1, 21)
display.text("Licht: {:> 5} lx" .format(round(values[  'lx']   )), 1, 31)
display.text("UV: {:> 8}"       .format(round(values[  'uv']   )), 1, 41)
display.text("Accu: {:> 6} %"   .format(round(        perc     )), 1, 54)
display.show()
machine.sleep(pycom.nvs_get('t_disp') * 1000)
display.fill(0)
display.text("Volume: {:> 4} dB".format(round(values['volu']   )), 1,  1)
display.text("VOC: {:> 7}"      .format(round(values[ 'voc']   )), 1, 11)
display.text("CO2: {:> 7} ppm"  .format(round(values[ 'co2']   )), 1, 21)
display.text("PM2.5: {:> 5} ppm".format(round(values['pm25'], 1)), 1, 31)
display.text("PM10: {:> 6} ppm" .format(round(values['pm10'], 1)), 1, 41)
display.text("Accu: {:> 6} %"   .format(round(        perc     )), 1, 54)
display.show()
machine.sleep(pycom.nvs_get('t_disp') * 1000)
display.poweroff()

# if there was an error last time but we got here now, set register to 0
if pycom.nvs_get("error") != 0:
    pycom.nvs_set("error", 0)

# set up for deepsleep
awake_time = time.ticks_diff(time.ticks_ms(), start_time) - 3000    # time in milliseconds the program has been running
push_button = machine.Pin(pins.Wake, mode = machine.Pin.IN, pull = machine.Pin.PULL_DOWN)   # initialize wake-up pin
machine.pin_sleep_wakeup([pins.Wake], mode = machine.WAKEUP_ANY_HIGH, enable_pull = True)   # set wake-up pin as trigger
machine.deepsleep(pycom.nvs_get('t_int') * 1000 - awake_time)       # deepsleep for remainder of the interval time