"""
Life Loop — zero-tolerance.

Contract:
observe → intent → action → verify → log → stop
If anything cannot be proven → UNVERIFIED → hard stop.
"""

import time
import threading
import hashlib
import numpy as np

from core.logger import Logger, log_event, log_crash
from perception.screen_adapter import ScreenAdapter
from core.delta import Delta
from evaluation.causality import evaluate_causality


class Timeout(Exception):
    pass


class Unverified(Exception):
    pass


def run_with_timeout(fn, timeout_s: float):
    box = {"value": None, "error": None}

    def target():
        try:
            box["value"] = fn()
        except Exception as e:
            box["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout_s)

    if t.is_alive():
        raise Timeout(f"operation exceeded {timeout_s}s")

    if box["error"]:
        raise box["error"]

    return box["value"]


def _load_raw_frame(path: str, width: int, height: int):
    with open(path, "rb") as f:
        raw = f.read()

    expected = width * height * 4
    if len(raw) != expected:
        raise RuntimeError(f"frame size mismatch {len(raw)} != {expected}")

    arr = np.frombuffer(raw, dtype=np.uint8)
    return arr.reshape((height, width, 4))


def _pixel_diff(pre, post):
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
        "mask": diff,
    }


def _hash_record(prev_hash: str, record: dict) -> str:
    h = hashlib.sha256()
    if prev_hash:
        h.update(prev_hash.encode("utf-8"))
    h.update(repr(record).encode("utf-8"))
    return h.hexdigest()


class LifeLoop:
    SCREEN_TIMEOUT = 5
    ACTION_TIMEOUT = 3
    LOG_TIMEOUT = 3

    STRONG_CAUSALITY = 0.80  # refuse anything weaker
    last_record_hash = ""

    def __init__(self, action_executor, logger: Logger):
        self._screen = ScreenAdapter()
        self._executor = action_executor
        self._logger = logger

    def _assert_preconditions(self, pre_frame, intent):
        # Intent must define what it expects to see BEFORE acting
        # Example contract fields:
        # intent["expects"]["present"] = list of UI selectors or regions
        if "expects" not in intent or "present" not in intent["expects"]:
            raise Unverified("intent missing precondition spec")

        for selector in intent["expects"]["present"]:
            if not self._screen.contains(pre_frame, selector):
                raise Unverified(f"precondition not found on screen: {selector}")

    def _verify_delta(self, diff, intent):
        # Intent must define expected delta region and/or property
        if "delta" not in intent:
            raise Unverified("intent missing delta spec")

        delta_spec = intent["delta"]

        # Region-based proof
        if "bbox" in delta_spec and delta_spec["bbox"]:
            exp = delta_spec["bbox"]
            got = diff["bbox"]
            if not got:
                raise Unverified("no visible change detected")
            # Require overlap, not exact equality
            gx1, gy1, gx2, gy2 = got
            ex1, ey1, ex2, ey2 = exp
            overlap = not (gx2 < ex1 or ex2 < gx1 or gy2 < ey1 or ey2 < gy1)
            if not overlap:
                raise Unverified("change occurred outside expected region")

        # Minimum change threshold
        if "min_percent" in delta_spec:
            if diff["percent_changed"] < float(delta_spec["min_percent"]):
                raise Unverified("insufficient visual change")

    def run_experiment(self, action):
        # action contract:
        # action.intent — describes preconditions + expected delta
        # action.payload — what to execute
        log_event("experiment.begin")

        start = time.perf_counter()
        verdict = "UNSET"
        err = None
        result = None

        # OBSERVE (pre)
        pre = run_with_timeout(self._screen.capture, self.SCREEN_TIMEOUT)

        # INTENT REQUIRED
        if not hasattr(action, "intent"):
            raise Unverified("action missing intent")

        # PRECONDITIONS
        self._assert_preconditions(pre, action.intent)

        # ACT
        try:
            result = run_with_timeout(
                lambda: self._executor.execute(action),
                self.ACTION_TIMEOUT,
            )
        except Exception as e:
            err = str(e)

        # OBSERVE (post)
        post = run_with_timeout(self._screen.capture, self.SCREEN_TIMEOUT)

        # DIFF
        diff = _pixel_diff(pre, post)
        delta = Delta(
            {
                "pixels_total": diff["pixels_total"],
                "pixels_changed": diff["pixels_changed"],
                "percent_changed": diff["percent_changed"],
                "bbox": diff["bbox"],
            }
        )

        # VERIFY DELTA AGAINST INTENT
        self._verify_delta(diff, action.intent)

        # CAUSALITY
        causality = evaluate_causality(
            delta=delta.to_dict(),
            time_window=(start, time.perf_counter()),
            pre_ts=pre.timestamp_monotonic,
            post_ts=post.timestamp_monotonic,
        )

        if causality.get("score", 0.0) < self.STRONG_CAUSALITY:
            raise Unverified("causality too weak")

        verdict = "VERIFIED" if not err else "FAILED"

        record = {
            "type": "experiment",
            "verdict": verdict,
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
            "prev_hash": self.last_record_hash,
        }

        # CHAINED INTEGRITY
        record_hash = _hash_record(self.last_record_hash, record)
        record["record_hash"] = record_hash
        self.last_record_hash = record_hash

        # HARD GATE: ONLY VERIFIED MOVES FORWARD
        if verdict != "VERIFIED":
            log_event("experiment.unverified", {"error": err})
            raise Unverified("step not verified")

        try:
            run_with_timeout(lambda: self._logger.record(record), self.LOG_TIMEOUT)
            log_event("experiment.complete")
        except Exception as e:
            log_crash("logging failed", {"error": str(e)})
            raise

        return record
