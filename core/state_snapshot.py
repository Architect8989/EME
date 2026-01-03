import hashlib
from dataclasses import dataclass
from typing import Tuple

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase, Result


HASH_DOWNSCALE = 8


def _perceptual_hash(buffer: bytes, width: int, height: int) -> str:
    if not buffer:
        Poison.trigger("empty frame buffer")

    expected = width * height * 4
    if len(buffer) != expected:
        Poison.trigger("frame buffer size mismatch")

    step_x = max(1, width // HASH_DOWNSCALE)
    step_y = max(1, height // HASH_DOWNSCALE)

    acc = bytearray()

    for y in range(0, height, step_y):
        for x in range(0, width * 4, step_x * 4):
            idx = y * width * 4 + x
            acc.append(buffer[idx])

    return hashlib.sha256(bytes(acc)).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    screen_hash: str
    resolution: Tuple[int, int]
    cursor: Tuple[int, int]

    @classmethod
    def from_backend(cls, backend: BackendBase) -> "StateSnapshot":
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        res: Result = backend.screenshot(_executor_token=backend._executor_token)
        if not res.ok:
            Poison.trigger("screenshot failed during state snapshot")

        if "buffer" not in res.details:
            Poison.trigger("screenshot missing buffer")

        if "width" not in res.details or "height" not in res.details:
            Poison.trigger("screenshot missing resolution")

        width = res.details["width"]
        height = res.details["height"]

        if not isinstance(width, int) or not isinstance(height, int):
            Poison.trigger("invalid resolution type")

        if width <= 0 or height <= 0:
            Poison.trigger("invalid resolution values")

        buffer = res.details["buffer"]
        screen_hash = _perceptual_hash(buffer, width, height)

        cursor = res.details.get("cursor")
        if cursor is None or not isinstance(cursor, tuple) or len(cursor) != 2:
            Poison.trigger("cursor position unavailable")

        x, y = cursor
        if not isinstance(x, int) or not isinstance(y, int):
            Poison.trigger("invalid cursor coordinates")

        if x < 0 or y < 0 or x >= width or y >= height:
            Poison.trigger("cursor out of bounds")

        return cls(
            screen_hash=screen_hash,
            resolution=(width, height),
            cursor=(x, y),
        )

    def equals(self, other: "StateSnapshot") -> bool:
        if other is None:
            Poison.trigger("comparison against null snapshot")

        return (
            self.screen_hash == other.screen_hash
            and self.resolution == other.resolution
            and self.cursor == other.cursor
        )
