## Here we store settings, credentials and constants.

# LoRa config info
APP_EUI = '30AEA47870B40000'
APP_KEY = '93F032DE681792632F0B928B555DAAB8'
LORA_SF = 12             # LoRa Spreading Factor (7 to 12)
LORA_DR = 12 - LORA_SF  # Data Rate complement of Spreading Factor (counted inversely from 0 to 5)

MEASURE_INTERVAL = 60  # measure every ... seconds
BOOT_TIME = 3           # time in seconds (approx) it takes to start SDS011 from poweron
WAKE_TIME = 32          # time in seconds that the SDS011 and MQ135 need to stabilize
PEAK_TIME = 6           # time in seconds to wait after starting voltage regulator
DISPLAY_TIME = 6        # time in seconds to display values on the internal display
SLEEP_TIME = MEASURE_INTERVAL - BOOT_TIME - WAKE_TIME

DEBUG_MODE = False