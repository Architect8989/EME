from typing import Dict, Tuple
import time


class EphemeralMemory:
    """
    In-run, ephemeral memory.

    Purpose:
    - Store short-lived associations during a single life
    - Track object-related hypotheses and interaction outcomes
    - Enable learning within one run only

    Hard invariants:
    - No OS access
    - No backend / executor access
    - No persistence
    - Cleared on process exit
    """

    def __init__(self) -> None:
        # object_id -> affordance kind -> confidence
        self._affordance_confidence: Dict[int, Dict[str, float]] = {}

        # object_id -> last interaction timestamp (monotonic)
        self._last_interaction_ts: Dict[int, float] = {}

        # object_id -> success / failure counts
        self._outcomes: Dict[int, Tuple[int, int]] = {}

    # ─────────────────────────────────────────────
    # Affordance confidence tracking
    # ─────────────────────────────────────────────

    def get_affordance_confidence(
        self, object_id: int, kind: str
    ) -> float:
        return self._affordance_confidence.get(object_id, {}).get(kind, 0.0)

    def update_affordance_confidence(
        self,
        *,
        object_id: int,
        kind: str,
        delta: float,
    ) -> None:
        if object_id not in self._affordance_confidence:
            self._affordance_confidence[object_id] = {}

        prev = self._affordance_confidence[object_id].get(kind, 0.0)
        new = max(0.0, min(1.0, prev + delta))
        self._affordance_confidence[object_id][kind] = new

    # ─────────────────────────────────────────────
    # Interaction outcomes
    # ─────────────────────────────────────────────

    def record_interaction(
        self,
        *,
        object_id: int,
        success: bool,
    ) -> None:
        ok, fail = self._outcomes.get(object_id, (0, 0))
        if success:
            ok += 1
        else:
            fail += 1

        self._outcomes[object_id] = (ok, fail)
        self._last_interaction_ts[object_id] = time.monotonic()

    def success_rate(self, object_id: int) -> float:
        ok, fail = self._outcomes.get(object_id, (0, 0))
        total = ok + fail
        if total == 0:
            return 0.0
        return ok / total

    # ─────────────────────────────────────────────
    # Temporal decay / freshness
    # ─────────────────────────────────────────────

    def time_since_last_interaction(self, object_id: int) -> float | None:
        ts = self._last_interaction_ts.get(object_id)
        if ts is None:
            return None
        return time.monotonic() - ts

    # ─────────────────────────────────────────────
    # Maintenance
    # ─────────────────────────────────────────────

    def forget_object(self, object_id: int) -> None:
        self._affordance_confidence.pop(object_id, None)
        self._outcomes.pop(object_id, None)
        self._last_interaction_ts.pop(object_id, None)

    def reset(self) -> None:
        """
        Clear all in-run memory.
        Intended only for controlled restart inside a single life,
        not for persistence across runs.
        """
        self._affordance_confidence.clear()
        self._outcomes.clear()
        self._last_interaction_ts.clear()
