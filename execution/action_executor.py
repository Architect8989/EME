"""
Action Executor — smallest possible surface.
Executes exactly one action. Nothing else.
"""

from core.logger import log_event


class ActionExecutor:
    def __init__(self):
        pass

    def execute(self, action):
        if not hasattr(action, "execute") or not callable(action.execute):
            raise TypeError("action must implement execute()")

        log_event("action.begin", {"action": type(action).__name__})
        result = action.execute()
        log_event("action.end", {"action": type(action).__name__})

        return result
