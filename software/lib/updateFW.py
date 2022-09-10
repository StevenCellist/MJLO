import machine
import pycom
import os
import secret

BLOCKSIZE = const(4096)

def check_SD(display):
	display.fill(0)

	# initialize SD card
	try:
		sd = machine.SD()
		os.mount(sd, '/sd')
		display.text("Mounted SD card", 1, 1)
		display.show()
	except:
		display.text("No SD card", 1, 1)
		display.show()
		return False

	# perform injection code (usually an upgrade)
	ret = do_upgrade()
	display.text(ret, 1, 11)
	display.show()

	ret, size = check_firmware()
	display.text(ret, 1, 21)
	display.show()

	ret = do_firmware(display, size)
	display.text(ret, 1, 41)
	display.show()

	# prepare for safe SD card removal
	os.umount('/sd')
	sd.deinit()
	display.text("Remove SD card!", 1, 51)
	display.show()
	machine.sleep(5000)
	display.text("Remove SD card!", 1, 51, col = 0)	# de-fill previous line
	display.text("Rebooting...", 1, 51)				# write current line
	display.show()
	machine.sleep(1000)
	
	return True

def do_upgrade():
	# check if an upgrade file exists
	try:
		os.stat(secret.file_upgrade)
	except:
		return "No upgrade file"

	# execute upgrade file
	try:
		__import__(secret.file_upgrade[:-3])
	except:
		return "Upgrade failed"

	return "Upgrade done"

def check_firmware():
	# check if a firmware file exists
	try:
		filesize = os.stat(secret.file_firmware)[6]	# get filesize in bytes
	except:
		return ("No firmware", 0)

	# check if firmware file has identical size to last update (approx. zero chance randomly)
	if filesize == pycom.nvs_get('fwsize'):
		return ("Same firmware", 0)

	return ("New firmware", filesize)

def do_firmware(display, filesize):
	last_prog = 0
	string = "{:>4}/{} ({:>3}%)".format(size, filesize, last_prog)
	display.text(string, 1, 31)
	display.show()
	try:
		with open(secret.file_firmware, "rb") as f:	# open new firmware file
			buffer = bytearray(BLOCKSIZE)			# buffer of 4096 bytes
			mv = memoryview(buffer)
			size = 0								# copied bytes counter
			pycom.ota_start()                   	# start Over The Air update
			chunk = f.readinto(buffer)
			while chunk > 0:
				pycom.ota_write(mv[:chunk])
				size += chunk
				prog = int(size / filesize * 100) 	# calculate progress (in %)
				if prog != last_prog:               # if % has changed, update display
					display.text(string, 1, 31, col = 0)	# de-fill previous string
					string = "{:>4}/{} ({:>3}%)".format(size, filesize, prog)
					display.text(string, 1, 31)		# write current string
					display.show()
					last_prog = prog                # update old value
				chunk = f.readinto(buffer)
			pycom.ota_finish()                  	# finish Over The Air update
			pycom.nvs_set('fwsize', filesize)		# save firmware filesize in NVRAM
		return "Update done"
	except:
		return "Update failed"