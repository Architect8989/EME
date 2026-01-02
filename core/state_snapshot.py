import hashlib
from dataclasses import dataclass
from typing import Tuple

import numpy as np

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase


HASH_DOWNSCALE = 8


def _perceptual_hash(frame: np.ndarray) -> str:
    if frame is None or frame.size == 0:
        Poison.trigger("Invalid frame for perceptual hash")

    if frame.ndim != 3 or frame.shape[2] < 3:
        Poison.trigger("Unexpected frame shape")

    gray = frame[..., :3].mean(axis=2)
    h, w = gray.shape

    if h < HASH_DOWNSCALE or w < HASH_DOWNSCALE:
        Poison.trigger("Frame too small for hashing")

    sh, sw = h // HASH_DOWNSCALE, w // HASH_DOWNSCALE
    small = gray[: sh * HASH_DOWNSCALE, : sw * HASH_DOWNSCALE]
    small = small.reshape(sh, HASH_DOWNSCALE, sw, HASH_DOWNSCALE).mean(axis=(1, 3))

    mean = small.mean()
    bits = small > mean

    return hashlib.sha256(bits.tobytes()).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    screen_hash: str
    resolution: Tuple[int, int]
    cursor: Tuple[int, int]

    @classmethod
    def from_backend(cls, backend: BackendBase) -> "StateSnapshot":
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        res = backend.screenshot()
        if not res.ok:
            Poison.trigger("Screenshot failed during state snapshot")

        if "width" not in res.data or "height" not in res.data:
            Poison.trigger("Screenshot missing resolution metadata")

        width = res.data["width"]
        height = res.data["height"]

        if width <= 0 or height <= 0:
            Poison.trigger("Invalid screen resolution")

        frame = backend._capture()
        screen_hash = _perceptual_hash(frame)

        cursor = backend._cursor()
        if cursor is None or len(cursor) != 2:
            Poison.trigger("Cursor position unavailable")

        x, y = cursor
        if x < 0 or y < 0 or x >= width or y >= height:
            Poison.trigger("Cursor position out of bounds")

        return cls(
            screen_hash=screen_hash,
            resolution=(width, height),
            cursor=(x, y),
        )

    def equals(self, other: "StateSnapshot") -> bool:
        if other is None:
            Poison.trigger("Comparison against null state snapshot")

        return (
            self.screen_hash == other.screen_hash
            and self.resolution == other.resolution
            and self.cursor == other.cursor
)
