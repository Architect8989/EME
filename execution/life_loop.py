import time
from core.logger import Logger, log_crash


class LifeLoop:
    def __init__(self, action_executor, logger: Logger):
        if not hasattr(action_executor, "execute"):
            raise TypeError("action_executor must implement execute()")
        if not hasattr(logger, "record"):
            raise TypeError("logger must implement record()")

        self._action_executor = action_executor
        self._logger = logger

    def run_experiment(self, action):
        experiment_id = self._generate_experiment_id()

        start = time.perf_counter()
        result = None
        err = None

        try:
            result = self._action_executor.execute(action)
        except Exception as e:
            err = str(e)

        end = time.perf_counter()

        record = {
            "experiment_id": experiment_id,
            "action_id": getattr(action, "id", "unknown"),
            "start_timestamp": start,
            "end_timestamp": end,
            "duration": end - start,
            "raw_result": repr(result),
            "raw_error": err,
        }

        try:
            self._logger.record(record)
        except Exception as e:
            log_crash(f"LOGGING FAILED: {e}")
            raise

        return record

    def _generate_experiment_id(self):
        import hashlib
        t = time.perf_counter_ns()
        return hashlib.sha256(str(t).encode()).hexdigest()[:16]
