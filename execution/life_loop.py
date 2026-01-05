import time
import hashlib

from core.poison import Poison
from core.logger import log_event, log_crash
from perception.screen_adapter import ScreenAdapter, Frame
from evaluation.causality import evaluate_causality
from perception.delta import compute_delta


class Unverified(Exception):
    pass


def _hash_record(prev_hash: str, record: dict) -> str:
    h = hashlib.sha256()
    if prev_hash:
        h.update(prev_hash.encode("utf-8"))
    h.update(repr(record).encode("utf-8"))
    return h.hexdigest()


class LifeLoop:
    """
    Single-pass execution verifier.

    Mechanical invariants:
    - Exactly one action
    - Exactly two observations (pre/post)
    - No retries
    - No loops
    - Any ambiguity poisons immediately
    """

    __slots__ = ("_executor", "_screen", "_last_hash")

    def __init__(self, executor) -> None:
        Poison.assert_clean()
        self._executor = executor
        self._screen = ScreenAdapter()
        self._last_hash = ""

    def run_experiment(self, action) -> dict:
        Poison.assert_clean()

        start_ts = time.monotonic()
        verdict = "UNVERIFIED"
        error = None

        try:
            log_event("experiment.begin")

            # ──────────────────
            # OBSERVE (PRE)
            # ──────────────────
            pre_res = self._executor.backend.screenshot(
                _executor_token=self._executor.token
            )

            if not pre_res.ok:
                Poison.trigger("pre-screenshot failed")

            pre: Frame = self._screen.ingest(
                buffer=pre_res.details["buffer"],
                width=pre_res.details["width"],
                height=pre_res.details["height"],
                pixel_format=pre_res.details["pixel_format"],
            )

            # ──────────────────
            # EXECUTE (SOLE AUTHORITY)
            # ──────────────────
            self._executor.execute(action)

            # ──────────────────
            # OBSERVE (POST)
            # ──────────────────
            post_res = self._executor.backend.screenshot(
                _executor_token=self._executor.token
            )

            if not post_res.ok:
                Poison.trigger("post-screenshot failed")

            post: Frame = self._screen.ingest(
                buffer=post_res.details["buffer"],
                width=post_res.details["width"],
                height=post_res.details["height"],
                pixel_format=post_res.details["pixel_format"],
            )

            # ──────────────────
            # DELTA (DETERMINISTIC, BUFFER-LEVEL)
            # ──────────────────
            delta = compute_delta(
                pre_buffer=pre.buffer,
                post_buffer=post.buffer,
                width=pre.width,
                height=pre.height,
            )

            # ──────────────────
            # CAUSALITY (FAIL-CLOSED)
            # ──────────────────
            causality = evaluate_causality(
                delta=delta,
                time_window=(start_ts, time.monotonic()),
                pre_ts=pre.timestamp_monotonic,
                post_ts=post.timestamp_monotonic,
            )

            if causality.get("attributed") is not True:
                raise Unverified(causality.get("reason", "causality_failed"))

            verdict = "VERIFIED"

        except BaseException as e:
            error = repr(e)
            Poison.trigger(f"life_loop failure: {error}")

        record = {
            "type": "experiment",
            "verdict": verdict,
            "error": error,
            "duration": time.monotonic() - start_ts,
        }

        record_hash = _hash_record(self._last_hash, record)
        record["record_hash"] = record_hash
        record["prev_hash"] = self._last_hash
        self._last_hash = record_hash

        try:
            log_event(f"experiment.{verdict.lower()}")
        except BaseException as e:
            log_crash("logging failure", {"error": repr(e)})
            Poison.trigger(f"logging failure: {repr(e)}")

        if verdict != "VERIFIED":
            Poison.trigger("non-verified execution reached return")

        return record
