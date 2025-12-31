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
from typing import Optional

from core.logger import Logger, log_event, log_crash
from perception.screen_adapter import ScreenAdapter
from core.delta import Delta
from evaluation.causality import evaluate_causality


class Timeout(Exception):
    pass


class Unverified(Exception):
    pass


def run_with_timeout(fn, timeout_s: float):
    """⚠️ WARNING: Thread timeouts are unsafe for OS-level operations.
       Only use for non-OS, pure Python operations."""
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
    """Load raw frame with safety checks for incomplete writes.
       ⚠️ WARNING: File I/O under real desktop load can cause jitter.
       Replace with in-memory diff after stabilization."""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            with open(path, "rb") as f:
                raw = f.read()

            expected = width * height * 4
            if len(raw) != expected:
                if attempt < max_attempts - 1:
                    time.sleep(0.01)  # Brief pause for filesystem sync
                    continue
                raise RuntimeError(f"frame size mismatch {len(raw)} != {expected}")

            arr = np.frombuffer(raw, dtype=np.uint8)
            return arr.reshape((height, width, 4))
        except (IOError, OSError) as e:
            if attempt < max_attempts - 1:
                time.sleep(0.01)
                continue
            raise RuntimeError(f"failed to load frame after {max_attempts} attempts: {e}")


def _pixel_diff(pre, post):
    """Calculate pixel difference with retry logic for file loading."""
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
        "percent_changed": float(pixels_changed / pixels_total) if pixels_total > 0 else 0.0,
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
    # Class constants (shared, immutable)
    SCREEN_TIMEOUT = 5
    ACTION_TIMEOUT = 3
    LOG_TIMEOUT = 3
    STRONG_CAUSALITY = 0.80  # refuse anything weaker
    MAX_TOKENS = 3  # Energy budget per reset

    def __init__(self, action_executor, logger: Logger):
        self._screen = ScreenAdapter()
        self._executor = action_executor
        self._logger = logger
        
        # ⚠️ CRITICAL: Instance-scoped safety states
        self.observe_only = True  # Instance-scoped for newborn phase
        self._tokens_remaining = self.MAX_TOKENS  # Instance-scoped energy physics
        self._frozen = False  # Instance-scoped freeze state
        self.last_record_hash = ""  # Instance-scoped hash chain

    def _assert_preconditions(self, pre_frame, intent):
        if "expects" not in intent or "present" not in intent["expects"]:
            raise Unverified("intent missing precondition spec")

        for selector in intent["expects"]["present"]:
            if not self._screen.contains(pre_frame, selector):
                raise Unverified(f"precondition not found on screen: {selector}")

    def _verify_delta(self, diff, intent):
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

    def is_frozen(self) -> bool:
        """Check if loop is in frozen state."""
        return self._frozen

    def reset(self) -> bool:
        """Manual reset to clear frozen state and replenish tokens."""
        if not self._frozen:
            return False  # Only allow reset when frozen
        
        self._frozen = False
        self._tokens_remaining = self.MAX_TOKENS
        log_event("life_loop.reset")
        return True

    def run_experiment(self, action):
        """Main execution with safety gates."""
        
        # GATE 0: Check frozen state (surprise = death)
        if self._frozen:
            raise Unverified("loop is frozen - manual reset required")

        # GATE 1: Observe-only mode for newborn phase
        if self.observe_only:
            # Still capture and log, but refuse action
            log_event("experiment.blocked.observe_only")
            pre = self._screen.capture()  # No timeout for newborn phase
            post = self._screen.capture()
            
            record = {
                "type": "observation_only",
                "verdict": "OBSERVED",
                "error": "action blocked: observe-only mode",
                "duration": 0.0,
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
                "prev_hash": self.last_record_hash,
            }
            
            record_hash = _hash_record(self.last_record_hash, record)
            record["record_hash"] = record_hash
            self.last_record_hash = record_hash
            
            try:
                self._logger.record(record)
            except Exception as e:
                log_crash("logging failed", {"error": str(e)})
                self._frozen = True  # Freeze on logging failure
            
            return record

        # GATE 2: Token/energy gate
        if self._tokens_remaining <= 0:
            self._frozen = True
            raise Unverified("energy depleted - manual reset required")
        
        self._tokens_remaining -= 1  # Consume token regardless of outcome
        log_event("experiment.begin", {"tokens_remaining": self._tokens_remaining})

        start = time.perf_counter()
        verdict = "UNVERIFIED"  # Default pessimistic verdict
        err = None
        result = None
        record = None

        try:
            # OBSERVE (pre) - No thread timeout for safety
            pre = self._screen.capture()

            # INTENT REQUIRED
            if not hasattr(action, "intent"):
                raise Unverified("action missing intent")

            # PRECONDITIONS
            self._assert_preconditions(pre, action.intent)

            # ACT - No thread timeout (⚠️ dangerous but necessary for newborn)
            # TODO: Replace with subprocess isolation in v2
            try:
                result = self._executor.execute(action)
            except Exception as e:
                err = str(e)
                verdict = "FAILED"

            # OBSERVE (post)
            post = self._screen.capture()

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
                raise Unverified(f"causality too weak: {causality.get('score', 0.0)}")

            verdict = "VERIFIED" if not err else "FAILED"

        except Unverified as e:
            err = str(e)
            verdict = "UNVERIFIED"
            self._frozen = True  # ⚠️ CRITICAL: Freeze on any unverified state
        except Timeout as e:
            err = str(e)
            verdict = "TIMEOUT"
            self._frozen = True  # ⚠️ CRITICAL: Freeze on timeout
        except Exception as e:
            err = str(e)
            verdict = "ERROR"
            self._frozen = True  # ⚠️ CRITICAL: Freeze on unexpected error

        # ALWAYS LOG (success or failure)
        record = {
            "type": "experiment",
            "verdict": verdict,
            "error": err,
            "result": repr(result) if result else None,
            "duration": time.perf_counter() - start,
            "pre": {
                "path": str(pre.path) if 'pre' in locals() else None,
                "checksum": pre.checksum if 'pre' in locals() else None,
                "ts": pre.timestamp_monotonic if 'pre' in locals() else None,
            } if 'pre' in locals() else None,
            "post": {
                "path": str(post.path) if 'post' in locals() else None,
                "checksum": post.checksum if 'post' in locals() else None,
                "ts": post.timestamp_monotonic if 'post' in locals() else None,
            } if 'post' in locals() else None,
            "delta": delta.to_dict() if 'delta' in locals() else None,
            "causality": causality if 'causality' in locals() else None,
            "prev_hash": self.last_record_hash,
            "tokens_remaining": self._tokens_remaining,
            "frozen": self._frozen,
        }

        # CHAINED INTEGRITY
        record_hash = _hash_record(self.last_record_hash, record)
        record["record_hash"] = record_hash
        self.last_record_hash = record_hash

        try:
            # Keep timeout for logging only (non-OS operation)
            run_with_timeout(lambda: self._logger.record(record), self.LOG_TIMEOUT)
            log_event(f"experiment.{verdict.lower()}")
        except Exception as e:
            log_crash("logging failed", {"error": str(e)})
            self._frozen = True  # Freeze even if logging fails

        # HARD GATE: ONLY VERIFIED ALLOWS CONTINUATION
        if verdict != "VERIFIED":
            # Already frozen above, just raise
            raise Unverified(f"step not verified: {verdict} - {err}")

        return record
