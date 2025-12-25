from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw


@dataclass
class MoveMouse:
    id: str = "motion.simulated_pointer"

    def run(self):
        path = Path("snapshots/sim_marker.png")

        img = Image.new("RGB", (300, 120), "black")
        draw = ImageDraw.Draw(img)
        draw.rectangle((30, 30, 270, 90), outline="white", width=5)
        img.save(path)
