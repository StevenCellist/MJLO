## Here we store settings, credentials and constants.

# LoRa config info.
APP_EUI = '30AEA459134C0000'
APP_KEY = '38C9AD4E8B69241FE50AB179932CAE1F'
MEASURE_INTERVAL = 60
BOOT_TIME = 8           # approximate time it takes to start main.py from poweron
WAKE_TIME = 32
DISPLAY_TIME = 6
SLEEP_TIME = MEASURE_INTERVAL - BOOT_TIME - WAKE_TIME
DEBUG_MODE = True