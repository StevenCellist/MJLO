import machine
import pycom
import os
import secret

BLOCKSIZE = const(4096)
file_FW = secret.file_firmware               	# firmware filename
file_UG = secret.file_upgrade					# upgrade filename

def check_update(display):
	display.fill(0)
	
	# initialize SD card
	try:
		sd = machine.SD()
		display.text("Found SD card", 1, 1)
		display.show()
	except:
		display.text("No SD card", 1, 1)
		display.show()
		return False

	# mount SD card
	try:
		os.mount(sd, '/sd')
	except:
		display.text("Could not mount", 1, 11)
		display.show()
		return False

	# perform injection code (usually an upgrade) if an upgrade file is present
	try:
		os.stat(file_UG)
		display.text("Applying upgrade", 1, 11)
		__import__(file_UG[:-3])
	except:
		display.text("No upgrade found", 1, 11)

	# update firmware if a firmware file is present on the SD card
	try:
		with open(file_FW, "rb") as f:        		# open new firmware file
			filesize = os.stat(file_FW)[6]   		# get filesize in bytes
			if filesize == pycom.nvs_get('fwsize'):	# check if firmware size is identical (approx. zero chance)
				display.text("Same firmware!", 1, 21)
				display.show()
			else:
				pycom.nvs_set('fwsize', filesize)
				display.text("New firmware!", 1, 21)
				display.text("Size: " + str(int(filesize / 1000)) + " kB", 1, 31)
				display.show()
				buffer = bytearray(BLOCKSIZE)		# buffer of 4096 bytes
				mv = memoryview(buffer)
				size = 0							# copied bytes counter
				last_prog = 0						# keep track of progress
				pycom.ota_start()                   # start Over The Air update
				while True:
					chunk = f.readinto(buffer)      # read chunk
					if chunk > 0:
						pycom.ota_write(mv[:chunk])
						size += chunk
						prog = int(size / filesize / 10)    # calculate progress (in %)
						if prog != last_prog:               # if % has changed, update display
							display.text("Progress: {:>3}%".format(last_prog), 1, 41, col = 0)	# de-fill previous progress
							display.text("Progress: {:>3}%".format(prog), 1, 41)				# write current progress
							display.show()
							last_prog = prog                # update old value
					else:
						break
				pycom.ota_finish()                  # finish Over The Air update
	except:
		display.text("Update failed", 1, 31)
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

	return True