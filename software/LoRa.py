import network
import socket
import pycom
import time

_configs = { # bytes, offset, precision
        'temp' : (2, 100, 0.01  ),
        'pres' : (2,   0, 0.1   ),
        'humi' : (1,   0, 0.5   ),
        'voc'  : (2,   0, 1     ),
        'uv'   : (2,   0, 1     ),
        'lx'   : (2,   0, 1     ),
        'volu' : (1,   0, 0.5   ),
        'batt' : (2,   0, 0.001 ),
        'co2'  : (2,   0, 0.1   ),
        'pm25' : (2,   0, 0.1   ),
        'pm10' : (2,   0, 0.1   ),
        'lat'  : (3,  90, 0.0001),
        'long' : (3, 180, 0.0001),
        'alt'  : (2, 100, 0.1   ),
        'hdop' : (1,   0, 0.1   ),
        'fw'   : (1,   0, 1     ),
        'error': (1, 128, 1     )
}

class LoRaWAN:
    def __init__(self, sf = None, fport = None):
        # create lora object
        self.lora = network.LoRa(mode = network.LoRa.LORAWAN, region = network.LoRa.EU868)

        # maybe we got here from error.py after already creating this object in main.py
        # in that case, we should not restore from nvram as that would erase the information
        if not self.has_joined:
            self.lora.nvram_restore()

        # if, after restoring data from nvram, it turns out that lora is not joined, join now
        # this join is performed non-blocking as it should have completed before sending a message
        if not self.has_joined:
            import secret
            self.lora.join(activation = pycom.nvs_get('lora'),      # 0 = OTAA, 1 = ABP
                           auth = secret.auth(),                    # get keys for this specific node
                           dr = 12 - pycom.nvs_get('sf_h'))         # always join using maximum power
            self._fcnt = 0                                          # default LoRa frame count
        else:
            self._fcnt = pycom.nvs_get('fcnt')                      # restore LoRa frame count from nvRAM

        if sf:
            self._dr = 12 - sf
        else:
            self._dr = 12 - pycom.nvs_get('sf_l')                   # default SF (low)
            if self._fcnt % pycom.nvs_get('adr') == 0:
                self._dr = 12 - pycom.nvs_get('sf_h')               # every adr'th message, send on high SF

        if fport:
            self._fport = 4
        else:
            self._fport = 1                                         # default LoRa packet decoding type 1 (no GPS)

        self._frame = bytes([])
    
    @property
    def fcnt(self):
        return self._fcnt
    
    @property
    def sf(self):
        return 12 - self._dr
    
    @sf.setter
    def sf(self, sfactor):
        self._dr = 12 - sfactor
    
    @property
    def dr(self):
        return self._dr
    
    @property
    def fport(self):
        return self._fport
    
    @fport.setter
    def fport(self, port):
        self._fport = port

    @property
    def frame(self):
        return self._frame
    
    @property
    def has_joined(self):
        return self.lora.has_joined()

    @staticmethod
    def pack(name, values):
        numbytes, offset, precision  = _configs[name]
        value = round((values + offset) / precision)                # add offset, then round to precision
        value = max(0, min(value, 2**(8*numbytes) - 1))             # stay in range 0 .. int.max_size - 1
        out = value.to_bytes(numbytes, 'big')                       # pack to bytes
        return out

    def make_frame(self, odict):
        for key, values in odict.items():
            self._frame += LoRaWAN.pack(key, values)

        return len(self._frame)

    def send_frame(self, join_flag = False):
        if not self._frame:
            raise AttributeError("empty frame")
        
        if join_flag:
            while not self.has_joined:
                time.sleep(1)
        
        # send LoRa message and store LoRa context + frame count in NVRAM
        sckt = socket.socket(socket.AF_LORA, socket.SOCK_RAW)       # create a LoRa socket (blocking by default)
        sckt.setsockopt(socket.SOL_LORA, socket.SO_DR, self._dr)    # set the LoRaWAN data rate
        sckt.bind(self._fport)                                      # set the type of message used for decoding the packet
        sckt.send(self._frame)
        sckt.close()

        self.lora.nvram_save()
        pycom.nvs_set('fcnt', self._fcnt + 1)

        self._frame = bytes([])