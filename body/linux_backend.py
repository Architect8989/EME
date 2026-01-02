import time
import subprocess
from typing import Tuple

import mss
import numpy as np

from core.mode_gate import ModeGate, Mode
from execution.backend_contract import BackendBase, Result, ErrorCode


MAX_PX_PER_SEC = 100
MOVE_STEP_PX = 1
CAPTURE_RETRY_LIMIT = 2


class LinuxBackend(BackendBase):
    def __init__(self):
        self._mss = mss.mss()
        self._screen = self._primary_monitor()

    def _primary_monitor(self):
        monitors = self._mss.monitors
        if not monitors or len(monitors) < 2:
            raise RuntimeError("No primary monitor")
        return monitors[1]

    def _run(self, cmd):
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if p.returncode != 0:
            raise RuntimeError(p.stderr.strip())
        return p.stdout.strip()

    def _capture(self) -> np.ndarray:
        for _ in range(CAPTURE_RETRY_LIMIT):
            try:
                frame = np.array(self._mss.grab(self._screen))
                if frame.size == 0:
                    raise RuntimeError("Empty frame")
                return frame
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("Screen capture unstable")

    def _cursor(self) -> Tuple[int, int]:
        out = self._run(["xdotool", "getmouselocation", "--shell"])
        vals = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = int(v)
        if "X" not in vals or "Y" not in vals:
            raise RuntimeError("Cursor read failed")
        return vals["X"], vals["Y"]

    def _clamp(self, x: int, y: int) -> Tuple[int, int]:
        w = self._screen["width"] - 1
        h = self._screen["height"] - 1
        return max(0, min(x, w)), max(0, min(y, h))

    def _impl_screenshot(self) -> Result:
        ModeGate.assert_allowed(require=Mode.PROBE)
        frame = self._capture()
        return Result.ok({
            "width": frame.shape[1],
            "height": frame.shape[0],
            "format": "raw",
            "mean_delta": 0.0,
        })

    def _impl_move_mouse(self, x: int, y: int) -> Result:
        ModeGate.assert_allowed(require=Mode.EXECUTE)

        cx, cy = self._cursor()
        tx, ty = self._clamp(x, y)

        dx = tx - cx
        dy = ty - cy

        if abs(dx) > MOVE_STEP_PX or abs(dy) > MOVE_STEP_PX:
            return Result.err(ErrorCode.UNSAFE_OPERATION)

        before = self._capture()
        self._run(["xdotool", "mousemove", str(tx), str(ty)])
        time.sleep(1.0 / MAX_PX_PER_SEC)
        after = self._capture()

        delta = float(np.mean(np.abs(before.astype(np.int16) - after.astype(np.int16))))

        if delta <= 0:
            return Result.err(ErrorCode.NO_EFFECT)

        return Result.ok({
            "from": (cx, cy),
            "to": (tx, ty),
            "delta": delta,
        })

    def _impl_click(self, button: str, count: int) -> Result:
        ModeGate.assert_allowed(require=Mode.EXECUTE)
        return Result.err(ErrorCode.UNAVAILABLE)

    def _impl_type_text(self, text: str) -> Result:
        ModeGate.assert_allowed(require=Mode.EXECUTE)
        return Result.err(ErrorCode.UNAVAILABLE)

    def self_test(self):
        raise RuntimeError("self_test is forbidden under authority model")
