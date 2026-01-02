# core/poison.py

import sys
import threading
from typing import Optional


class PoisonError(Exception):
    pass


class Poison:
    _lock = threading.RLock()
    _poisoned: bool = False
    _reason: Optional[str] = None

    @classmethod
    def is_poisoned(cls) -> bool:
        with cls._lock:
            return cls._poisoned

    @classmethod
    def reason(cls) -> Optional[str]:
        with cls._lock:
            return cls._reason

    @classmethod
    def trigger(cls, reason: str):
        with cls._lock:
            if cls._poisoned:
                return

            cls._poisoned = True
            cls._reason = reason

        sys.stderr.write(f"[POISONED] {reason}\n")
        sys.stderr.flush()

        # Hard stop: no recovery, no retries, no continuation
        raise PoisonError(reason)

    @classmethod
    def assert_clean(cls):
        if cls.is_poisoned():
            raise PoisonError(f"System poisoned: {cls._reason}")
