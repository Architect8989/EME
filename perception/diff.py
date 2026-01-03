import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from core.poison import Poison


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except BaseException as e:
        Poison.trigger(f"checksum read failed: {repr(e)}")
    return h.hexdigest()


def _bbox_from_diff(diff_img) -> Optional[Tuple[int, int, int, int]]:
    try:
        return diff_img.getbbox()
    except BaseException as e:
        Poison.trigger(f"bbox computation failed: {repr(e)}")


def compute_delta(pre_path: Path, post_path: Path) -> Dict[str, Any]:
    if not isinstance(pre_path, Path) or not isinstance(post_path, Path):
        Poison.trigger("invalid path arguments")

    if not pre_path.exists() or not post_path.exists():
        Poison.trigger("delta paths do not exist")

    try:
        from PIL import Image, ImageChops
        import numpy as np
    except BaseException as e:
        Poison.trigger(f"diff import failed: {repr(e)}")

    try:
        pre = Image.open(pre_path).convert("L")
        post = Image.open(post_path).convert("L")
    except BaseException as e:
        Poison.trigger(f"image load failed: {repr(e)}")

    pre_checksum = _checksum(pre_path)
    post_checksum = _checksum(post_path)

    if pre.size != post.size:
        total = pre.size[0] * pre.size[1]
        return {
            "pre_checksum": pre_checksum,
            "post_checksum": post_checksum,
            "pixels_total": total,
            "pixels_changed": total,
            "percent_changed": 1.0,
            "bbox": [0, 0, pre.size[0], pre.size[1]],
        }

    try:
        diff = ImageChops.difference(pre, post)
    except BaseException as e:
        Poison.trigger(f"image diff failed: {repr(e)}")

    diff_arr = np.asarray(diff)
    if diff_arr.size == 0:
        Poison.trigger("empty diff array")

    pixels_total = int(diff_arr.size)
    pixels_changed = int((diff_arr != 0).sum())

    bbox = _bbox_from_diff(diff)

    return {
        "pre_checksum": pre_checksum,
        "post_checksum": post_checksum,
        "pixels_total": pixels_total,
        "pixels_changed": pixels_changed,
        "percent_changed": pixels_changed / pixels_total,
        "bbox": list(bbox) if bbox else None,
    }
