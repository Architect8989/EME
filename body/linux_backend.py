# body/linux_backend.py

from execution.backend_contract import BackendBase, Result, ErrorCode
import pyautogui
import hashlib
import io
import time


class LinuxBackend(BackendBase):
    def _impl_screenshot(self) -> dict:
        img = pyautogui.screenshot()

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        sha = hashlib.sha256(raw).hexdigest()

        # storage_key is only an identifier — caller persists it elsewhere
        storage_key = f"frame-{int(time.time_ns())}-{sha}"

        return {
            "width": img.width,
            "height": img.height,
            "format": "png",
            "sha256": sha,
            "storage_key": storage_key,
        }

    def _impl_move_mouse(self, x: int, y: int) -> dict:
        screen_w, screen_h = pyautogui.size()

        clamped_x = max(0, min(x, screen_w - 1))
        clamped_y = max(0, min(y, screen_h - 1))

        pyautogui.moveTo(clamped_x, clamped_y, duration=0)

        pos_x, pos_y = pyautogui.position()

        return {
            "requested": (x, y),
            "final": (pos_x, pos_y),
            "clamped": (clamped_x != x) or (clamped_y != y),
        }

    def _impl_click(self, button: str, count: int) -> dict:
        pyautogui.click(button=button, clicks=count, interval=0)
        return {"button": button, "count": count}

    def _impl_type_text(self, text: str) -> dict:
        pyautogui.typewrite(text, interval=0)
        return {"length": len(text)}
