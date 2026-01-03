import sys
import threading
from typing import Optional


class PoisonError(Exception):
    pass


class Poison:
    """
    Terminal, irreversible poison latch.
    No filesystem access.
    No recovery path.
    Fail-closed by construction.
    """

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
                raise PoisonError(f"System already poisoned: {cls._reason}")

            cls._poisoned = True
            cls._reason = reason

        sys.stderr.write(f"[POISONED] {reason}\n")
        sys.stderr.flush()

        raise PoisonError(reason)

    @classmethod
    def assert_clean(cls):
        with cls._lock:
            if cls._poisoned:
                raise PoisonError(f"System poisoned: {cls._reason}")
