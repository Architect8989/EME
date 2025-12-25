"""
Delta = factual description of what changed between two observations.

Rules:
- Append-only (never mutated after creation)
- Serializable
- No interpretation, no guesses, no AI
"""

from dataclasses import dataclass, field
from typing import Dict, Any
import copy


@dataclass(frozen=True)
class Delta:
    data: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not bool(self.data)

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.data)

    def __repr__(self) -> str:
        return f"Delta({self.data})"
