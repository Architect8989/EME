from dataclasses import dataclass
from typing import List, Tuple, Dict

from perception_env.object import VisualObject


@dataclass(frozen=True)
class SpatialRelation:
    """
    Simple spatial relation between two objects.
    """
    a_id: int
    b_id: int
    relation: str  # e.g. "contains", "overlaps", "left_of", "above"


@dataclass(frozen=True)
class EnvironmentState:
    """
    Canonical environment state at a moment in time.

    Invariants:
    - Read-only
    - Derived only from visual objects
    - No OS / backend / executor access
    - Deterministic for identical inputs
    """

    objects: List[VisualObject]
    relations: List[SpatialRelation]
    focused_object_id: int | None
    cursor_object_ids: Tuple[int, ...]
    timestamp_monotonic: float

    def object_by_id(self, object_id: int) -> VisualObject | None:
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None

    def objects_with_relation(self, relation: str) -> List[Tuple[VisualObject, VisualObject]]:
        pairs: List[Tuple[VisualObject, VisualObject]] = []
        for rel in self.relations:
            if rel.relation == relation:
                a = self.object_by_id(rel.a_id)
                b = self.object_by_id(rel.b_id)
                if a is not None and b is not None:
                    pairs.append((a, b))
        return pairs
