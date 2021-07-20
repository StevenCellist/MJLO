import display

class Display:
    def __init__(self, bus_connection):
        self.display = display.SSD1306_I2C(128, 32, bus_connection)

    # TODO: find out how many pixels are in a line and make a mechanism so you can specify on which line number the text should go.
    def text(self, text, line=0):
        self.display.text(text, 1, 1, 1)
        self.display.show()


    