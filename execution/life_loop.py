"""
Life Loop — single-step, deterministic, fail-fast.
"""

import time
import signal
import threading
from dataclasses import dataclass

import numpy as np

from core.logger import log_event, log_crash, Logger
from perception.screen_adapter import ScreenAdapter
from core.delta import Delta
from evaluation.causality import evaluate_causality


class Timeout(Exception):
    pass


def run_with_timeout(fn, timeout_s):
    result = {"value": None, "error": None}

    def target():
        try:
            result["value"] = fn()
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout_s)

    if t.is_alive():
        raise Timeout(f"operation exceeded {timeout_s}s")

    if result["error"]:
        raise result["error"]

    return result["value"]


def _load_raw_frame(path: str, width: int, height: int):
    with open(path, "rb") as f:
        raw = f.read()

    expected = width * height * 4
    if len(raw) != expected:
        raise RuntimeError(f"Frame size mismatch {len(raw)} != {expected}")

    arr = np.frombuffer(raw, dtype=np.uint8)
    return arr.reshape((height, width, 4))


def _compute_delta(pre, post):
    pre_arr = _load_raw_frame(pre.path, pre.width, pre.height)
    post_arr = _load_raw_frame(post.path, post.width, post.height)

    if pre_arr.shape != post_arr.shape:
        raise RuntimeError("Snapshot dimension mismatch")

    diff = np.any(pre_arr != post_arr, axis=2)
    pixels_total = diff.size
    pixels_changed = int(np.count_nonzero(diff))

    if pixels_total == 0:
        raise RuntimeError("Zero-sized frame")

    if pixels_changed:
        ys, xs = np.where(diff)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    else:
        bbox = None

    return {
        "error": None,
        "pixels_total": int(pixels_total),
        "pixels_changed": pixels_changed,
        "percent_changed": float(pixels_changed / pixels_total),
        "bbox": bbox,
    }


class LifeLoop:
    """
    Observe → act once → verify → log.
    No guesses. No retries. No loops.
    """

    SCREEN_TIMEOUT = 5
    ACTION_TIMEOUT = 3

    def __init__(self, action_executor, logger: Logger):
        self._screen = ScreenAdapter()
        self._action_executor = action_executor
        self._logger = logger

    def run_experiment(self, action):
        log_event("experiment.begin")

        start = time.perf_counter()

        pre = run_with_timeout(self._screen.capture, self.SCREEN_TIMEOUT)

        err = None
        result = None

        try:
            log_event("experiment.dispatch")
            result = run_with_timeout(
                lambda: self._action_executor.execute(action),
                self.ACTION_TIMEOUT,
            )
        except Exception as e:
            err = str(e)
            log_event("experiment.failure")

        post = run_with_timeout(self._screen.capture, self.SCREEN_TIMEOUT)

        delta_data = _compute_delta(pre, post)
        delta = Delta(delta_data)

        causality = evaluate_causality(
            delta=delta.to_dict(),
            time_window=(start, time.perf_counter()),
            pre_ts=pre.timestamp_monotonic,
            post_ts=post.timestamp_monotonic,
        )

        record = {
            "start": start,
            "duration": time.perf_counter() - start,
            "raw_result": repr(result),
            "raw_error": err,
            "pre": {
                "path": str(pre.path),
                "checksum": pre.checksum,
                "ts": pre.timestamp_monotonic,
            },
            "post": {
                "path": str(post.path),
                "checksum": post.checksum,
                "ts": post.timestamp_monotonic,
            },
            "delta": delta.to_dict(),
            "causality": causality,
        }

        try:
            self._logger.record(record)
            log_event("experiment.complete")
        except Exception as e:
            log_crash(f"LOGGING FAILED: {e}")
            raise

        return record
