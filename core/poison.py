import sys
import threading
from typing import Optional


class PoisonError(RuntimeError):
    pass


class Poison:
    """
    Terminal, irreversible poison latch.

    Mechanical invariants (enforced):
    - Write-once
    - Global and permanent
    - Dominates all execution paths
    - No reset, no recovery, no suppression
    - Once triggered, execution must not continue
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
                # already terminal; do not allow continuation
                sys.stderr.write(
                    f"[POISONED:REENTER] {cls._reason}\n"
                )
                sys.stderr.flush()
                sys.exit(1)

            cls._poisoned = True
            cls._reason = reason

        # irreversible external signal
        sys.stderr.write(f"[POISONED] {reason}\n")
        sys.stderr.flush()

        # absolute termination point
        sys.exit(1)

    @classmethod
    def assert_clean(cls) -> None:
        with cls._lock:
            if cls._poisoned:
                sys.stderr.write(
                    f"[POISONED:ASSERT] {cls._reason}\n"
                )
                sys.stderr.flush()
                sys.exit(1)
