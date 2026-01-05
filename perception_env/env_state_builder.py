import time
from typing import List, Tuple

from perception_env.object import VisualObject
from perception_env.env_state import EnvironmentState, SpatialRelation


class EnvironmentStateBuilder:
    """
    Deterministic environment state builder.

    Responsibilities:
    - Derive spatial relations between visual objects
    - Identify focus candidates
    - Identify cursor proximity relations
    - Build a read-only EnvironmentState

    Invariants:
    - No OS access
    - No backend / executor access
    - No persistence
    - Deterministic for identical inputs
    """

    def __init__(
        self,
        *,
        overlap_iou_threshold: float = 0.2,
        containment_iou_threshold: float = 0.8,
        cursor_proximity_px: int = 32,
    ) -> None:
        self._overlap_iou_th = overlap_iou_threshold
        self._containment_iou_th = containment_iou_threshold
        self._cursor_px = cursor_proximity_px

    @staticmethod
    def _center(obj: VisualObject) -> Tuple[float, float]:
        r = obj.latest_region
        return (r.x + r.width / 2.0, r.y + r.height / 2.0)

    def _spatial_relations(
        self, objects: List[VisualObject]
    ) -> List[SpatialRelation]:
        relations: List[SpatialRelation] = []

        for i, a in enumerate(objects):
            ra = a.latest_region
            for j, b in enumerate(objects):
                if i == j:
                    continue
                rb = b.latest_region

                iou = ra.iou(rb)

                # containment
                if iou >= self._containment_iou_th:
                    relations.append(
                        SpatialRelation(
                            a_id=a.object_id,
                            b_id=b.object_id,
                            relation="contains",
                        )
                    )
                    continue

                # overlap
                if iou >= self._overlap_iou_th:
                    relations.append(
                        SpatialRelation(
                            a_id=a.object_id,
                            b_id=b.object_id,
                            relation="overlaps",
                        )
                    )

                # relative positioning
                ax, ay = self._center(a)
                bx, by = self._center(b)

                if ax < bx:
                    relations.append(
                        SpatialRelation(
                            a_id=a.object_id,
                            b_id=b.object_id,
                            relation="left_of",
                        )
                    )
                elif ax > bx:
                    relations.append(
                        SpatialRelation(
                            a_id=a.object_id,
                            b_id=b.object_id,
                            relation="right_of",
                        )
                    )

                if ay < by:
                    relations.append(
                        SpatialRelation(
                            a_id=a.object_id,
                            b_id=b.object_id,
                            relation="above",
                        )
                    )
                elif ay > by:
                    relations.append(
                        SpatialRelation(
                            a_id=a.object_id,
                            b_id=b.object_id,
                            relation="below",
                        )
                    )

        return relations

    def _focus_candidate(self, objects: List[VisualObject]) -> int | None:
        """
        Heuristic focus candidate:
        - highest stability
        - largest area
        """
        if not objects:
            return None

        best = None
        best_score = -1.0

        for obj in objects:
            r = obj.latest_region
            score = (obj.stability * 2.0) + (r.area / 1_000_000.0)
            if score > best_score:
                best_score = score
                best = obj.object_id

        return best

    def _cursor_proximity(
        self,
        objects: List[VisualObject],
        cursor: Tuple[int, int],
    ) -> Tuple[int, ...]:
        cx, cy = cursor
        near: List[int] = []

        for obj in objects:
            r = obj.latest_region
            if (
                abs(cx - (r.x + r.width / 2.0)) <= self._cursor_px
                and abs(cy - (r.y + r.height / 2.0)) <= self._cursor_px
            ):
                near.append(obj.object_id)

        return tuple(near)

    def build(
        self,
        *,
        objects: List[VisualObject],
        cursor: Tuple[int, int] | None = None,
    ) -> EnvironmentState:
        if objects is None:
            raise RuntimeError("objects is None")

        relations = self._spatial_relations(objects)
        focused = self._focus_candidate(objects)

        cursor_ids: Tuple[int, ...] = ()
        if cursor is not None:
            cursor_ids = self._cursor_proximity(objects, cursor)

        return EnvironmentState(
            objects=list(objects),
            relations=relations,
            focused_object_id=focused,
            cursor_object_ids=cursor_ids,
            timestamp_monotonic=time.monotonic(),
      )
