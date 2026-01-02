import hashlib
from dataclasses import dataclass
from typing import Tuple

import numpy as np

from core.mode_gate import ModeGate, Mode
from execution.backend_contract import BackendBase, Result


HASH_DOWNSCALE = 8
PIXEL_TOLERANCE = 0.02


class StateSnapshotError(Exception):
    pass


def _perceptual_hash(frame: np.ndarray) -> str:
    gray = frame[..., :3].mean(axis=2)
    h, w = gray.shape
    sh, sw = h // HASH_DOWNSCALE, w // HASH_DOWNSCALE
    small = gray[: sh * HASH_DOWNSCALE, : sw * HASH_DOWNSCALE]
    small = small.reshape(sh, HASH_DOWNSCALE, sw, HASH_DOWNSCALE).mean(axis=(1, 3))
    bits = small > small.mean()
    return hashlib.sha256(bits.tobytes()).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    screen_hash: str
    resolution: Tuple[int, int]
    cursor: Tuple[int, int]

    @classmethod
    def from_backend(cls, backend: BackendBase) -> "StateSnapshot":
        ModeGate.assert_allowed(require=Mode.PROBE)

        res = backend.screenshot()
        if not res.ok:
            raise StateSnapshotError("Screenshot failed")

        frame = backend._capture()  # internal, calibrated
        screen_hash = _perceptual_hash(frame)

        cursor = backend._cursor()
        resolution = (res.data["width"], res.data["height"])

        return cls(
            screen_hash=screen_hash,
            resolution=resolution,
            cursor=cursor,
        )

    def equals(self, other: "StateSnapshot") -> bool:
        return (
            self.screen_hash == other.screen_hash
            and self.resolution == other.resolution
            and self.cursor == other.cursor
        )

    def similarity(self, other: "StateSnapshot") -> float:
        if self.resolution != other.resolution:
            return 0.0
        return 1.0 if self.screen_hash == other.screen_hash else 0.0

    def is_known_relative(self, other: "StateSnapshot") -> bool:
        return self.similarity(other) >= (1.0 - PIXEL_TOLERANCE)
