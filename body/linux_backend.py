from typing import Tuple

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase
from execution.action_executor import ExecutorToken


MOVE_STEP_PX = 1


class LinuxBackend(BackendBase):
    """
    Linux X11 backend.

    Mechanical guarantees:
    - No OS interaction at import time
    - No OS interaction in __init__
    - Executor token bound exactly once
    - All OS effects occur only inside _impl_* methods
    """

    __slots__ = ("_np", "_mss_lib", "_subprocess")

    def __init__(self, token: ExecutorToken):
        if not isinstance(token, ExecutorToken):
            Poison.trigger("backend instantiated without executor token")

        super().__init__()
        self._bind_executor(token)

        self._np = None
        self._mss_lib = None
        self._subprocess = None

    # ─────────────────────────────────────────────
    # Lazy OS helpers (executor-gated via callers)
    # ─────────────────────────────────────────────

    def _ensure_libs(self) -> None:
        if self._np is None:
            try:
                import numpy as np
                from mss import mss
                import subprocess
            except BaseException as e:
                Poison.trigger(f"backend dependency import failed: {repr(e)}")

            self._np = np
            self._mss_lib = mss
            self._subprocess = subprocess

    def _primary_monitor(self):
        self._ensure_libs()
        with self._mss_lib() as sct:
            monitors = sct.monitors
            if not monitors or len(monitors) < 2:
                Poison.trigger("primary monitor not found")
            return monitors[1]

    def _grab(self):
        self._ensure_libs()
        mon = self._primary_monitor()
        with self._mss_lib() as sct:
            img = sct.grab(mon)
            data = img.bgra if hasattr(img, "bgra") else img.raw
            if len(data) != img.width * img.height * 4:
                Poison.trigger("screen buffer size mismatch")
            return data, img.width, img.height

    def _run(self, cmd):
        self._ensure_libs()
        p = self._subprocess.run(
            cmd,
            stdout=self._subprocess.PIPE,
            stderr=self._subprocess.PIPE,
            text=True,
        )
        if p.returncode != 0:
            Poison.trigger(f"command failed: {p.stderr.strip()}")
        return p.stdout.strip()

    def _cursor(self) -> Tuple[int, int]:
        out = self._run(["xdotool", "getmouselocation", "--shell"])
        vals = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = int(v)
        if "X" not in vals or "Y" not in vals:
            Poison.trigger("cursor position unavailable")
        return vals["X"], vals["Y"]

    def _clamp(self, x: int, y: int, w: int, h: int) -> Tuple[int, int]:
        return max(0, min(x, w - 1)), max(0, min(y, h - 1))

    # ─────────────────────────────────────────────
    # BackendBase implementations
    # ─────────────────────────────────────────────

    def _impl_screenshot(self) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        buffer, width, height = self._grab()
        cx, cy = self._cursor()

        return {
            "buffer": buffer,
            "width": width,
            "height": height,
            "cursor": (cx, cy),
            "pixel_format": "BGRA",
        }

    def _impl_move_mouse(self, x: int, y: int) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.EXECUTE)

        buffer, width, height = self._grab()
        cx, cy = self._cursor()
        tx, ty = self._clamp(x, y, width, height)

        dx = tx - cx
        dy = ty - cy

        if abs(dx) > MOVE_STEP_PX or abs(dy) > MOVE_STEP_PX:
            Poison.trigger("unsafe mouse movement requested")

        self._run(["xdotool", "mousemove", str(tx), str(ty)])

        return {
            "from": (cx, cy),
            "to": (tx, ty),
        }

    def _impl_click(self, button: str, count: int) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.EXECUTE)
        Poison.trigger("click not implemented")

    def _impl_type_text(self, text: str) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.EXECUTE)
        Poison.trigger("type_text not implemented")
