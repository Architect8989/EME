"""
LIFE LOOP — FROZEN EXECUTION LAYER

One experiment:
1) capture pre-screen
2) execute exactly one action
3) capture post-screen
4) compute pixel delta
5) evaluate causality
6) log the record

No AI. No guessing. No normalization. No retries.
"""

import time
import hashlib
import numpy as np

from core.logger import Logger, log_crash, log_event
from perception.screen_adapter import ScreenAdapter, ScreenSnapshot
from core.delta import Delta
from evaluation.causality import evaluate_causality


def _load_raw_frame(path: str, width: int, height: int):
    """Load raw BGRA frame from disk exactly as written."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception as e:
        raise RuntimeError(f"Failed reading snapshot: {e}")

    expected = width * height * 4
    if len(raw) != expected:
        raise RuntimeError(
            f"Frame size mismatch: expected {expected} bytes, got {len(raw)}"
        )

    arr = np.frombuffer(raw, dtype=np.uint8)
    arr = arr.reshape((height, width, 4))
    return arr


def _compute_delta(pre: ScreenSnapshot, post: ScreenSnapshot):
    """
    Strict pixel delta.
    No semantics. No filters. No smoothing.
    """

    pre_arr = _load_raw_frame(pre.path, pre.width, pre.height)
    post_arr = _load_raw_frame(post.path, post.width, post.height)

    if pre_arr.shape != post_arr.shape:
        raise RuntimeError("Snapshot dimension mismatch")

    diff = np.any(pre_arr != post_arr, axis=2)
    pixels_total = diff.size
    pixels_changed = int(np.count_nonzero(diff))

    if pixels_total == 0:
        raise RuntimeError("Zero-sized frame")

    # bounding box of change
    if pixels_changed > 0:
        ys, xs = np.where(diff)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    else:
        bbox = None

    return {
        "error": None,
        "pre_checksum": pre.checksum,
        "post_checksum": post.checksum,
        "pixels_total": int(pixels_total),
        "pixels_changed": pixels_changed,
        "percent_changed": float(pixels_changed / pixels_total),
        "bbox": bbox,
    }


class LifeLoop:
    """
    Executes one action.
    Measures reality.
    Refuses to lie.
    """

    def __init__(self, action_executor, logger: Logger):
        if not hasattr(action_executor, "execute") or not callable(action_executor.execute):
            raise TypeError("action_executor must implement execute()")

        if not hasattr(logger, "record") or not callable(logger.record):
            raise TypeError("logger must implement record()")

        self._action_executor = action_executor
        self._logger = logger
        self._screen = ScreenAdapter()

    def run_experiment(self, action):
        log_event("experiment.begin")

        experiment_id = self._generate_experiment_id()

        # ---- PRE SNAPSHOT ----
        pre_snap = self._screen.capture()

        start = time.perf_counter()
        result = None
        err = None

        try:
            log_event("experiment.dispatch")
            result = self._action_executor.execute(action)
        except Exception as e:
            err = str(e)
            log_event("experiment.failure")

        end = time.perf_counter()

        # ---- POST SNAPSHOT ----
        post_snap = self._screen.capture()

        # ---- DELTA ----
        delta_data = _compute_delta(pre_snap, post_snap)
        delta = Delta(delta_data)

        # ---- CAUSALITY ----
        causality = evaluate_causality(
            delta=delta.to_dict(),
            time_window=(start, end),
            pre_ts=pre_snap.timestamp_monotonic,
            post_ts=post_snap.timestamp_monotonic,
        )

        record = {
            "experiment_id": experiment_id,
            "action_id": getattr(action, "id", "unknown"),

            "start_timestamp": start,
            "end_timestamp": end,
            "duration": end - start,

            "raw_result": repr(result),
            "raw_error": err,

            "pre_snapshot": {
                "path": str(pre_snap.path),
                "timestamp": pre_snap.timestamp_monotonic,
                "width": pre_snap.width,
                "height": pre_snap.height,
                "checksum": pre_snap.checksum,
            },

            "post_snapshot": {
                "path": str(post_snap.path),
                "timestamp": post_snap.timestamp_monotonic,
                "width": post_snap.width,
                "height": post_snap.height,
                "checksum": post_snap.checksum,
            },

            "delta": delta.to_dict(),
            "causality": causality,
        }

        try:
            self._logger.record(record)
            log_event("experiment.recorded")
        except Exception as e:
            log_crash(f"LOGGING FAILED: {e}")
            raise

        log_event("experiment.complete")
        return record

    def _generate_experiment_id(self):
        t = time.perf_counter_ns()
        return hashlib.sha256(str(t).encode()).hexdigest()[:16]
