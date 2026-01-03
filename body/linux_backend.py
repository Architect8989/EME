from typing import Tuple

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase
from execution.action_executor import ExecutorToken


MAX_PX_PER_SEC = 100
MOVE_STEP_PX = 1


class LinuxBackend(BackendBase):
    def __init__(self, token: ExecutorToken):
        if not isinstance(token, ExecutorToken):
            Poison.trigger("backend instantiated without executor token")

        super().__init__()
        Poison.assert_clean()

        # ---- lazy OS / native imports (FIX 2) ----
        import subprocess
        import numpy as np
        from mss import mss

        self._subprocess = subprocess
        self._np = np
        self._mss_lib = mss

        self._token = token
        self._mss = self._mss_lib()
        self._screen = self._primary_monitor()

    def _primary_monitor(self):
        Poison.assert_clean()
        monitors = self._mss.monitors
        if not monitors or len(monitors) < 2:
            Poison.trigger("primary monitor not found")
        return monitors[1]

    def _run(self, cmd):
        Poison.assert_clean()
        p = self._subprocess.run(
            cmd,
            stdout=self._subprocess.PIPE,
            stderr=self._subprocess.PIPE,
            text=True,
        )
        if p.returncode != 0:
            Poison.trigger(f"command failed: {p.stderr.strip()}")
        return p.stdout.strip()

    def _capture(self):
        Poison.assert_clean()
        try:
            frame = self._np.array(self._mss.grab(self._screen))
        except Exception as e:
            Poison.trigger(f"screen capture failed: {e}")

        if frame.size == 0:
            Poison.trigger("empty screen frame captured")

        return frame

    def _cursor(self) -> Tuple[int, int]:
        Poison.assert_clean()
        out = self._run(["xdotool", "getmouselocation", "--shell"])
        vals = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = int(v)

        if "X" not in vals or "Y" not in vals:
            Poison.trigger("cursor position incomplete")

        return vals["X"], vals["Y"]

    def _clamp(self, x: int, y: int) -> Tuple[int, int]:
        Poison.assert_clean()
        w = self._screen["width"] - 1
        h = self._screen["height"] - 1
        return max(0, min(x, w)), max(0, min(y, h))

    def _impl_screenshot(self) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        frame = self._capture()

        return {
            "width": frame.shape[1],
            "height": frame.shape[0],
            "format": "raw",
            "mean_delta": 0.0,
        }

    def _impl_move_mouse(self, x: int, y: int) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.EXECUTE)

        cx, cy = self._cursor()
        tx, ty = self._clamp(x, y)

        dx = tx - cx
        dy = ty - cy

        if abs(dx) > MOVE_STEP_PX or abs(dy) > MOVE_STEP_PX:
            Poison.trigger("unsafe mouse movement requested")

        before = self._capture()
        self._run(["xdotool", "mousemove", str(tx), str(ty)])
        after = self._capture()

        delta = float(
            self._np.mean(
                self._np.abs(before.astype(self._np.int16) - after.astype(self._np.int16))
            )
        )

        if delta <= 0:
            Poison.trigger("mouse movement produced no visual delta")

        return {
            "from": (cx, cy),
            "to": (tx, ty),
            "delta": delta,
        }

    def _impl_click(self, button: str, count: int) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.EXECUTE)
        Poison.trigger("click action not implemented")

    def _impl_type_text(self, text: str) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.EXECUTE)
        Poison.trigger("type action not implemented")
