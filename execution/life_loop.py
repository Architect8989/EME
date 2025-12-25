import time
import hashlib

from core.logger import Logger, log_crash, log_event
from perception.screenshot import capture_screen


class LifeLoop:
    """
    Infrastructure gatekeeper.
    Executes one action. Measures reality. Refuses to lie.
    """

    def __init__(self, action_executor, logger: Logger):
        if not hasattr(action_executor, "execute"):
            raise TypeError("action_executor must implement execute()")

        if not hasattr(logger, "record"):
            raise TypeError("logger must implement record()")

        self._action_executor = action_executor
        self._logger = logger

    def run_experiment(self, action):
        log_event("experiment.begin")

        experiment_id = self._generate_experiment_id()

        # ---- PERCEPTION: BEFORE ----
        pre_snap = capture_screen(experiment_id)

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

        # ---- PERCEPTION: AFTER ----
        post_snap = capture_screen(experiment_id)

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
                "timestamp": pre_snap.timestamp,
                "width": pre_snap.width,
                "height": pre_snap.height
            },

            "post_snapshot": {
                "path": str(post_snap.path),
                "timestamp": post_snap.timestamp,
                "width": post_snap.width,
                "height": post_snap.height
            },
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
