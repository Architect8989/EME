# core/system_state.py

import threading

class SystemStateError(Exception):
    pass


class SystemState:
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def mark_initialized(cls):
        with cls._lock:
            if cls._initialized:
                raise SystemStateError("System already initialized")
            cls._initialized = True

    @classmethod
    def assert_initialized(cls):
        if not cls._initialized:
            raise SystemStateError("System not initialized via bootstrap")
