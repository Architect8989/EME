from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw
import time


@dataclass
class MoveMouse:
    id: str = "motion.simulated_pointer"

    def run(self):
        # simulate a visual change inside snapshots folder
        # this makes deltas spike without lying about OS control
        path = Path("snapshots/sim_marker.png")

        img = Image.new("RGB", (200, 80), "black")
        draw = ImageDraw.Draw(img)
        draw.rectangle((20, 20, 180, 60), outline="white", width=3)
        img.save(path)

        time.sleep(0.05)
