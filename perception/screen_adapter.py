"""
SCREEN ADAPTER — FROZEN INFRASTRUCTURE

Truth boundary. Pixel-in → Evidence-out.

Hard guarantees:
- Exact framebuffer bytes preserved
- No transformations (no resize, encode, convert, normalize)
- Cryptographic integrity verification
- Atomic persistence or crash
- Deterministic behavior

If anything smells wrong → crash.
"""

import os
import time
import json
import hashlib
import tempfile
from pathlib import Path

import mss
import numpy as np


SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _sha256_bytes(buf: bytes) -> str:
    h = hashlib.sha256()
    h.update(buf)
    return h.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    # Write to temp file → fsync → atomic rename
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            dir=str(path.parent),
            delete=False,
        ) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)

        tmp_path.replace(path)

        # final durability barrier
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    except Exception as e:
        raise RuntimeError(f"Atomic write failure: {e}")


class ScreenSnapshot:
    """
    Immutable factual snapshot. No mutation allowed.
    """

    __slots__ = ("path", "timestamp_monotonic", "timestamp_wall", "width", "height", "checksum")

    def __init__(self, path: Path, tmono: float, twall: float, width: int, height: int, checksum: str):
        self.path = str(path)
        self.timestamp_monotonic = float(tmono)
        self.timestamp_wall = float(twall)
        self.width = int(width)
        self.height = int(height)
        self.checksum = str(checksum)

    def to_dict(self):
        return {
            "path": self.path,
            "timestamp_monotonic": self.timestamp_monotonic,
            "timestamp_wall": self.timestamp_wall,
            "width": self.width,
            "height": self.height,
            "checksum": self.checksum,
        }


class ScreenAdapter:
    """
    Deterministic screen capture boundary.
    """

    def __init__(self):
        self._sct = mss.mss()

    def capture(self) -> ScreenSnapshot:
        t_before = time.perf_counter()

        frame = self._sct.grab(self._sct.monitors[0])

        # Convert to numpy without modification
        np_frame = np.asarray(frame, dtype=np.uint8)

        # Invariant enforcement
        if np_frame.ndim != 3:
            raise RuntimeError(f"Frame invariant violated: ndim={np_frame.ndim}")

        h, w, c = np_frame.shape
        if c != 4:
            raise RuntimeError(f"Color channel invariant violated: expected BGRA(4), got {c}")

        # Freeze the raw bytes exactly as captured
        raw_bytes = np_frame.tobytes()

        # First checksum
        checksum = _sha256_bytes(raw_bytes)

        t_after = time.perf_counter()
        t_wall = time.time()

        # Filename embeds time + checksum prefix
        fname = f"{int(t_wall * 1000)}_{checksum[:16]}.bin"
        target = SNAPSHOT_DIR / fname

        _atomic_write(target, raw_bytes)

        # Re-read → re-hash to guarantee fidelity after persistence
        with open(target, "rb") as f:
            persisted = f.read()

        persisted_hash = _sha256_bytes(persisted)

        if persisted_hash != checksum:
            raise RuntimeError("Post-persist checksum mismatch — storage corruption suspected")

        # Monotonic ordering invariant
        if t_after < t_before:
            raise RuntimeError("Monotonic clock violation")

        return ScreenSnapshot(
            path=target,
            tmono=t_after,
            twall=t_wall,
            width=w,
            height=h,
            checksum=checksum,
        )


# Optional manual check
if __name__ == "__main__":
    adapter = ScreenAdapter()
    snap = adapter.capture()
    print(json.dumps(snap.to_dict(), indent=2))
