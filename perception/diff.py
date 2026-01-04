import hashlib
from typing import Dict, Any, Optional, Tuple

import numpy as np

from core.poison import Poison
from perception.screen_adapter import Frame


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def compute_delta(pre: Frame, post: Frame) -> Dict[str, Any]:
    """
    Deterministic, in-memory visual delta.

    Mechanical guarantees:
    - No filesystem access
    - No OS interaction
    - No retries
    - Any ambiguity poisons immediately
    """

    if not isinstance(pre, Frame) or not isinstance(post, Frame):
        Poison.trigger("delta requires Frame inputs")

    if pre.width != post.width or pre.height != post.height:
        total = pre.width * pre.height
        return {
            "pre_checksum": pre.checksum,
            "post_checksum": post.checksum,
            "pixels_total": total,
            "pixels_changed": total,
            "percent_changed": 1.0,
            "bbox": [0, 0, pre.width, pre.height],
        }

    try:
        a = np.frombuffer(pre.buffer, dtype=np.uint8)
        b = np.frombuffer(post.buffer, dtype=np.uint8)
    except BaseException as e:
        Poison.trigger(f"buffer decode failed: {repr(e)}")

    if a.size != b.size or a.size == 0:
        Poison.trigger("invalid frame buffer sizes")

    diff = a != b
    pixels_total = int(diff.size)
    pixels_changed = int(diff.sum())

    percent_changed = pixels_changed / pixels_total

    return {
        "pre_checksum": pre.checksum,
        "post_checksum": post.checksum,
        "pixels_total": pixels_total,
        "pixels_changed": pixels_changed,
        "percent_changed": percent_changed,
        "bbox": None,  # bbox intentionally omitted (no heuristics)
    }
