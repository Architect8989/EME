import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_from_diff(diff_img) -> Optional[Tuple[int, int, int, int]]:
    return diff_img.getbbox()


def compute_delta(pre_path: Path, post_path: Path) -> Dict[str, Any]:
    """
    Computes a deterministic visual delta.

    Contract:
    - Never raises
    - Never lies
    - Any internal inconsistency is surfaced explicitly
    """

    try:
        # ---- lazy imports (no import-time effects) ----
        from PIL import Image, ImageChops
        import numpy as np

        pre = Image.open(pre_path).convert("L")
        post = Image.open(post_path).convert("L")

        pre_checksum = _checksum(pre_path)
        post_checksum = _checksum(post_path)

        if pre.size != post.size:
            total = pre.size[0] * pre.size[1]
            return {
                "error": None,
                "pre_checksum": pre_checksum,
                "post_checksum": post_checksum,
                "pixels_total": total,
                "pixels_changed": total,
                "percent_changed": 1.0,
                "bbox": [0, 0, pre.size[0], pre.size[1]],
            }

        diff = ImageChops.difference(pre, post)

        # Convert once, vectorized count (deterministic)
        diff_arr = np.asarray(diff)
        pixels_total = diff_arr.size
        pixels_changed = int((diff_arr != 0).sum())

        bbox = _bbox_from_diff(diff)

        return {
            "error": None,
            "pre_checksum": pre_checksum,
            "post_checksum": post_checksum,
            "pixels_total": pixels_total,
            "pixels_changed": pixels_changed,
            "percent_changed": (
                pixels_changed / pixels_total if pixels_total else 0.0
            ),
            "bbox": list(bbox) if bbox else None,
        }

    except Exception as e:
        # Explicit failure surface — never ambiguous
        return {
            "error": f"diff_failure:{type(e).__name__}",
            "pre_checksum": None,
            "post_checksum": None,
            "pixels_total": None,
            "pixels_changed": None,
            "percent_changed": None,
            "bbox": None,
        }
