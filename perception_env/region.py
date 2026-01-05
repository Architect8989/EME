from dataclasses import dataclass
from typing import Tuple
import hashlib


@dataclass(frozen=True)
class Region:
    """
    Immutable visual region primitive.

    Represents a contiguous visual area derived from pixels.
    Pure data + deterministic computation only.

    Invariants:
    - No OS access
    - No backend access
    - No executor access
    - No mutation
    - No side effects
    """

    # Bounding box (inclusive-exclusive)
    x: int
    y: int
    width: int
    height: int

    # Simple visual descriptors
    area: int
    mean_color: Tuple[int, int, int]   # RGB mean
    edge_density: float                # 0.0 – 1.0
    contour_hash: str                  # shape fingerprint

    @staticmethod
    def compute_contour_hash(mask_bytes: bytes) -> str:
        """
        Deterministic shape fingerprint.

        mask_bytes:
            A binary mask (same size per region extraction run)
            where region pixels are 1 and others 0.
        """
        if not isinstance(mask_bytes, (bytes, bytearray)) or not mask_bytes:
            raise ValueError("invalid contour mask")

        h = hashlib.sha256()
        h.update(mask_bytes)
        return h.hexdigest()

    def intersects(self, other: "Region") -> bool:
        return not (
            self.x + self.width <= other.x
            or other.x + other.width <= self.x
            or self.y + self.height <= other.y
            or other.y + other.height <= self.y
        )

    def iou(self, other: "Region") -> float:
        """
        Intersection-over-Union.
        Used later by object tracking.
        """
        ix1 = max(self.x, other.x)
        iy1 = max(self.y, other.y)
        ix2 = min(self.x + self.width, other.x + other.width)
        iy2 = min(self.y + self.height, other.y + other.height)

        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        intersection = iw * ih

        if intersection == 0:
            return 0.0

        union = self.area + other.area - intersection
        if union <= 0:
            return 0.0

        return intersection / union
