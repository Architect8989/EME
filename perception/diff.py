"""
Image difference utilities.

Compute level-0 deltas:
- checksums (pre / post)
- pixel change count
- percent changed
- bounding box of changed region (if any)

No semantics. No guesses. Pure measurement.
"""

import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from PIL import Image, ImageChops, ImageStat


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_from_diff(diff_img: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    # PIL returns None if no change
    return diff_img.getbbox()


def compute_delta(pre_path: Path, post_path: Path) -> Dict[str, Any]:
    """
    Returns a dict suitable to place inside Delta.data
    Never raises — on failure, returns minimal diagnostic structure.
    """

    try:
        pre = Image.open(pre_path).convert("L")   # grayscale
        post = Image.open(post_path).convert("L")

        if pre.size != post.size:
            # Different shapes — treat as full-frame change
            return {
                "error": None,
                "pre_checksum": _checksum(pre_path),
                "post_checksum": _checksum(post_path),
                "pixels_total": pre.size[0] * pre.size[1],
                "pixels_changed": pre.size[0] * pre.size[1],
                "percent_changed": 1.0,
                "bbox": [0, 0, pre.size[0], pre.size[1]],
            }

        diff = ImageChops.difference(pre, post)
        stat = ImageStat.Stat(diff)

        # Count non-zero pixels
        pixels_total = pre.size[0] * pre.size[1]
        non_zero = sum(1 for p in diff.getdata() if p != 0)

        bbox = _bbox_from_diff(diff)

        return {
            "error": None,
            "pre_checksum": _checksum(pre_path),
            "post_checksum": _checksum(post_path),
            "pixels_total": pixels_total,
            "pixels_changed": non_zero,
            "percent_changed": non_zero / pixels_total if pixels_total else 0.0,
            "bbox": list(bbox) if bbox else None,
        }

    except Exception as e:
        return {
            "error": str(e),
            "pre_checksum": None,
            "post_checksum": None,
            "pixels_total": None,
            "pixels_changed": None,
            "percent_changed": None,
            "bbox": None,
  }
