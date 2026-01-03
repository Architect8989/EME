from typing import Dict, Any, Tuple


def evaluate_causality(
    delta: Dict[str, Any],
    time_window: Tuple[float, float],
    pre_ts: float,
    post_ts: float,
    max_expected_change: float = 0.25,
) -> Dict[str, Any]:
    """
    Returns an attribution record. Never raises.

    Fields:
      attributed: bool
      reason: str
    """

    try:
        if not isinstance(time_window, tuple) or len(time_window) != 2:
            return {
                "attributed": False,
                "reason": "invalid_time_window",
            }

        action_start, action_end = time_window

        # Missing or malformed delta → cannot decide
        if not isinstance(delta, dict):
            return {
                "attributed": False,
                "reason": "no_delta",
            }

        pixels_changed = delta.get("pixels_changed")
        percent_changed = delta.get("percent_changed", 0.0)

        # No observable change
        if not isinstance(pixels_changed, int) or pixels_changed <= 0:
            return {
                "attributed": False,
                "reason": "no_observable_change",
            }

        # Change occurred entirely before the action
        if post_ts < action_start:
            return {
                "attributed": False,
                "reason": "change_precedes_action",
            }

        # Change outside plausible action window
        if pre_ts > action_end:
            return {
                "attributed": False,
                "reason": "change_outside_window",
            }

        # Excessive change for a single primitive action
        if not isinstance(percent_changed, (int, float)):
            return {
                "attributed": False,
                "reason": "invalid_delta",
            }

        if percent_changed > max_expected_change:
            return {
                "attributed": False,
                "reason": "excessive_change_outlier",
            }

        # Passed minimal sanity checks
        return {
            "attributed": True,
            "reason": "plausible_within_window",
        }

    except Exception:
        return {
            "attributed": False,
            "reason": "causality_evaluator_failure",
        }
