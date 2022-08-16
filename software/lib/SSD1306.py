# Adaptation of CircuitPython library by Steven Boonstoppel
from micropython import const
import framebuf

# register definitions
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_IREF_SELECT = const(0xAD)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)

class SSD1306:
    def __init__(self, width, height, i2c, address = 0x3C):
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(((height // 8) * width) + 1)
        self.buffer[0] = 0x40  # Set first byte of data buffer to Co=0, D/C=1
        self.framebuf = framebuf.FrameBuffer1(memoryview(self.buffer)[1:], width, height)
        
        self.width = width
        self.height = height
        self.pages = self.height // 8
        self._power = False
        self.poweron()
        self.init_display()

    def write_cmd(self, cmd) -> None:
        buffer = bytearray(2)
        buffer[0] = 0x80
        buffer[1] = cmd
        self.i2c.writeto(self.address, buffer)

    def write_framebuf(self) -> None:
        self.i2c.writeto(self.address, self.buffer)

    def init_display(self) -> None:
        for cmd in (
            SET_DISP | 0x00,  # off
            # address setting
            SET_MEM_ADDR, 0x00,  # Horizontal Addressing Mode
            # resolution and layout
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,  # column addr 127 mapped to SEG0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,  # scan from COM[N] to COM0
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.width > 2 * self.height else 0x12,
            # timing and driving scheme
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0xF1,
            SET_VCOM_DESEL, 0x30,  # 0.83*Vcc
            # display
            SET_CONTRAST, 0xFF,  # maximum
            SET_ENTIRE_ON,  # output follows RAM contents
            SET_NORM_INV,  # not inverted
            SET_IREF_SELECT, 0x30,  # enable internal IREF during display on
            # charge pump
            SET_CHARGE_PUMP, 0x14,
            SET_DISP | 0x01):  # display on
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweron(self) -> None:
        "Reset device and turn on the display."
        self.write_cmd(SET_DISP | 0x01)
        self._power = True

    def poweroff(self) -> None:
        """Turn off the display (nothing visible)"""
        self.write_cmd(SET_DISP | 0x00)
        self._power = False

    @property
    def power(self) -> bool:
        """True if the display is currently powered on, otherwise False"""
        return self._power

    def contrast(self, contrast: int) -> None:
        """Adjust the contrast"""
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def show(self) -> None:
        xpos0 = 0
        xpos1 = self.width - 1
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(xpos0)
        self.write_cmd(xpos1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_framebuf()
    
    def fill(self, col):
        self.framebuf.fill(col)

    def text(self, string, x, y, col=1):
        self.framebuf.text(string, x, y, col)