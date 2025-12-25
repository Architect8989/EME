"""
Causality gate.

Answers one question:

Did the observed change plausibly occur *because of* the action,
given the time window and the amount of change?

Never overwrites facts. Only annotates.
"""

from typing import Dict, Any, Tuple


def evaluate_causality(
    delta: Dict[str, Any],
    time_window: Tuple[float, float],
    pre_ts: float,
    post_ts: float,
    max_expected_change: float = 0.25
) -> Dict[str, Any]:
    """
    Returns an attribution record. Never raises.

    Fields:
      attributed: bool
      reason: str
    """

    try:
        action_start, action_end = time_window

        # Missing delta → cannot decide
        if delta is None:
            return {
                "attributed": False,
                "reason": "no_delta"
            }

        # No pixels changed
        if delta.get("pixels_changed") in (0, None):
            return {
                "attributed": False,
                "reason": "no_observable_change"
            }

        # Change happened entirely before action
        if post_ts < action_start:
            return {
                "attributed": False,
                "reason": "change_precedes_action"
            }

        # Change happens impossibly late relative to capture
        if pre_ts > action_end and delta.get("percent_changed", 0) > 0:
            return {
                "attributed": False,
                "reason": "change_outside_window"
            }

        # Outlier: too much change for a single primitive action
        pct = delta.get("percent_changed") or 0.0
        if pct > max_expected_change:
            return {
                "attributed": False,
                "reason": "excessive_change_outlier"
            }

        # Passed minimal sanity checks
        return {
            "attributed": True,
            "reason": "plausible_within_window"
        }

    except Exception as _:
        return {
            "attributed": False,
            "reason": "causality_evaluator_failure"
            }
