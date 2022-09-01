"""
Reading format. See http://cl.ly/ekot

0 Header   '\xaa'
1 Command  '\xc0'
2 DATA1    PM2.5 Low byte
3 DATA2    PM2.5 High byte
4 DATA3    PM10 Low byte
5 DATA4    PM10 High byte
6 DATA5    ID byte 1
7 DATA6    ID byte 2
8 Checksum Low byte of sum of DATA bytes
9 Tail     '\xab'
"""

import struct

_SDS011_CMDS = {'SET': b'\x01',
        'GET': b'\x00',
        'QUERY': b'\x04',
        'REPORTING_MODE': b'\x02',
        'DUTYCYCLE': b'\x08',
        'SLEEPWAKE': b'\x06'}

class SDS011:
    def __init__(self, uart):
        self._uart = uart
        self._pm25 = 0.0
        self._pm10 = 0.0

        self.set_reporting_mode_query()

    @property
    def pm25(self):
        """Return the PM2.5 concentration, in µg/m^3."""
        return self._pm25

    @property
    def pm10(self):
        """Return the PM10 concentration, in µg/m^3."""
        return self._pm10

    def make_command(self, cmd, mode, param):
        header = b'\xaa\xb4'
        padding = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff'
        checksum = chr(( ord(cmd) + ord(mode) + ord(param) + 255 + 255) % 256)
        checksum = bytes(checksum, 'utf8')
        tail = b'\xab'
        return header + cmd + mode + param + padding + checksum + tail

    def get_response(self, command_ID):
        # try for 120 bytes (0.2) second to get a response from sensor (typical response time 12~33 bytes)
        for _ in range(120):
            try:
                header = self._uart.read(1)
                if header == b'\xaa':
                    command = self._uart.read(1)
                    if command == command_ID:
                        packet = self._uart.read(8)
                        if packet != None:
                            if command_ID == b'\xc0':
                                self.process_measurement(packet)
                            return True
                    else:
                        pass
            except Exception as e:
                pass
        return False

    def wake(self):
        """Sends wake command to sds011 (starts its fan and laser)."""
        cmd = self.make_command(_SDS011_CMDS['SLEEPWAKE'],
                _SDS011_CMDS['SET'], chr(1))
        self._uart.write(cmd)
        return self.get_response(b'\xc5')

    def sleep(self):
        """Sends sleep command to sds011 (stops its fan and laser)."""
        cmd = self.make_command(_SDS011_CMDS['SLEEPWAKE'],
                _SDS011_CMDS['SET'], chr(0))
        self._uart.write(cmd)
        return self.get_response(b'\xc5')

    def set_reporting_mode_query(self):
        cmd = self.make_command(_SDS011_CMDS['REPORTING_MODE'],
                _SDS011_CMDS['SET'], chr(1))
        self._uart.write(cmd)
        return self.get_response(b'\xc5')

    def query(self):
        cmd = self.make_command(_SDS011_CMDS['QUERY'], chr(0), chr(0))
        self._uart.write(cmd)

    def process_measurement(self, packet):
        try:
            *data, _, _ = struct.unpack('<HHBBBs', packet)
            self._pm25 = data[0]/10.0
            self._pm10 = data[1]/10.0
        except Exception as e:
            pass

    def read(self):
        self.query()                        # query measurement
        return self.get_response(b'\xc0')   # try to get values from the response
