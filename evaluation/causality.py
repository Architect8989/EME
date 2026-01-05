from typing import Dict, Any, Tuple
from core.poison import Poison


def evaluate_causality(
    *,
    delta: Dict[str, Any],
    time_window: Tuple[float, float],
    pre_ts: float,
    post_ts: float,
) -> bool:
    # Hard validation
    if not isinstance(delta, dict):
        Poison.trigger("invalid delta")

    if not isinstance(time_window, tuple) or len(time_window) != 2:
        Poison.trigger("invalid time_window")

    if not isinstance(pre_ts, (int, float)) or not isinstance(post_ts, (int, float)):
        Poison.trigger("invalid timestamps")

    start, end = time_window
    if start > end:
        Poison.trigger("inverted time_window")

    pixels_changed = delta.get("pixels_changed")
    percent_changed = delta.get("percent_changed")

    if not isinstance(pixels_changed, int):
        Poison.trigger("pixels_changed invalid")

    if not isinstance(percent_changed, (int, float)):
        Poison.trigger("percent_changed invalid")

    if pixels_changed <= 0:
        return False

    if percent_changed <= 0.0:
        return False

    if post_ts < start or pre_ts > end:
        return False

    return True
