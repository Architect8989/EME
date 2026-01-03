import time
import hashlib

from core.poison import Poison
from core.logger import Logger, log_event, log_crash
from perception.screen_adapter import ScreenAdapter
from core.delta import Delta
from evaluation.causality import evaluate_causality


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
    Single-pass, fail-closed execution driver.

    Mechanical guarantees:
    - No looping
    - No retries
    - No OS termination primitives
    - Poison is the only terminal mechanism
    """

    def __init__(self, executor, logger: Logger):
        Poison.assert_clean()
        self._executor = executor
        self._logger = logger
        self._screen = ScreenAdapter()
        self._last_hash = ""

    def run_experiment(self, action) -> dict:
        Poison.assert_clean()

        start_ts = time.monotonic()
        verdict = "UNVERIFIED"
        error = None

        try:
            log_event("experiment.begin")

            # OBSERVE (pre)
            pre = self._screen.capture()

            # EXECUTE (sole authority)
            self._executor.execute(action)

            # OBSERVE (post)
            post = self._screen.capture()

            # DIFF
            diff = self._screen.diff(pre, post)
            delta = Delta(diff)

            # CAUSALITY (boolean, fail-closed)
            causality = evaluate_causality(
                delta=delta.to_dict(),
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
            self._logger.record(record)
            log_event(f"experiment.{verdict.lower()}")
        except BaseException as e:
            log_crash("logging failure", {"error": repr(e)})
            Poison.trigger(f"logging failure: {repr(e)}")

        if verdict != "VERIFIED":
            Poison.trigger("non-verified execution reached return")

        return record
