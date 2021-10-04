import pycom
from network import Bluetooth

# Here we disable things we don't need.
# Otherwise it will draw power for no reason.
pycom.heartbeat(False)
pycom.heartbeat_on_boot(False)
pycom.wifi_on_boot(False)
bluetooth = Bluetooth()
bluetooth.deinit()
