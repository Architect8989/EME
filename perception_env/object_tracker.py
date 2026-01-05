from typing import List, Dict, Tuple
import math

from perception_env.region import Region
from perception_env.object import VisualObject


class ObjectTracker:
    """
    Deterministic region-to-object tracker.

    Responsibilities:
    - Match current Regions to existing VisualObjects
    - Maintain ephemeral identities within a single run
    - Mark objects dead when unmatched
    - No guessing beyond thresholds; ambiguity reduces stability

    Guarantees:
    - No OS access
    - No executor/backend access
    - No persistence
    """

    def __init__(
        self,
        *,
        iou_threshold: float = 0.25,
        centroid_dist_threshold: float = 64.0,
        max_objects: int = 512,
    ) -> None:
        self._iou_th = iou_threshold
        self._dist_th = centroid_dist_threshold
        self._max_objects = max_objects

        self._next_id: int = 1
        self._objects: Dict[int, VisualObject] = {}

    @staticmethod
    def _centroid(r: Region) -> Tuple[float, float]:
        return (r.x + r.width / 2.0, r.y + r.height / 2.0)

    @staticmethod
    def _centroid_dist(a: Region, b: Region) -> float:
        ax, ay = ObjectTracker._centroid(a)
        bx, by = ObjectTracker._centroid(b)
        return math.hypot(ax - bx, ay - by)

    def _score(self, obj: VisualObject, reg: Region) -> float:
        """
        Higher score is better.
        Combine IoU and inverse centroid distance.
        """
        last = obj.latest_region
        iou = last.iou(reg)
        dist = self._centroid_dist(last, reg)

        if iou <= 0.0 and dist > self._dist_th:
            return 0.0

        # Normalize distance contribution
        dist_score = max(0.0, 1.0 - (dist / self._dist_th))
        return (0.7 * iou) + (0.3 * dist_score)

    def update(self, regions: List[Region]) -> List[VisualObject]:
        """
        Update tracker with regions from the current frame.

        Returns the list of alive VisualObjects after update.
        """
        # Mark all objects as unmatched initially
        matched_obj_ids = set()
        matched_regions = set()

        # Greedy matching (deterministic order)
        for reg_idx, reg in enumerate(regions):
            best_id = None
            best_score = 0.0

            for obj_id, obj in self._objects.items():
                if not obj.alive:
                    continue
                score = self._score(obj, reg)
                if score > best_score:
                    best_score = score
                    best_id = obj_id

            if best_id is not None and best_score >= self._iou_th:
                obj = self._objects[best_id]
                obj.update(reg, stability_delta=+0.1)
                matched_obj_ids.add(best_id)
                matched_regions.add(reg_idx)

        # Create new objects for unmatched regions
        for idx, reg in enumerate(regions):
            if idx in matched_regions:
                continue
            if len(self._objects) >= self._max_objects:
                break

            obj = VisualObject(
                object_id=self._next_id,
                regions=[reg],
                age=1,
                stability=0.2,
                alive=True,
            )
            self._objects[self._next_id] = obj
            matched_obj_ids.add(self._next_id)
            self._next_id += 1

        # Decay or kill unmatched objects
        for obj_id, obj in list(self._objects.items()):
            if not obj.alive:
                continue
            if obj_id not in matched_obj_ids:
                obj.stability = max(0.0, obj.stability - 0.2)
                if obj.stability <= 0.0:
                    obj.mark_dead()

        # Return alive objects only
        return [o for o in self._objects.values() if o.alive]
