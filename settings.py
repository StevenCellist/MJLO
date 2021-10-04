# Here we store all settings, credentials and constants.

#Pycom import for LoRa constants.
from network import LoRa

# Color codes in hexadecimal. Used for setting LED colour.
COLOR = dict(
    GREEN       = 0x007f00,
    LIGHT_GREEN = 0x00ff00,
    RED         = 0xff0000,
    DARK_RED    = 0x140000,
    DARK_ORANGE = 0x2E2000,
    DARK_GREEN  = 0x001400,
    DARK_BLUE   = 0x000014,
    AMBER       = 0xB7790E,
    DARK_AMBER  = 0x79520F,
    LILA        = 0x590E6C,
    OFF         = 0x000000
)

# Add all the connected pin numbers here.
# ...

# LoRa config info.
LORA_MODE = LoRa.LORAWAN
LORA_REGION = LoRa.EU868
LORA_ACTIVATION = LoRa.OTAA
APP_EUI = '30AEA459134C0000'
APP_KEY = '38C9AD4E8B69241FE50AB179932CAE1F'
MEASURE_INTERVAL = 30
DEBUG_MODE = True
