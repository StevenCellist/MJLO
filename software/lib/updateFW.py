import machine
import pycom
import os
import secret

BLOCKSIZE = const(4096)
APPIMG = secret.filename                        # firmware filename

def check_update(display):
	display.fill(0)
	try:
		sd = machine.SD()                       # initialize SD card
		display.text("Found SD card", 1, 1)
		display.show()
	except:
		display.text("No SD card", 1, 1)
		display.show()
		return False

	try:
		os.mount(sd, '/sd')                     # mount SD card
	except:
		display.text("Could not mount", 1, 11)
		display.show()
		return False

	try:
		with open(APPIMG, "rb") as f:           # open new firmware file
			display.text("New firmware!", 1, 11)
			filesize = int(os.stat(APPIMG)[6] / 1000)   # calculate filesize in kB
			display.text("Size: " + str(filesize) + " kB", 1, 21)
			display.show()
			buffer = bytearray(BLOCKSIZE)
			mv = memoryview(buffer)
			size = 0
			last_prog = 0
			pycom.ota_start()                   # start Over The Air update
			while True:
				chunk = f.readinto(buffer)      # read chunk
				if chunk > 0:
					pycom.ota_write(mv[:chunk])
					size += chunk
					prog = int(size / filesize / 10)    # calculate progress (in %)
					if prog != last_prog:               # if % has changed, update display
						display.text("Progress: {:>3}%".format(last_prog), 1, 31, col = 0)
						display.text("Progress: {:>3}%".format(prog), 1, 31)
						display.show()
						last_prog = prog                # update old value
				else:
					break
			
			pycom.ota_finish()                  # finish Over The Air update
		
	except:
		display.text("Update failed", 1, 31)
		display.show()
    
	try:
		os.stat('/sd/upgrade.py')
		display.text("Applying upgrade", 1, 41)
		__import__('/sd/upgrade')
	except:
		display.text("No upgrade found", 1, 41)
	
	os.umount('/sd')
	sd.deinit()
		
	display.text("Rebooting...", 1, 51)
	display.show()

	return True