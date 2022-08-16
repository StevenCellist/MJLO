# LoRa config
LORA_MODE = 'ABP'
NODE = 18

SF_LOW = 10         # lower Spreading Factor for Blind ADR
SF_HIGH = 12        # upper Spreading Factor for Blind ADR
FRACTION = 3        # every FRACTION'th message is sent on SF_HIGH, others on SF_LOW

# time config
T_INTERVAL = 600    # measure every ... seconds
T_DISPLAY = 10      # time to show a page of values on the display
T_WAKE = 28         # time for CO2 and PM sensor to wake and stabilize

# debug config
DEBUG = False
T_DEBUG = 60        # measure every ... seconds (debug only)