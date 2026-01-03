import time
import hashlib
import tempfile
import pathlib
import threading
import os
import json
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, Dict, Any

from core.system_state import SystemState
from core.mode_gate import ModeGate, Mode
from core.poison import Poison


CAPTURE_RETRIES = 3
CAPTURE_BACKOFF = 0.15  # seconds


@dataclass(frozen=True)
class Frame:
    path: pathlib.Path
    width: int
    height: int
    checksum: str
    timestamp_monotonic: float
    previous_checksum: str
    monitor: Optional[int]
    pixel_format: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


class CaptureError(RuntimeError):
    pass


class ForensicCapture:
    """
    Forensic-grade screen capture.

    Mechanical guarantees:
    - No import-time OS access
    - Lossless raw buffers only
    - Monotonic timestamps
    - SHA-256 hash chain
    - fsync durability
    - Crash on any anomaly
    """

    def __init__(self, *, monitor: Optional[int] = None):
        SystemState.assert_initialized()
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        self._monitor = monitor
        self._lock = threading.Lock()

        self._tmpdir = pathlib.Path(tempfile.gettempdir()) / "eme_frames"
        self._tmpdir.mkdir(exist_ok=True, parents=True)

        self._last_timestamp: float = 0.0
        self._last_checksum: str = ""
        self._frame_count: int = 0

    # ---------- internal helpers ----------

    def _checksum(self, data: bytes) -> str:
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def _stable_path(self, ts: float) -> pathlib.Path:
        return self._tmpdir / f"frame_{int(ts * 1_000_000):020d}.raw"

    def _validate_buffer(self, data: bytes, w: int, h: int):
        expected = w * h * 4
        if len(data) != expected:
            raise CaptureError("buffer size mismatch")

    def _grab(self) -> Tuple[bytes, int, int, str]:
        # Lazy import — NO import-time OS effects
        import mss

        with mss.mss() as sct:
            if self._monitor is None:
                mon = sct.monitors[0]
            else:
                if self._monitor >= len(sct.monitors):
                    raise CaptureError("monitor index out of range")
                mon = sct.monitors[self._monitor]

            img = sct.grab(mon)
            data = img.bgra if hasattr(img, "bgra") else img.raw
            self._validate_buffer(data, img.width, img.height)
            return data, img.width, img.height, "BGRA"

    def _write_atomic(self, data: bytes, path: pathlib.Path):
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if tmp.stat().st_size != len(data):
            raise CaptureError("partial write detected")

        tmp.replace(path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        os.fsync(dir_fd)
        os.close(dir_fd)

    def _write_sidecar(self, frame: Frame):
        sidecar = frame.path.with_suffix(".json")
        tmp = sidecar.with_suffix(".tmp")

        payload = frame.to_dict()
        payload["frame_number"] = self._frame_count
        payload["system_time"] = time.time()
        payload["bytes_per_pixel"] = 4

        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())

        tmp.replace(sidecar)
        dir_fd = os.open(str(sidecar.parent), os.O_RDONLY)
        os.fsync(dir_fd)
        os.close(dir_fd)

    # ---------- public API ----------

    def capture(self) -> Frame:
        SystemState.assert_initialized()
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        with self._lock:
            for attempt in range(CAPTURE_RETRIES):
                try:
                    ts = time.monotonic()
                    if ts <= self._last_timestamp:
                        raise CaptureError("non-monotonic timestamp")

                    data, w, h, fmt = self._grab()
                    checksum = self._checksum(data)
                    path = self._stable_path(ts)

                    self._write_atomic(data, path)

                    frame = Frame(
                        path=path,
                        width=w,
                        height=h,
                        checksum=checksum,
                        timestamp_monotonic=ts,
                        previous_checksum=self._last_checksum,
                        monitor=self._monitor,
                        pixel_format=fmt,
                    )

                    self._write_sidecar(frame)

                    self._last_timestamp = ts
                    self._last_checksum = checksum
                    self._frame_count += 1

                    return frame

                except CaptureError:
                    raise
                except Exception as e:
                    if attempt + 1 >= CAPTURE_RETRIES:
                        raise CaptureError(str(e))
                    time.sleep(CAPTURE_BACKOFF)

            raise CaptureError("capture failed unexpectedly")
