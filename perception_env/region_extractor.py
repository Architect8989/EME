from typing import List, Tuple

import numpy as np
import cv2

from perception.screen_adapter import Frame
from perception_env.region import Region


class RegionExtractor:
    """
    Deterministic visual region extractor.

    Responsibility:
    - Convert a Frame into a set of visual Regions
    - No learning, no state, no caching
    - Pure pixel-to-structure transformation

    Guarantees:
    - No OS access
    - No executor / backend access
    - Deterministic for identical input frames
    """

    def __init__(
        self,
        *,
        min_region_area: int = 400,
        canny_low: int = 80,
        canny_high: int = 160,
    ) -> None:
        self._min_region_area = min_region_area
        self._canny_low = canny_low
        self._canny_high = canny_high

    def extract(self, frame: Frame) -> List[Region]:
        if frame is None:
            raise RuntimeError("frame is None")

        # ---- Decode buffer ----
        width = frame.width
        height = frame.height
        buf = frame.buffer

        expected_len = width * height * 4
        if len(buf) != expected_len:
            raise RuntimeError("frame buffer size mismatch")

        img = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 4))
        bgr = img[:, :, :3]  # BGRA → BGR

        # ---- Preprocess ----
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # ---- Edge detection ----
        edges = cv2.Canny(
            blurred,
            threshold1=self._canny_low,
            threshold2=self._canny_high,
        )

        # ---- Morphological closing ----
        kernel = np.ones((3, 3), np.uint8)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        # ---- Contour extraction ----
        contours, _ = cv2.findContours(
            closed,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        regions: List[Region] = []

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h

            if area < self._min_region_area:
                continue

            # ---- Mask for this region ----
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 1, thickness=-1)

            # ---- Visual descriptors ----
            region_pixels = bgr[mask == 1]
            if region_pixels.size == 0:
                continue

            mean_color_bgr = region_pixels.mean(axis=0)
            mean_color_rgb = (
                int(mean_color_bgr[2]),
                int(mean_color_bgr[1]),
                int(mean_color_bgr[0]),
            )

            edge_pixels = edges[mask == 1]
            edge_density = float(edge_pixels.sum() > 0) / max(1, region_pixels.shape[0])

            contour_hash = Region.compute_contour_hash(
                mask[y : y + h, x : x + w].tobytes()
            )

            regions.append(
                Region(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    area=area,
                    mean_color=mean_color_rgb,
                    edge_density=edge_density,
                    contour_hash=contour_hash,
                )
            )

        return regions
