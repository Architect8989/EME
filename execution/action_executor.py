from core.logger import log_event


class ActionExecutor:
    def __init__(self, guard):
        self._guard = guard

    def execute(self, action):
        if self._guard.is_frozen():
            raise RuntimeError("executor blocked: system frozen")

        if not hasattr(action, "execute") or not callable(action.execute):
            raise TypeError("action must implement execute()")

        if not getattr(action, "atomic", False):
            raise RuntimeError("executor refused: action not declared atomic")

        log_event("action.begin", {"action": type(action).__name__})

        try:
            result = action.execute()
        except Exception:
            self._guard.emergency_stop("action execution failed")
            raise
        finally:
            log_event("action.end", {"action": type(action).__name__})

        return result
