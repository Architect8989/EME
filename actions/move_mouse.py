from dataclasses import dataclass


@dataclass
class MoveMouse:
    id: str = "motion.move_pointer"
    x: int = 50
    y: int = 50

    def run(self):
        import pyautogui
        pyautogui.moveTo(self.x, self.y, duration=0.05)
