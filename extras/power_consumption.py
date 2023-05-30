import matplotlib.pyplot as plt
import numpy as np

data = np.genfromtxt("extras\power_consumption.csv", delimiter = ',')

plt.figure(figsize = (8, 5))
plt.plot(np.linspace(0, 44, len(data[:, 2])), data[:, 2])
plt.title("Stroomgebruik tijdens meting - FW v2.7.0")
plt.xlabel("$tijd$ (s)")
plt.ylabel("$stroomsterkte$ (mA)")
plt.xlim(0, 44)
plt.ylim(bottom = 0)
plt.grid()
plt.axvspan( 0,  3, 0, 200, alpha = 0.15, color = 'red',        label = 'programma\nstarten')
plt.axvspan( 3, 28, 0, 200, alpha = 0.15, color = 'green',      label = 'sensoren\nmeten')
plt.axvspan(28, 32, 0, 200, alpha = 0.15, color = 'dodgerblue', label = 'LoRa\ntransmissie')
plt.axvspan(32, 37, 0, 200, alpha = 0.15, color = 'yellow',     label = 'waarden\nweergeven')
plt.axvspan(37, 44, 0, 200, alpha = 0.15, color = 'gray',       label = 'diepe\nslaap')
plt.legend(loc = 'upper right')
plt.xticks([0, 3, 5, 10, 15, 20, 25, 28, 32, 35, 37, 40, 44])
plt.savefig("extras\Stroomgebruik_MJLO_v2_7_0.png", dpi=1200)
plt.savefig("extras\Stroomgebruik_MJLO_v2_7_0.svg")
plt.savefig("extras\Stroomgebruik_MJLO_v2_7_0.pdf")
plt.show(block = True)