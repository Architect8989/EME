import time
import hashlib
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from core.system_state import SystemState
from core.mode_gate import ModeGate, Mode
from core.poison import Poison


@dataclass(frozen=True)
class Frame:
    width: int
    height: int
    checksum: str
    timestamp_monotonic: float
    previous_checksum: str
    monitor: Optional[int]
    pixel_format: str
    buffer: bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "checksum": self.checksum,
            "timestamp_monotonic": self.timestamp_monotonic,
            "previous_checksum": self.previous_checksum,
            "monitor": self.monitor,
            "pixel_format": self.pixel_format,
        }


class CaptureError(RuntimeError):
    pass


class ScreenAdapter:
    def __init__(self):
        SystemState.assert_initialized()
        Poison.assert_clean()
        self._lock = threading.Lock()
        self._last_timestamp: float = 0.0
        self._last_checksum: str = ""

    def _checksum(self, data: bytes) -> str:
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def _grab(self) -> Tuple[bytes, int, int, str]:
        import mss

        with mss.mss() as sct:
            mon = sct.monitors[0]
            img = sct.grab(mon)
            data = img.bgra if hasattr(img, "bgra") else img.raw
            if len(data) != img.width * img.height * 4:
                raise CaptureError("buffer size mismatch")
            return data, img.width, img.height, "BGRA"

    def capture(self) -> Frame:
        SystemState.assert_initialized()
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        with self._lock:
            ts = time.monotonic()
            if ts <= self._last_timestamp:
                Poison.trigger("non-monotonic screen timestamp")

            try:
                data, w, h, fmt = self._grab()
            except BaseException as e:
                Poison.trigger(f"screen grab failed: {repr(e)}")

            checksum = self._checksum(data)

            frame = Frame(
                width=w,
                height=h,
                checksum=checksum,
                timestamp_monotonic=ts,
                previous_checksum=self._last_checksum,
                monitor=None,
                pixel_format=fmt,
                buffer=data,
            )

            self._last_timestamp = ts
            self._last_checksum = checksum

            return frame
