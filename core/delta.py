from typing import Dict, Any
import hashlib

from core.poison import Poison


def compute_delta(
    *,
    pre_buffer: bytes,
    post_buffer: bytes,
    width: int,
    height: int,
) -> Dict[str, Any]:
    # ─────────────────────────────
    # Hard validation (fail-closed)
    # ─────────────────────────────
    if not isinstance(pre_buffer, (bytes, bytearray)):
        Poison.trigger("invalid pre_buffer")

    if not isinstance(post_buffer, (bytes, bytearray)):
        Poison.trigger("invalid post_buffer")

    if not isinstance(width, int) or not isinstance(height, int):
        Poison.trigger("invalid dimensions")

    if width <= 0 or height <= 0:
        Poison.trigger("non-positive dimensions")

    if len(pre_buffer) != len(post_buffer):
        Poison.trigger("buffer size mismatch")

    if len(pre_buffer) == 0:
        Poison.trigger("empty buffers")

    # BGRA invariant: 4 bytes per pixel
    if len(pre_buffer) % 4 != 0:
        Poison.trigger("buffer not aligned to 4 bytes per pixel")

    pixels_total = width * height
    expected_len = pixels_total * 4

    if len(pre_buffer) != expected_len:
        Poison.trigger("buffer length does not match dimensions")

    # ─────────────────────────────
    # Deterministic checksums
    # ─────────────────────────────
    pre_checksum = hashlib.sha256(pre_buffer).hexdigest()
    post_checksum = hashlib.sha256(post_buffer).hexdigest()

    # ─────────────────────────────
    # Pixel-wise delta (strict)
    # ─────────────────────────────
    pixels_changed = 0

    for i in range(0, expected_len, 4):
        if pre_buffer[i:i + 4] != post_buffer[i:i + 4]:
            pixels_changed += 1

    percent_changed = pixels_changed / pixels_total

    # ─────────────────────────────
    # Deterministic output
    # ─────────────────────────────
    return {
        "pre_checksum": pre_checksum,
        "post_checksum": post_checksum,
        "pixels_total": pixels_total,
        "pixels_changed": pixels_changed,
        "percent_changed": percent_changed,
                       }
