from typing import Dict, Any, Tuple

from core.poison import Poison


def evaluate_causality(
    delta: Dict[str, Any],
    time_window: Tuple[float, float],
    pre_ts: float,
    post_ts: float,
    max_expected_change: float = 0.25,
) -> Dict[str, Any]:
    if not isinstance(time_window, tuple) or len(time_window) != 2:
        Poison.trigger("invalid time_window")

    if not isinstance(delta, dict):
        Poison.trigger("invalid delta")

    if not isinstance(pre_ts, (int, float)) or not isinstance(post_ts, (int, float)):
        Poison.trigger("invalid timestamps")

    action_start, action_end = time_window

    if not isinstance(action_start, (int, float)) or not isinstance(action_end, (int, float)):
        Poison.trigger("invalid time_window bounds")

    pixels_changed = delta.get("pixels_changed")
    percent_changed = delta.get("percent_changed")

    if not isinstance(pixels_changed, int):
        Poison.trigger("pixels_changed missing or invalid")

    if pixels_changed <= 0:
        return {
            "attributed": False,
            "reason": "no_observable_change",
        }

    if not isinstance(percent_changed, (int, float)):
        Poison.trigger("percent_changed missing or invalid")

    if percent_changed < 0.0:
        Poison.trigger("negative percent_changed")

    if percent_changed > max_expected_change:
        return {
            "attributed": False,
            "reason": "excessive_change",
        }

    if post_ts < action_start:
        return {
            "attributed": False,
            "reason": "change_precedes_action",
        }

    if pre_ts > action_end:
        return {
            "attributed": False,
            "reason": "change_outside_window",
        }

    return {
        "attributed": True,
        "reason": "within_window",
    }
