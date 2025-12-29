"""
Screen capture — forensic grade.

Requirements:
— Lossless capture only
— Monotonic timestamps
— SHA256 checksums
— Stable file naming
— Multi-monitor support
— Retries with backoff
— No silent partial frames
"""

import time
import hashlib
import tempfile
import pathlib
import threading

from dataclasses import dataclass
from typing import Optional, Tuple

# Choose the right backend per OS. Avoid lossy APIs.
# Example uses mss because it is stable and cross-platform.
import mss


CAPTURE_RETRIES = 3
CAPTURE_BACKOFF = 0.15  # seconds


@dataclass
class Frame:
    path: pathlib.Path
    width: int
    height: int
    checksum: str
    timestamp_monotonic: float


class CaptureError(Exception):
    pass


class ScreenCapture:
    def __init__(self, monitor: Optional[int] = None):
        # monitor=None means “all monitors”
        self._monitor = monitor
        self._lock = threading.Lock()
        self._tmpdir = pathlib.Path(tempfile.gettempdir()) / "eme_frames"
        self._tmpdir.mkdir(exist_ok=True, parents=True)

    def _stable_path(self, ts: float) -> pathlib.Path:
        # deterministic, sortable filenames
        name = f"frame_{int(ts * 1_000_000)}.raw"
        return self._tmpdir / name

    def _checksum(self, data: bytes) -> str:
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def _grab(self) -> Tuple[bytes, int, int]:
        with mss.mss() as sct:
            if self._monitor is None:
                monitor = sct.monitors[0]  # virtual monitor (all)
            else:
                if self._monitor >= len(sct.monitors):
                    raise CaptureError("monitor index out of range")
                monitor = sct.monitors[self._monitor]

            img = sct.grab(monitor)

            # enforce 32-bit RGBA raw buffer
            width = img.width
            height = img.height

            # mss already provides BGRA contiguous bytes
            raw = img.rgb  # converts to RGB; we normalize to RGBA below
            # Normalize to RGBA with opaque alpha
            rgba = bytearray()
            for i in range(0, len(raw), 3):
                r = raw[i]
                g = raw[i + 1]
                b = raw[i + 2]
                rgba.extend((r, g, b, 255))

            data = bytes(rgba)
            expected = width * height * 4
            if len(data) != expected:
                raise CaptureError("dimension mismatch in capture buffer")

            return data, width, height

    def capture(self) -> Frame:
        with self._lock:
            for attempt in range(1, CAPTURE_RETRIES + 1):
                ts = time.monotonic()
                path = self._stable_path(ts)

                try:
                    data, w, h = self._grab()
                    checksum = self._checksum(data)

                    # write atomically
                    tmp = path.with_suffix(".raw.tmp")
                    with open(tmp, "wb") as f:
                        f.write(data)
                        f.flush()

                    tmp.replace(path)

                    return Frame(
                        path=path,
                        width=w,
                        height=h,
                        checksum=checksum,
                        timestamp_monotonic=ts,
                    )

                except Exception as e:
                    if attempt == CAPTURE_RETRIES:
                        raise CaptureError(f"capture failed: {e}")
                    time.sleep(CAPTURE_BACKOFF)
