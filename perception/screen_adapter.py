import time
import hashlib
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any

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


class ScreenAdapter:
    """
    Passive frame normalizer.

    Mechanical guarantees:
    - No OS interaction
    - No screen capture
    - No backend access
    - Accepts executor-supplied buffers only
    """

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

    def ingest(
        self,
        *,
        buffer: bytes,
        width: int,
        height: int,
        pixel_format: str,
        monitor: Optional[int] = None,
    ) -> Frame:
        SystemState.assert_initialized()
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        if not isinstance(buffer, (bytes, bytearray)) or not buffer:
            Poison.trigger("invalid screen buffer")

        if not isinstance(width, int) or not isinstance(height, int):
            Poison.trigger("invalid frame dimensions")

        if width <= 0 or height <= 0:
            Poison.trigger("non-positive frame dimensions")

        with self._lock:
            ts = time.monotonic()
            if ts <= self._last_timestamp:
                Poison.trigger("non-monotonic screen timestamp")

            checksum = self._checksum(buffer)

            frame = Frame(
                width=width,
                height=height,
                checksum=checksum,
                timestamp_monotonic=ts,
                previous_checksum=self._last_checksum,
                monitor=monitor,
                pixel_format=pixel_format,
                buffer=bytes(buffer),
            )

            self._last_timestamp = ts
            self._last_checksum = checksum

            return frame
