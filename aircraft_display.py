import time

from samplebase import SampleBase
from rgbmatrix import graphics

class AircraftDisplay(SampleBase):
    def __init__(self, line_1, line_2=None, line_3=None, line_4=None, *args, **kwargs):
        super(AircraftDisplay, self).__init__(*args, **kwargs)
        self.line_1 = line_1
        self.line_2 = line_2
        self.line_3 = line_3
        self.line_4 = line_4

    def run(self):
        canvas = self.matrix
        font = graphics.Font()
        font_size = "5x8" if self.line_4 else "6x12"
        font.LoadFont(f"./fonts/{font_size}.bdf")
        lines = [7, 15, 23, 31] if self.line_4 else [10, 20, 30]

        white = graphics.Color(128, 128, 128)
        red = graphics.Color(200, 0, 0)
        orange = graphics.Color(200, 100, 0)
        yellow = graphics.Color(200, 200, 0)
        green = graphics.Color(0, 200, 0)
        blue = graphics.Color(0, 0, 255)
        purple = graphics.Color(100, 0, 200)

        graphics.DrawText(canvas, font, 0, lines[0], blue, str(self.line_1))
        # for b in range(255):
        #     blue = graphics.Color(0, 0, b)
        #     graphics.DrawText(canvas, font, 0, lines[0], blue, str(self.line_1))
        #     time.sleep(0.001)

        # for b in range(64):
        #     canvas.Clear()
        #     blue = graphics.Color(0, 0, 255)
        #     graphics.DrawText(canvas, font, 64 - b, lines[0], blue, str(self.line_1))
        #     time.sleep(0.01)

        if self.line_2:
            graphics.DrawText(canvas, font, 0, lines[1], green, str(self.line_2))
            # for b in range(200):
            #     green = graphics.Color(0, b, 0) 
            #     graphics.DrawText(canvas, font, 0, lines[1], green, str(self.line_2))
            #     time.sleep(0.001)

        if self.line_3:
            graphics.DrawText(canvas, font, 0, lines[2], red, str(self.line_3))
            # for b in range(200):
            #     red = graphics.Color(b, 0, 0) 
            #     graphics.DrawText(canvas, font, 0, lines[2], red, str(self.line_3))
            #     time.sleep(0.001)

        if self.line_4:
            graphics.DrawText(canvas, font, 0, lines[3], yellow, str(self.line_4))
            # for b in range(200):
            #     yellow = graphics.Color(b, b, 0)
            #     graphics.DrawText(canvas, font, 0, lines[3], yellow, str(self.line_4))
            #     time.sleep(0.001)

        time.sleep(1)

