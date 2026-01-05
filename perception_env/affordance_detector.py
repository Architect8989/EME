from typing import List

from perception_env.affordance import Affordance
from perception_env.object import VisualObject
from perception_env.env_state import EnvironmentState


class AffordanceDetector:
    """
    Deterministic affordance inference.

    Responsibilities:
    - Infer possible interactions from visual structure
    - Produce hypotheses only (never permissions)
    - No execution, no planning, no OS access

    Invariants:
    - Deterministic for identical input
    - Fail-closed (no affordance is safer than wrong affordance)
    """

    def __init__(
        self,
        *,
        min_click_area: int = 400,
        max_click_area: int = 200_000,
        min_edge_density: float = 0.05,
    ) -> None:
        self._min_click_area = min_click_area
        self._max_click_area = max_click_area
        self._min_edge_density = min_edge_density

    def detect(self, env: EnvironmentState) -> List[Affordance]:
        if env is None:
            raise RuntimeError("environment state is None")

        affordances: List[Affordance] = []

        for obj in env.objects:
            r = obj.latest_region

            # ---- Clickable heuristic ----
            clickable_conf = self._clickable_confidence(obj)
            if clickable_conf > 0.0:
                affordances.append(
                    Affordance(
                        object_id=obj.object_id,
                        kind="clickable",
                        confidence=clickable_conf,
                    )
                )

            # ---- Text input heuristic ----
            text_conf = self._text_input_confidence(obj)
            if text_conf > 0.0:
                affordances.append(
                    Affordance(
                        object_id=obj.object_id,
                        kind="text_input",
                        confidence=text_conf,
                    )
                )

            # ---- Scrollable heuristic ----
            scroll_conf = self._scrollable_confidence(obj)
            if scroll_conf > 0.0:
                affordances.append(
                    Affordance(
                        object_id=obj.object_id,
                        kind="scrollable",
                        confidence=scroll_conf,
                    )
                )

        return affordances

    def _clickable_confidence(self, obj: VisualObject) -> float:
        r = obj.latest_region

        if r.area < self._min_click_area or r.area > self._max_click_area:
            return 0.0

        if r.edge_density < self._min_edge_density:
            return 0.0

        # Stability boosts confidence
        conf = 0.4 + (obj.stability * 0.6)
        return min(1.0, conf)

    def _text_input_confidence(self, obj: VisualObject) -> float:
        r = obj.latest_region

        # Text fields are often wide, low height, rectangular
        aspect = r.width / max(1, r.height)
        if aspect < 2.0:
            return 0.0

        if r.edge_density < 0.1:
            return 0.0

        conf = 0.3 + (obj.stability * 0.5)
        return min(1.0, conf)

    def _scrollable_confidence(self, obj: VisualObject) -> float:
        r = obj.latest_region

        # Scrollbars are tall and thin
        aspect = r.height / max(1, r.width)
        if aspect < 3.0:
            return 0.0

        conf = 0.2 + (obj.stability * 0.4)
        return min(1.0, conf)
