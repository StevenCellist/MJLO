import pycom
import settings
import os
pycom.nvs_set('node', settings.NODE)
pycom.nvs_set('lora', 1)
pycom.nvs_set('sf_h', 12)
pycom.nvs_set('sf_l', 10)
pycom.nvs_set('adr', 3)
pycom.nvs_set('t_int', 600)
pycom.nvs_set('t_wake', 25)
pycom.nvs_set('t_disp', 8)
pycom.nvs_set('debug', 0)
pycom.nvs_set('t_debug', 45)
os.mkfs('/flash')