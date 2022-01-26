import machine
import settings

from lib.micropyGPS import MicropyGPS
gps_en = machine.Pin('P22', mode=machine.Pin.OUT)               # 2N2907 (PNP) gate pin
gps_en.hold(False)                                              # disable hold from deepsleep
gps_en.value(1)                                                 # keep disabled
gps = MicropyGPS()                                              # create GPS object

from lib.SSD1306 import SSD1306
i2c_bus = machine.I2C(0, machine.I2C.MASTER)                    # create I2C object and initialize (inactive) display
display = SSD1306(128, 64, i2c_bus)
display.poweroff()


#%% get GPS location if pushbutton was pressed
wake_reason = machine.wake_reason()[0]                          # tuple of (wake_reason, GPIO_list)
if wake_reason == machine.PIN_WAKE:
    
    gps_en.value(0)                                             # enable GPS power
    com2 = machine.UART(2, pins=('P3', 'P4'),  baudrate=9600)   # GPS communication

    display.poweron()
    display.fill(0)
    display.text("GPS gestart!", 1, 1)
    display.show()
    
    while True:
        while com2.any():                                       # wait for incoming communication
            print('.', end = '')
            my_sentence = com2.readline()                       # read NMEA sentence
            for x in my_sentence:
                gps.update(chr(x))                              # decode it through micropyGPS

        if gps.latitude > 0 and gps.longitude > 0:              # once we found valid data, power off GPS module and show data on display
            gps_en.value(1)                                     # disable GPS power

            print("GPS: NB %f, OL %f, H %f" % (gps.latitude, gps.longitude, gps.altitude))
            display.text("GPS locatie:",           1, 11)
            display.text("NB: %f" % gps.latitude,  1, 21)
            display.text("OL: %f" % gps.longitude, 1, 31)
            display.text("H:  %f" % gps.altitude,  1, 41)
            display.show()
            machine.sleep(settings.DISPLAY_TIME)
            display.poweroff()
            break

#%% retrieve sensor values from RTC memory
import struct
rtc = machine.RTC()         # get access to RTC module for deepsleep memory

delimiter = b'\x21\x21'     # TODO might need better delimiter, but this has never given any errors yet

if wake_reason == machine.RTC_WAKE or wake_reason == machine.PIN_WAKE:
    # restore values of previous cycle from psRAM
    previous_values = rtc.memory()
    previous_values = previous_values.split(delimiter)
    batt_volt =     struct.unpack('f', previous_values[0])[0]   # unpack returns tuple (unpacked_value,) so we select [0] everytime
    temperature =   struct.unpack('f', previous_values[1])[0]
    pressure  =     struct.unpack('f', previous_values[2])[0]
    humidity =      struct.unpack('f', previous_values[3])[0]
    dBm =           struct.unpack('f', previous_values[4])[0]
    light =         struct.unpack('i', previous_values[5])[0]
    uv_raw =        struct.unpack('i', previous_values[6])[0]
    tVOC =          struct.unpack('i', previous_values[7])[0]
    co2 =           struct.unpack('i', previous_values[8])[0]
    pm_25 =         struct.unpack('f', previous_values[9])[0]
    pm_100 =        struct.unpack('f', previous_values[10])[0]

    # calculate approx. battery percentage, assuming a range from 3.1 to 4.1 Volts on the battery
    batt_perc = (batt_volt - 3.1) * 100

#%% set up LoRa and send values over CayenneLPP
import network
import socket
import ubinascii
import time

from lib.cayenneLPP import CayenneLPP

if settings.DEBUG_MODE == False:
    lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868, sf = settings.LORA_SF)            # create LoRa object
    
    if wake_reason != machine.RTC_WAKE and wake_reason != machine.PIN_WAKE:
        app_eui = ubinascii.unhexlify(settings.APP_EUI)
        app_key = ubinascii.unhexlify(settings.APP_KEY)
        lora.join(activation = network.LoRa.OTAA, auth = (app_eui, app_key), timeout = 0, dr = settings.LORA_DR)    # join with SF9
        display.poweron()
        display.text("Verbinden...", 1, 1)
        display.show()

        print("Verbinden met LoRaWAN", end = '')
        while not lora.has_joined():
            print('.', end = '')
            time.sleep(0.5)

        display.text("Verbonden!", 1, 11)
        display.show()

    # if we woke from deepsleep, i.e. there are sensor values present, send them over LoRa
    if wake_reason == machine.RTC_WAKE or wake_reason == machine.PIN_WAKE:
        lora.nvram_restore()                                            # restore the LoRa information from nvRAM
        s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)              # create a LoRa socket.
        s.setsockopt(socket.SOL_LORA, socket.SO_DR, settings.LORA_DR)   # set the LoRaWAN data rate
        s.setblocking(True)
        
        # create cayenne LPP packet
        if wake_reason == machine.PIN_WAKE:
            lpp = CayenneLPP(size = 53, sock = s)           # set payload size; 42 base + 11 GPS
            lpp.add_gps(gps.latitude, gps.longitude, gps.altitude, channel = 11)    # 1+1+9=11: 0.0001, 0.0001 and 0.01 accurate resp.
        else:
            lpp = CayenneLPP(size = 42, sock = s)

        lpp.add_analog_input(batt_volt, channel = 0)        # 1+1+2=4: 0.01 V accurate                      TODO humidity??
        lpp.add_temperature(temperature, channel = 1)       # 1+1+2=4: 0.1 C accurate
        lpp.add_barometric_pressure(pressure, channel = 2)  # 1+1+2=4: 0.1 hPa accurate
        lpp.add_relative_humidity(humidity, channel = 3)    # 1+1+1=3: 0.5% accurate  (range 0-100)
        lpp.add_relative_humidity(dBm, channel = 4)         # 1+1+1=3: 0.5 accurate   (range 0-80)
        lpp.add_luminosity(light, channel = 5)              # 1+1+2=4: 1 lux accurate (range 0-65536)
        lpp.add_luminosity(uv_raw, channel = 6)             # 1+1+2=4: 1 lux accurate (range 0-9999)        TODO humidity??
        lpp.add_luminosity(tVOC, channel = 7)               # 1+1+2=4: 1 ppb accurate (range 0-1187)
        lpp.add_luminosity(co2, channel = 8)                # 1+1+2=4: 1 ppm accurate (range 0-65536)
        lpp.add_barometric_pressure(pm_25, channel = 9)     # 1+1+2=4: 0.1 ug/m3 accurate (range 0.0-999.9) TODO humidity??
        lpp.add_barometric_pressure(pm_100, channel = 10)   # 1+1+2=4: 0.1 ug/m3 accurate (range 0.0-999.9) TODO humidity??
        lpp.send(reset_payload = True)

    # we don't need LoRa anymore so we save LoRa object to NVRAM and profit from machine.sleep's reduced power consumption
    lora.nvram_save()

#%% start PM and CO2 sensor
from lib.SDS011 import SDS011
from lib.MQ135 import MQ135

mq135_en = machine.Pin('P8', mode=machine.Pin.OUT)          # MQ135 VIN pin
mq135_en.hold(False)                                        # disable hold from deepsleep
mq135_en.value(1)                                           # preheat
mq135 = MQ135('P17')                                        # CO2 sensor
                                                            # active: 40 mA, sleep: 0.0 mA

sds011_en = machine.Pin('P21', mode=machine.Pin.OUT)        # voltage regulator SHDN pin
sds011_en.hold(False)                                       # disable hold from deepsleep
sds011_en.value(1)                                          # start fan and laser
com = machine.UART(1, pins=('P20', 'P19'), baudrate=9600)   # UART communication to SDS011
sds011 = SDS011(com)                                        # fine particle sensor

machine.sleep(settings.PEAK_TIME * 1000)                    # DO NOT even attempt to do anything after enabling the voltage regulator

#%% show sensor values on display
if wake_reason == machine.RTC_WAKE or wake_reason == machine.PIN_WAKE:
    if settings.DEBUG_MODE == True:
        print("Luchtdruk: %.2f"         % pressure)
        print("Temperatuur: %.2f "      % temperature)
        print("Luchtvochtigheid: %d"    % humidity)
        print("Fijnstof 2.5, 10: %.2f, %.2f" % (pm_25, pm_100))
        print("Volume: %d"              % dBm)
        print("VOC, CO2: %d %d"         % (tVOC, co2))
        print("UV index: %d"            % uv_raw)
        print("Lux: %d"                 % light)
        print("Voltage: %.3f, +/-%d %%" % (batt_volt, batt_perc))
    display.poweron()
    display.fill(0)
    display.text("Temp: %.2f"     % temperature, 1,  1)
    display.text("Druk: %.2f "    % pressure,    1, 11)
    display.text("Vocht: %d %%"   % humidity,    1, 21)
    display.text("Lux: %d"        % light,       1, 31)
    display.text("UV: %s"         % uv_raw,      1, 41)
    display.text("Accu: +/-%d %%" % batt_perc,   1, 54)
    display.show()
    machine.sleep(settings.DISPLAY_TIME * 1000)
    display.fill(0)
    display.text("Stof 2.5: %.2f" % pm_25,     1,  1)
    display.text("Stof 10: %.2f"  % pm_100,    1, 11)
    display.text("VOC: %d"        % tVOC,      1, 21)
    display.text("CO2: %d"        % co2,       1, 31)
    display.text("Volume: %d"     % dBm,       1, 41)
    display.text("Accu: +/-%d %%" % batt_perc, 1, 54)
    display.show()
    machine.sleep(settings.DISPLAY_TIME * 1000)
    display.fill(0)
    display.poweroff()

    machine.sleep((settings.WAKE_TIME - settings.PEAK_TIME - 2*settings.DISPLAY_TIME) * 1000)   # residue of stabilization time
else:
    machine.sleep((settings.WAKE_TIME - settings.PEAK_TIME) * 1000)

while not sds011.read():    # make sure we get response from SDS011
    pass

pm_25 = sds011.pm25
pm_100 = sds011.pm10
sds011_en.value(0)          # disable voltage regulator
sds011_en.hold(True)        # hold pin low during deepsleep


#%% get other sensors' values and put them to sleep immediately after
from lib.VEML6070 import VEML6070
from lib.TSL2591 import TSL2591
from lib.BME680 import BME680

bme680 =     BME680(i2c=i2c_bus, address=0x77)              # temp, pres, hum, VOC sensor
                                                            # active: 22 mA, sleep: 0.0 mA
bme680.temperature_oversample = 16                          # maximum accuracy
bme680.humidity_oversample = 16
bme680.pressure_oversample = 16

temperature = bme680.temperature
humidity = bme680.relative_humidity
pressure = bme680.pressure
tVOC = bme680.gas
bme680.set_power_mode(0)

polls = 3   # poll some sensors multiple times for more reliable values

co2 = sum([mq135.get_corrected_ppm(temperature, humidity) for _ in range(polls)]) / polls
mq135_en.value(0)           # disable heating element
mq135_en.hold(True)         # hold pin low during deepsleep

veml6070 = VEML6070(i2c=i2c_bus, address=56)                # UV sensor
                                                            # active: 0.0 mA, sleep: 0.0 mA
uv_raw = sum([veml6070.uv_raw for _ in range(polls)]) / polls
uv_raw = max(1, uv_raw) # prevent sending zeroes over Cayenne which messes with the decoding
veml6070.sleep()

tsl2591 =  TSL2591(i2c=i2c_bus, address=0x29)               # lux sensor
                                                            # active: 0.0 mA, sleep: 0.0 mA
light = sum([tsl2591.calculate_lux() for _ in range(polls)]) / polls
light = max(1, light)   # prevent sending zeroes over Cayenne which messes with the decoding
tsl2591.sleep()

volt_pin = machine.ADC().channel(pin = 'P15', attn=machine.ADC.ATTN_11DB)   # analog voltage sensor for battery level
batt_volt = sum([volt_pin.voltage() * 2 / 1000 for _ in range(polls)]) / polls

max4466 =  machine.ADC().channel(pin = 'P18', attn=machine.ADC.ATTN_11DB)   # analog loudness sensor
                                                            # active: 0.3 mA, sleep: 0.3 mA (always on)
loudness_voltage = sum([max4466.voltage() / 1000 for _ in range(polls)]) / polls
dBm = (40 * loudness_voltage - 20)  # https://forum.arduino.cc/t/dbm-from-max4466/398552 TODO calibrate!!!


#%% hibernate, but restart to GPS mode if push button is pressed
# write all values to psRAM to send during next wake
memory_string = ( struct.pack('f', float(batt_volt)) + delimiter
                + struct.pack('f', float(temperature)) + delimiter
                + struct.pack('f', float(pressure)) + delimiter
                + struct.pack('f', float(humidity)) + delimiter
                + struct.pack('f', float(dBm)) + delimiter
                + struct.pack('i', int(light)) + delimiter
                + struct.pack('i', int(uv_raw)) + delimiter
                + struct.pack('i', int(tVOC)) + delimiter
                + struct.pack('i', int(co2)) + delimiter
                + struct.pack('f', float(pm_25)) + delimiter
                + struct.pack('f', float(pm_100)))
rtc.memory(memory_string)

gps_en.hold(True)

push_button = machine.Pin('P23', mode=machine.Pin.IN, pull=machine.Pin.PULL_DOWN)
machine.pin_sleep_wakeup(['P23'], mode=machine.WAKEUP_ANY_HIGH, enable_pull=True)
machine.deepsleep(settings.SLEEP_TIME * 1000)