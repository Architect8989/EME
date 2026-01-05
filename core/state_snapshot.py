import hashlib
from dataclasses import dataclass
from typing import Tuple

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase, Result


HASH_DOWNSCALE = 8


def _perceptual_hash(buffer: bytes, width: int, height: int) -> str:
    if not isinstance(buffer, (bytes, bytearray)) or not buffer:
        Poison.trigger("invalid or empty frame buffer")

    expected = width * height * 4
    if len(buffer) != expected:
        Poison.trigger("frame buffer size mismatch")

    step_x = max(1, width // HASH_DOWNSCALE)
    step_y = max(1, height // HASH_DOWNSCALE)

    acc = bytearray()

    for y in range(0, height, step_y):
        row_base = y * width * 4
        for x in range(0, width, step_x):
            idx = row_base + x * 4
            acc.append(buffer[idx])

    return hashlib.sha256(bytes(acc)).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    """
    Read-only perceptual snapshot.

    Enforced invariants:
    - No OS effects initiated here
    - Read path only, executor-context only
    - Deterministic, buffer-derived state
    - Any ambiguity is terminal
    """

    screen_hash: str
    resolution: Tuple[int, int]
    cursor: Tuple[int, int]

    @classmethod
    def from_backend(cls, backend: BackendBase) -> "StateSnapshot":
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.PROBE)

        # executor-context read; backend enforces token internally
        try:
            res: Result = backend.screenshot(
                _executor_token=backend._executor_token  # executor-owned context
            )
        except BaseException as e:
            Poison.trigger(f"state snapshot screenshot failure: {repr(e)}")

        if not res.ok:
            Poison.trigger("screenshot failed during state snapshot")

        details = res.details
        if not isinstance(details, dict):
            Poison.trigger("screenshot details invalid")

        if "buffer" not in details:
            Poison.trigger("screenshot missing buffer")

        if "width" not in details or "height" not in details:
            Poison.trigger("screenshot missing resolution")

        width = details["width"]
        height = details["height"]

        if not isinstance(width, int) or not isinstance(height, int):
            Poison.trigger("invalid resolution type")

        if width <= 0 or height <= 0:
            Poison.trigger("invalid resolution values")

        buffer = details["buffer"]
        screen_hash = _perceptual_hash(buffer, width, height)

        cursor = details.get("cursor")
        if (
            cursor is None
            or not isinstance(cursor, tuple)
            or len(cursor) != 2
            or not all(isinstance(v, int) for v in cursor)
        ):
            Poison.trigger("cursor position unavailable or invalid")

        x, y = cursor
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
