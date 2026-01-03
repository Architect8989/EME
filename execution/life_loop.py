import time
import threading
import hashlib
from typing import Optional

from core.logger import Logger, log_event, log_crash
from perception.screen_adapter import ScreenAdapter
from core.delta import Delta
from evaluation.causality import evaluate_causality


class Timeout(Exception):
    pass


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
    Zero-tolerance execution loop.

    Contract:
    observe → act → observe → diff → verify → log → stop-on-failure
    """

    MAX_TOKENS = 3

    def __init__(self, executor, logger: Logger):
        self._executor = executor
        self._logger = logger
        self._screen = ScreenAdapter()

        self._tokens_remaining = self.MAX_TOKENS
        self._frozen = False
        self._last_hash = ""

    def is_frozen(self) -> bool:
        return self._frozen

    def run_experiment(self, action):
        if self._frozen:
            raise Unverified("life loop frozen")

        if self._tokens_remaining <= 0:
            self._frozen = True
            raise Unverified("energy exhausted")

        self._tokens_remaining -= 1
        log_event("experiment.begin", {"tokens_remaining": self._tokens_remaining})

        start_ts = time.monotonic()
        verdict = "UNVERIFIED"
        error = None
        record = None

        try:
            # OBSERVE (pre)
            pre = self._screen.capture()

            # EXECUTE
            result = self._executor.execute(action)

            # OBSERVE (post)
            post = self._screen.capture()

            # DIFF
            diff = self._screen.diff(pre, post)
            delta = Delta(diff)

            # CAUSALITY (boolean, not score)
            causality = evaluate_causality(
                delta=delta.to_dict(),
                time_window=(start_ts, time.monotonic()),
                pre_ts=pre.timestamp_monotonic,
                post_ts=post.timestamp_monotonic,
            )

            if not causality.get("attributed", False):
                raise Unverified(causality.get("reason", "causality_failed"))

            verdict = "VERIFIED"

        except Unverified as e:
            error = str(e)
            verdict = "UNVERIFIED"
            self._frozen = True

        except Exception as e:
            error = repr(e)
            verdict = "ERROR"
            self._frozen = True

        # RECORD (always)
        record = {
            "type": "experiment",
            "verdict": verdict,
            "error": error,
            "duration": time.monotonic() - start_ts,
            "tokens_remaining": self._tokens_remaining,
            "frozen": self._frozen,
        }

        record_hash = _hash_record(self._last_hash, record)
        record["record_hash"] = record_hash
        record["prev_hash"] = self._last_hash
        self._last_hash = record_hash

        try:
            self._logger.record(record)
            log_event(f"experiment.{verdict.lower()}")
        except Exception as e:
            log_crash("logging failure", {"error": repr(e)})
            self._frozen = True
            raise

        if verdict != "VERIFIED":
            raise Unverified(f"experiment failed: {error}")

        return record
