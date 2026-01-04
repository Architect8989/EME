from typing import Tuple, List

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase
from execution.action_executor import ExecutorToken


MOVE_STEP_PX = 1


class LinuxBackend(BackendBase):
    """
    Linux X11 live backend (GII body).

    Mechanical invariants:
    - Zero OS interaction at import time
    - Zero OS interaction in __init__
    - Executor token bound exactly once
    - All OS effects occur only inside _impl_* methods
    - Every OS effect gated by:
        - executor token (BackendBase)
        - poison
        - mode gate
    - No retries
    - Fail-closed on any anomaly
    """

    __slots__ = ("_np", "_mss", "_subprocess")

    def __init__(self, token: ExecutorToken) -> None:
        if not isinstance(token, ExecutorToken):
            Poison.trigger("backend instantiated without executor token")

        super().__init__()
        self._bind_executor(token)

        self._np = None
        self._mss = None
        self._subprocess = None

    # ─────────────────────────────────────────────
    # Lazy OS bindings (executor-authorized only)
    # ─────────────────────────────────────────────

    def _ensure_libs(self) -> None:
        if self._np is not None:
            return

        try:
            import numpy as np
            from mss import mss
            import subprocess
        except BaseException as e:
            Poison.trigger(f"backend dependency import failed: {repr(e)}")

        self._np = np
        self._mss = mss
        self._subprocess = subprocess

    # ─────────────────────────────────────────────
    # Low-level OS primitives
    # ─────────────────────────────────────────────

    def _primary_monitor(self):
        self._ensure_libs()
        with self._mss() as sct:
            monitors = sct.monitors
            if not isinstance(monitors, list) or len(monitors) < 2:
                Poison.trigger("primary monitor not found")
            return monitors[1]

    def _capture(self):
        self._ensure_libs()
        mon = self._primary_monitor()

        with self._mss() as sct:
            img = sct.grab(mon)
            buf = img.bgra if hasattr(img, "bgra") else img.raw

            if not isinstance(buf, (bytes, bytearray)):
                Poison.trigger("invalid screen buffer type")

            expected_len = img.width * img.height * 4
            if len(buf) != expected_len:
                Poison.trigger("screen buffer size mismatch")

            return bytes(buf), int(img.width), int(img.height)

    def _run(self, cmd: List[str]) -> str:
        self._ensure_libs()

        if not isinstance(cmd, list) or not cmd:
            Poison.trigger("invalid command")

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
                try:
                    vals[k] = int(v)
                except ValueError:
                    Poison.trigger("invalid cursor value")

        if "X" not in vals or "Y" not in vals:
            Poison.trigger("cursor position unavailable")

        return vals["X"], vals["Y"]

    def _clamp(self, x: int, y: int, w: int, h: int) -> Tuple[int, int]:
        return (
            max(0, min(x, w - 1)),
            max(0, min(y, h - 1)),
        )

    # ─────────────────────────────────────────────
    # BackendBase implementations (executor-only)
    # ─────────────────────────────────────────────

    def _impl_screenshot(self) -> dict:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        buffer, width, height = self._capture()
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

        if not isinstance(x, int) or not isinstance(y, int):
            Poison.trigger("invalid move coordinates")

        _, width, height = self._capture()
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
