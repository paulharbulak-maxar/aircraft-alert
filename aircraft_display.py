import time

from samplebase import SampleBase
from rgbmatrix import graphics

white = graphics.Color(128, 128, 128)
red = graphics.Color(200, 0, 0)
orange = graphics.Color(200, 100, 0)
yellow = graphics.Color(200, 200, 0)
green = graphics.Color(0, 200, 0)
blue = graphics.Color(0, 0, 255)
purple = graphics.Color(100, 0, 200)


class AircraftDisplay(SampleBase):
    def __init__(self, display_pipe, *args, **kwargs):
        super(AircraftDisplay, self).__init__(*args, **kwargs)
        self.display_pipe = display_pipe

    def run(self):
        canvas = self.matrix.CreateFrameCanvas()
        # canvas = self.matrix
        font = graphics.Font()
        font.LoadFont(f"./fonts/5x8.bdf")
        line_numbers = [7, 15, 23, 31]
        # font_size = "5x8" if self.line_4 else "6x12"
        # font.LoadFont(f"./fonts/{font_size}.bdf")
        # lines = [7, 15, 23, 31] if self.line_4 else [10, 20, 30]

        # TODO: Fix colormap for different lines instead of just using index of line number
        colors = [blue, green, red, yellow]

        for msg in iter(self.display_pipe.recv, "sentinel"):
            # print("Receiving message...")
            if len(msg) == 5:
                callsign, model, dist, schd_from, schd_to = msg
            elif len(msg) == 3:
                callsign, model, dist = msg
            else:
                raise ValueError("Unexpected number of items in response")
                
            lines = [callsign, model, f"{dist}mi"]
            # print(callsign, model, dist)
            if schd_from and schd_to:
                route = f"{schd_from} -> {schd_to}"
                lines.append(route)

            canvas.Clear()

            for i, line in enumerate(lines):
                graphics.DrawText(canvas, font, 0, line_numbers[i], colors[i], str(line))

            # for b in range(255):
            #     blue = graphics.Color(0, 0, b)
            #     graphics.DrawText(canvas, font, 0, lines[0], blue, str(self.line_1))
            #     time.sleep(0.001)

            # for b in range(64):
            #     canvas.Clear()
            #     blue = graphics.Color(0, 0, 255)
            #     graphics.DrawText(canvas, font, 64 - b, lines[0], blue, str(self.line_1))
            #     time.sleep(0.01)

            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(1)
