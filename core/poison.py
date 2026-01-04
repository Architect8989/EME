import sys
import threading
from typing import Optional


class PoisonError(RuntimeError):
    pass


class Poison:
    """
    Terminal, irreversible poison latch.

    Mechanical invariants:
    - Write-once
    - Cannot be cleared
    - Dominates all execution paths
    - No filesystem access
    - No recovery or reset
    """

    _lock = threading.Lock()
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
    def trigger(cls, reason: str) -> None:
        if not isinstance(reason, str) or not reason:
            reason = "unspecified poison reason"

        with cls._lock:
            if cls._poisoned:
                raise PoisonError(f"system already poisoned: {cls._reason}")

            cls._poisoned = True
            cls._reason = reason

        sys.stderr.write(f"[POISONED] {reason}\n")
        sys.stderr.flush()

        raise PoisonError(reason)

    @classmethod
    def assert_clean(cls) -> None:
        with cls._lock:
            if cls._poisoned:
                raise PoisonError(f"system poisoned: {cls._reason}")
