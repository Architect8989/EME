"""
Life Loop — deterministic, single-step.
Observe → act → verify → log → stop.
"""

import time
import threading
import numpy as np

from core.logger import Logger, log_event, log_crash
from perception.screen_adapter import ScreenAdapter
from core.delta import Delta
from evaluation.causality import evaluate_causality


class Timeout(Exception):
    pass


def run_with_timeout(fn, timeout_s: float):
    container = {"value": None, "error": None}

    def target():
        try:
            container["value"] = fn()
        except Exception as e:
            container["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout_s)

    if t.is_alive():
        raise Timeout(f"operation exceeded {timeout_s}s")

    if container["error"]:
        raise container["error"]

    return container["value"]


def _load_raw_frame(path: str, width: int, height: int):
    with open(path, "rb") as f:
        raw = f.read()

    expected = width * height * 4
    if len(raw) != expected:
        raise RuntimeError(f"frame size mismatch {len(raw)} != {expected}")

    arr = np.frombuffer(raw, dtype=np.uint8)
    return arr.reshape((height, width, 4))


def _compute_delta(pre, post):
    pre_arr = _load_raw_frame(pre.path, pre.width, pre.height)
    post_arr = _load_raw_frame(post.path, post.width, post.height)

    if pre_arr.shape != post_arr.shape:
        raise RuntimeError("snapshot dimension mismatch")

    diff = np.any(pre_arr != post_arr, axis=2)

    pixels_total = diff.size
    pixels_changed = int(np.count_nonzero(diff))

    if pixels_total == 0:
        raise RuntimeError("zero-sized frame")

    if pixels_changed:
        ys, xs = np.where(diff)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    else:
        bbox = None

    return {
        "pixels_total": int(pixels_total),
        "pixels_changed": pixels_changed,
        "percent_changed": float(pixels_changed / pixels_total),
        "bbox": bbox,
    }


class LifeLoop:
    SCREEN_TIMEOUT = 5
    ACTION_TIMEOUT = 3
    LOG_TIMEOUT = 3

    def __init__(self, action_executor, logger: Logger):
        self._screen = ScreenAdapter()
        self._executor = action_executor
        self._logger = logger

    def run_experiment(self, action):
        log_event("experiment.begin")

        start = time.perf_counter()

        pre = run_with_timeout(self._screen.capture, self.SCREEN_TIMEOUT)

        err = None
        result = None

        try:
            result = run_with_timeout(
                lambda: self._executor.execute(action),
                self.ACTION_TIMEOUT,
            )
        except Exception as e:
            err = str(e)
            log_event("experiment.failure", {"error": err})

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
            "type": "experiment",
            "error": err,
            "result": repr(result),
            "duration": time.perf_counter() - start,
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
            run_with_timeout(lambda: self._logger.record(record), self.LOG_TIMEOUT)
            log_event("experiment.complete")
        except Exception as e:
            log_crash("logging failed", {"error": str(e)})
            raise

        return record
