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
    """
    Immutable perceptual frame.
    Pure data; no behavior.
    """
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

    Enforced invariants:
    - No OS access
    - No backend coupling
    - Import-time inert
    - Deterministic
    - Monotonic time
    - No retries, no persistence
    """

    _BYTES_PER_PIXEL = 4
    _ALLOWED_PIXEL_FORMAT = "BGRA"

    def __init__(self) -> None:
        SystemState.assert_initialized()
        Poison.assert_clean()

        self._lock = threading.Lock()
        self._last_timestamp: float = 0.0
        self._last_checksum: str = ""

    @staticmethod
    def _checksum(data: bytes) -> str:
        if not isinstance(data, (bytes, bytearray)) or not data:
            Poison.trigger("invalid buffer for checksum")
        return hashlib.sha256(bytes(data)).hexdigest()

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

        # ───────── HARD VALIDATION ─────────
        if not isinstance(buffer, (bytes, bytearray)):
            Poison.trigger("screen buffer not bytes")

        if not isinstance(width, int) or not isinstance(height, int):
            Poison.trigger("invalid frame dimensions")

        if width <= 0 or height <= 0:
            Poison.trigger("non-positive frame dimensions")

        if pixel_format != self._ALLOWED_PIXEL_FORMAT:
            Poison.trigger("unsupported pixel format")

        expected_len = width * height * self._BYTES_PER_PIXEL
        if len(buffer) != expected_len:
            Poison.trigger("buffer length mismatch")

        # ───────── CONTINUITY ENFORCEMENT ─────────
        with self._lock:
            ts = time.monotonic()
            if ts <= self._last_timestamp:
                Poison.trigger("non-monotonic frame timestamp")

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
