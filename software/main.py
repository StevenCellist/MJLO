#%% imports
import network
import ubinascii
import struct
import socket

from lib.cayenneLPP import CayenneLPP
from lib.VEML6070 import VEML6070
from lib.TSL2591 import TSL2591
from lib.BME680 import BME680
from lib.MQ135 import MQ135
from lib.SSD1306 import SSD1306
from lib.micropyGPS import MicropyGPS
import settings

# set up display and GPS (TODO)
i2c_bus = machine.I2C(0, machine.I2C.MASTER)
display = SSD1306(128, 64, i2c_bus)                 # active: ~5 mA, sleep: 0.0 mA
gps = MicropyGPS()


#%% setup LoRa
if settings.DEBUG_MODE == False:
    lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868, sf = 9)       # create LoRa object TODO power_mode = network.LoRa.TX_ONLY
    lora.nvram_restore()                                        # restore the LoRa information from nvRAM
    # if LoRa was not (correctly) restored from nvRAM, try to connect
    if not lora.has_joined():
        app_eui = ubinascii.unhexlify(settings.APP_EUI)
        app_key = ubinascii.unhexlify(settings.APP_KEY)
            
        lora.join(activation = network.LoRa.OTAA, auth = (app_eui, app_key), timeout = 0)
        display.text("Verbinden...", 1, 1)
        display.show()

        print('Verbinden met LoRaWAN')
        while not lora.has_joined():
            print('.', end = '')
            time.sleep(0.2)

    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)      # create a LoRa socket.
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 3)          # set the LoRaWAN data rate. TODO use at least SF9 as configured in TTN.. but rather SF12
    s.setblocking(True)
    lpp = CayenneLPP(size = 54, sock = s)                   # TODO evaluate SF12 (51 bytes)

    print('Verbonden met LoRa!')
    display.text("Verbonden!", 1, 11)

else:
    print("Debug mode")


#%% process sensor values
def send_values(display_on = False):
    if settings.DEBUG_MODE == False:
        # create cayenne LPP packet
        lpp.add_analog_input(batt_volt, channel = 0)        # 1+1+2=4: 0.01 V accurate
        lpp.add_temperature(temperature, channel = 1)       # 1+1+2=4: 0.1 C accurate
        lpp.add_barometric_pressure(pressure, channel = 2)  # 1+1+2=4: 0.1 hPa accurate
        lpp.add_relative_humidity(humidity, channel = 3)    # 1+1+1=3: 0.5% accurate (range 0-100)
        lpp.add_luminosity(loudness, channel = 4)           # 1+1+2=4: 1 accurate (range 0-4096)
        lpp.add_luminosity(light, channel = 5)              # 1+1+2=4: 1 lux accurate (range 0-65536)
        lpp.add_luminosity(uv_raw, channel = 6)             # 1+1+2=4: 1 lux accurate (range 0-9999)
        lpp.add_luminosity(tVOC, channel = 7)               # 1+1+2=4: 1 ppb accurate (range 0-1187)
        lpp.add_luminosity(ppm_co2, channel = 8)            # 1+1+2=4: 1 ppm accurate (range 0-65536)
        lpp.add_barometric_pressure(pm_25, channel = 9)     # 1+1+2=4: 0.1 ug/m3 accurate (range 0.0-999.9) TODO: Find out if it is better to use unsigned fields for these
        lpp.add_barometric_pressure(pm_100, channel = 10)   # 1+1+2=4: 0.1 ug/m3 accurate (range 0.0-999.9)
        lpp.add_gps(gps.latitude, gps.longitude, gps.altitude, channel = 11)    # 1+1+9=11: 0.0001, 0.0001 and 0.01 accurate resp.
        lpp.send(reset_payload = True)

        # we don't need LoRa anymore so we save LoRa object to NVRAM and profit from machine.sleep's reduced power consumption
        lora.nvram_save()                                   # TODO figure out if socket.send is indeed nonblocking
    else:
        # print all of the sensor values via REPL (serial)
        print("GPS: NB %f, OL %f, H %f" % (gps.latitude, gps.longitude, gps.altitude))
        print("Luchtdruk: %.2f"         % pressure)
        print("Temperatuur: %.2f "      % temperature)
        print("Luchtvochtigheid: %d"    % humidity)
        print("Fijnstof 2.5, 10: %.2f, %.2f" % (pm_25, pm_100))
        print("Volume: %d"              % loudness)
        print("VOC, CO2: %d %d"         % (tVOC, ppm_co2))
        print("UV index: %d"            % uv_raw)
        print("Lux: %d"                 % light)
        print("Voltage: %.3f, %d %%"    % (batt_volt, batt_perc))

    if display_on:  # display all sensor data on display
        display.poweron()
        display.fill(0)
        display.text("Temp: %.2f"     % temperature, 1,  1)
        display.text("Druk: %.2f "    % pressure,    1, 11)
        display.text("Vocht: %d %%"   % humidity,    1, 21)
        display.text("Lux: %d"        % light,       1, 31)
        display.text("UV index: %s"   % uv_raw,      1, 41)
        display.text("Accu: ~ %d %%"  % batt_perc,   1, 54)
        display.show()
        machine.sleep(settings.DISPLAY_TIME * 1000)
        display.fill(0)
        display.text("Stof 2.5: %.2f" % pm_25,     1,  1)
        display.text("Stof 10: %.2f"  % pm_100,    1, 11)
        display.text("VOC: %d"        % tVOC,      1, 21)
        display.text("CO2: %d"        % ppm_co2,   1, 31)
        display.text("Volume: %d"     % loudness,  1, 41)
        display.text("Accu: ~ %d %%"  % batt_perc, 1, 54)
        display.show()
        machine.sleep(settings.DISPLAY_TIME * 1000)
        display.fill(0)
        display.poweroff()

#%% retrieve sensor values from RTC memory
# get access to RTC module for deepsleep memory
rtc = machine.RTC()

delimiter = b'\x21\x21'  # TODO might need better delimiter, but this has never given any errors yet

# restore values of previous cycle from psRAM (returns None if not set) and process them
previous_values = rtc.memory()
if previous_values:
    previous_values = previous_values.split(delimiter)
    batt_volt = struct.unpack('f', previous_values[0])[0]   # unpack returns tuple (unpacked_value,) so we select [0] everytime
    temperature = struct.unpack('f', previous_values[1])[0]
    pressure  = struct.unpack('f', previous_values[2])[0]
    humidity = struct.unpack('f', previous_values[3])[0]
    loudness = struct.unpack('i', previous_values[4])[0]
    light = struct.unpack('i', previous_values[5])[0]
    uv_raw = struct.unpack('i', previous_values[6])[0]
    tVOC = struct.unpack('i', previous_values[7])[0]
    ppm_co2 = struct.unpack('i', previous_values[8])[0]
    pm_25 = struct.unpack('f', previous_values[9])[0]
    pm_100 = struct.unpack('f', previous_values[10])[0]

    voc_hum_base = struct.unpack('f', previous_values[11])[0]
    voc_counter = struct.unpack('i', previous_values[12])[0]
    voc_baseline = struct.unpack('i', previous_values[13])[0]
    # calculate approx. battery percentage, assuming a range of 3.3 to 4.3 Volts on the battery
    batt_perc = (batt_volt - 3.3) * 100

    send_values(display_on = True)
else:
    tVOC = 125
    voc_hum_base = 0
    voc_counter = 6
    voc_baseline = 0

#%% start other sensors
bme680 =     BME680(i2c=i2c_bus, address=0x77)              # temp, pres, hum, VOC sensor
                                                            # active: 22 mA, sleep: 0.7 mA (forced query mode)
veml6070 = VEML6070(i2c=i2c_bus, address=56)                # UV sensor
veml6070.sleep()                                            # active: 0.0 mA, sleep: 0.0 mA
tsl2591 =  TSL2591(i2c=i2c_bus, address=0x29)               # lux sensor
tsl2591.sleep()                                             # active: 0.0 mA, sleep: 0.0 mA
mq135 = MQ135('P17')                                        # CO2 sensor
                                                            # active: 40 mA, sleep: 0.0 mA
volt_pin = machine.ADC().channel(pin = 'P15', attn=machine.ADC.ATTN_11DB)   # analog voltage sensor for battery level
max4466 =  machine.ADC().channel(pin = 'P18', attn=machine.ADC.ATTN_11DB)   # analog loudness sensor
                                                            # active: 0.3 mA, sleep: 0.3 mA (always on)


#%% get sensor values and put sensors to sleep immediately after
polls = 3   # poll every sensor multiple times for more reliable values

tsl2591.wake()
veml6070.wake()

batt_volt = sum([volt_pin.voltage() * 2 / 1000 for _ in range(polls)]) / polls
temperature = sum([bme680.temperature for _ in range(polls)]) / polls
humidity = sum([bme680.relative_humidity for _ in range(polls)]) / polls
pressure = sum([bme680.pressure for _ in range(polls)]) / polls

tVOC, voc_hum_base, voc_counter, voc_baseline = bme680.gas(temperature, humidity, tVOC, voc_hum_base, voc_counter, voc_baseline, polls)

loudness = sum([max4466.value() for _ in range(polls)]) / polls
light = sum([tsl2591.calculate_lux() for _ in range(polls)]) / polls
uv_raw = sum([veml6070.uv_raw for _ in range(polls)]) / polls
uv_index = veml6070.get_index(uv_raw)

tsl2591.sleep()
veml6070.sleep()

current_interval = time.ticks_ms() - wake_time              # calculate how long SDS011 has been running yet
machine.sleep(settings.WAKE_TIME * 1000 - current_interval) # sleep for the remaining time

while not sds011.read():                                    # make sure we get response from SDS011
    pass

pm_25 = sds011.pm25
pm_100 = sds011.pm10
sds011.sleep()

ppm_co2 = sum([mq135.get_corrected_ppm(temperature, humidity) for _ in range(polls)]) / polls
mq135_en.value(0)


#%% hibernate, but restart to GPS mode if push button is pressed
push_button = machine.Pin('P23', mode=machine.Pin.IN, pull=machine.Pin.PULL_DOWN)
machine.pin_sleep_wakeup(['P23'], mode=machine.WAKEUP_ANY_HIGH, enable_pull=True)

# write all values to psRAM to send during next wake
memory_string = ( struct.pack('f', float(batt_volt)) + delimiter
                + struct.pack('f', float(temperature)) + delimiter
                + struct.pack('f', float(pressure)) + delimiter
                + struct.pack('f', float(humidity)) + delimiter
                + struct.pack('i', int(loudness)) + delimiter
                + struct.pack('i', int(light)) + delimiter
                + struct.pack('i', int(uv_raw)) + delimiter
                + struct.pack('i', int(tVOC)) + delimiter
                + struct.pack('i', int(ppm_co2)) + delimiter
                + struct.pack('f', float(pm_25)) + delimiter
                + struct.pack('f', float(pm_100)) + delimiter
                + struct.pack('f', float(voc_hum_base)) + delimiter
                + struct.pack('i', int(voc_counter)) + delimiter
                + struct.pack('i', int(voc_baseline)))
rtc.memory(memory_string)

machine.deepsleep(settings.SLEEP_TIME * 1000)