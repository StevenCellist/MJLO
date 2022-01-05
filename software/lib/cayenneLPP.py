"""
CayenneLPP module.

The constants have the format NAME_SENSOR = (LPP id, Data size) where LPP id
is the IPSO id - 3200 and Data size is the number of bytes that must be used
to encode the reading from the sensor.

https://mydevices.com/cayenne/docs/lora/#lora-cayenne-low-power-payload-overview
"""

import struct

# Some constants of the form
# NAME_SENSOR = (LPP id = IPSO id - 3200, Data size in bytes)
ANALOG_INPUT       = (bytes([2]),   2) # 0.01 signed
ILLUMINANCE_SENSOR = (bytes([101]), 2) # 1 lux unsigned MSB
TEMPERATURE_SENSOR = (bytes([103]), 2) # 0.1 deg Celcius signed MSB
HUMIDITY_SENSOR    = (bytes([104]), 1) # 0.5 unsigned
BAROMETER          = (bytes([115]), 2) # 0.1 hPa unsigned MSB
GPS                = (bytes([136]), 9) # latitude:  0.0001 degree signed MSB
                                       # longiture: 0.0001 degree signed MSB
                                       # altitude:  0.01 meter signed MSB

class CayenneLPP:
    """
    Class for packing data in the Cayenne LPP format

    The payload structure for the Cayenne LPP format is data frame of
    the form: [SENSOR_1, SENSOR_2, ... SENSOR_N], where the format for one
    sensor is defined by: [CHANNEL, SENSOR TYPE, DATA].
    """

    def __init__(self, size = 11, sock = None):

        if size < 3:
            size = 3

        self.size = size
        self.payload = bytes()
        self.socket = sock

    def is_within_size_limit(self, a_size):
        """
        Check if adding data will result in a payload size below size
        """

        if (len(self.payload) + a_size + 2) <= self.size:   # + 2 for 1 channel byte and 1 sensortype byte
            return True
        return False

    def reset_payload(self):
        self.payload = bytes()

    def change_size(self, a_size):
        self.size = a_size

    def get_size(self):
        return len(self.payload)

    def send(self, reset_payload = False):
        """
        Args:
            reset_payload: Indicates whether the payload must be reset after
                           the transmission (i.e. if a socket is defined).
        """

        if self.socket is None:
            return False
        else:
            self.socket.send(self.payload)
            if reset_payload:
                self.reset_payload()
            return True

    def add_analog_input(self, value, channel = 3):
        # Resolution: 0.01, signed.
        if self.is_within_size_limit(ANALOG_INPUT[1]):
            value = int(value * 100)  # precision is 0.01
            self.payload = (self.payload +
                            bytes([channel]) +
                            ANALOG_INPUT[0] +
                            struct.pack('>h', value))
        else:
            raise Exception('payload too big: size exceeds the limit!')

    def add_luminosity(self, value, channel = 5):
        # Resolution: 1 lux, unsigned.
        if self.is_within_size_limit(ILLUMINANCE_SENSOR[1]):
            value = int(value) # precision is 1
            self.payload = (self.payload +
                            bytes([channel]) +
                            ILLUMINANCE_SENSOR[0] +
                            struct.pack('>H', value))
        else:
            raise Exception('payload too big: size exceeds the limit!')

    def add_temperature(self, value, channel = 7):
        # Resolution: 0.1 degrees Celsius, signed.
        if self.is_within_size_limit(TEMPERATURE_SENSOR[1]):
            value = int(value * 10) # precision is 0.1
            self.payload = (self.payload +
                            bytes([channel]) +
                            TEMPERATURE_SENSOR[0] +
                            struct.pack('>h', value))
        else:
            raise Exception('payload too big: size exceeds the limit!')

    def add_relative_humidity(self, value, channel = 8):
        # Resolution: 0.5 %, signed.
        if self.is_within_size_limit(HUMIDITY_SENSOR[1]):
            value = int(value * 2) # precision is 0.5
            self.payload = (self.payload +
                            bytes([channel]) +
                            HUMIDITY_SENSOR[0] +
                            struct.pack('>B', value))
        else:
            raise Exception('payload too big: size exceeds the limit!')

    def add_barometric_pressure(self, value, channel = 10):
        # Resolution: 0.1 hPa, unsigned.
        if self.is_within_size_limit(BAROMETER[1]):
            value = int(value * 10) # precision is 0.1
            self.payload = (self.payload +
                            bytes([channel]) +
                            BAROMETER[0] +
                            struct.pack('>H', value))
        else:
            raise Exception('payload too big: size exceeds the limit!')

    def add_gps(self, lat, lon, alt, channel = 12):
        """
        Resolution:
            0.0001 deg for the latitude and longitute, signed.
            0.01 meters for the altitude, signed.
        """

        if self.is_within_size_limit(GPS[1]):
            lat = int(lat * 10000) # precision is 0.0001 for lat and lon
            lon = int(lon * 10000)
            alt = int(alt * 100)   # precision is 0.01 for altitude
            self.payload = (self.payload +
                            bytes([channel]) +
                            GPS[0] +
                            struct.pack('>l', lat)[1:4] +
                            struct.pack('>l', lon)[1:4] +
                            struct.pack('>l', alt)[1:4])
        else:
            raise Exception('payload too big: size exceeds the limit!')

    def add_generic(self, lpp_id, values, channel = 13, data_size = 1,
                    is_signed = True, precision = 1):
        """
        Adding an generic sensor reading to the payload

        Args:
            channel: The channel of the payload.
            lpp_id: The LPP id of the sensor (IPSO id - 3200).
            data_size: The total number of bytes for the payload.
            is_signed: Show whether we use signed (True) or unsigned (False) encoding.
            precision: The precision of the sensor reading (e.g. 0.01, 1, 0.5).
            values: The data to be encoded, either a scalar or a list.
        """

        if self.is_within_size_limit(data_size):

            # determining the encoding
            enc = ''
            if is_signed:
                enc = '>l'
            else:
                enc = '>L'

            # updating the payload
            self.payload = self.payload + bytes([channel]) + bytes([lpp_id])
            values = int(values / precision)
            self.payload = self.payload + struct.pack(enc, values)[-data_size:]

        else:
            raise Exception('payload too big: size exceeds the limit!')
