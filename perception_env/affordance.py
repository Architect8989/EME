from dataclasses import dataclass
from typing import Literal


AffordanceType = Literal[
    "clickable",
    "text_input",
    "scrollable",
    "draggable",
    "selectable",
]


@dataclass(frozen=True)
class Affordance:
    """
    Interaction hypothesis for a visual object.

    Properties:
    - Hypothesis only (never authorization)
    - Deterministic
    - No execution power
    - No OS / backend access
    """

    object_id: int
    kind: AffordanceType
    confidence: float  # 0.0 – 1.0

    def is_plausible(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold
