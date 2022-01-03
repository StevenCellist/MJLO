# Meet je leefomgeving (software-repository)
In deze repository vindt u de meest recente software die op de meetkastjes gebruikt wordt.  
Het prototype hiervan is aangeleverd door ICR3ATE en vervolgens volledig verder ontwikkeld door Steven Boonstoppel.  

## Algemene opzet
De constructie van de software is als volgt:  
Bij het opstarten wordt <kbd>boot.py</kbd> uitgevoerd. Als allereerste wordt daar de LED en WiFi onderdrukt. Vervolgens starten direct de SDS011 en MQ135 die beiden 30 seconden tijd nodig hebben om hun metingen te stabiliseren. Omdat UART naar de SDS011 op minder dan de officiële 5V traag start, wordt er gewacht tot er een respons is gekomen.  
Daarna wordt <kbd>main.py</kbd> uitgevoerd. Hierin start het kastje met het initialiseren van het display en vervolgens wordt er gepoogd de LoRa informatie te herstellen vanuit RAM. Is er niets aanwezig in RAM (en is LoRa dus nog niet gejoind), dan joint hij het netwerk; anders kan hij direct door vanuit de deepsleep reset. Daarna wordt gezocht of er vanuit de vorige sessie sensorwaarden zijn opgeslagen in RAM. Als dat het geval is, worden deze nu verzonden over LoRa en op het display getoond. Vervolgens worden alle anderen sensoren gestart en worden hun relevante waarden gemeten, waarna ze weer in slaapstand gezet worden. Daarna wordt de LoRa informatie weer opgeslagen in RAM en in lightsleep gewacht tot de 30 seconden opwarmtijd voorbij zijn (er zijn circa 15 seconden resterend, afhankelijk van de instellingen). Dan worden de laatste twee sensoren gemeten en alle waarden opgeslagen in RAM, om vervolgens in deepsleep te gaan. De waarden van deze sessie worden pas tijdens de volgende verzonden.  
Wordt tijdens deepsleep op de knop gedrukt, dan waakt het kastje op en wordt de GPS-module geactiveerd om de locatie vast te zetten. Aangezien dit slechts bij verplaatsing hoeft te gebeuren, wordt dit ook maar eenmalig uitgevoerd. Zodra een GPS-fix is gevonden, wordt de module weer gedeactiveerd.

## Hardware
Microcontroller: LoPy4 op Expansion Board v3.1
Accu: Keeppower Li-ion 26650 5200 mAh
SSD1306 OLED display
VEML6070 UV sensor
TSL2591 Lux sensor
BME680 Temperatuur/luchtvochtigheid/luchtdruk sensor
MAX4466 Volume sensor
MQ135 CO2 sensor
SDS011 Fijnstof sensor
Neo-6M GPS module

## LoPy4
[Pinout](https://docs.pycom.io/datasheets/development/lopy4/)

## Expansion Board v3.1
[Specs: definitely a lie](https://docs.pycom.io/datasheets/expansionboards/expansion3/)
[Specs: much better](https://gitlab.com/rcolistete/micropython-samples/-/blob/master/Pycom/Using_Expansion_Board_en.md)
[Voltage divider: mess](https://community.hiveeyes.org/t/batterieuberwachung-voltage-divider-und-attenuation-fur-micropython-firmware/2128/46?page=2)