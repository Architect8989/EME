import sys
import threading
from pathlib import Path
from typing import Optional


POISON_MARKER = Path(".POISONED")


class PoisonError(Exception):
    pass


class Poison:
    _lock = threading.RLock()
    _poisoned: bool = False
    _reason: Optional[str] = None

    @classmethod
    def _load_marker(cls):
        if POISON_MARKER.exists():
            try:
                reason = POISON_MARKER.read_text().strip()
            except Exception:
                reason = "unknown (marker unreadable)"
            cls._poisoned = True
            cls._reason = reason

    @classmethod
    def _write_marker(cls, reason: str):
        try:
            POISON_MARKER.write_text(reason)
        except Exception:
            pass  # even if this fails, memory poison still holds

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
            cls._write_marker(reason)

        sys.stderr.write(f"[POISONED] {reason}\n")
        sys.stderr.flush()

        raise PoisonError(reason)

    @classmethod
    def assert_clean(cls):
        with cls._lock:
            if not cls._poisoned and POISON_MARKER.exists():
                cls._load_marker()

            if cls._poisoned:
                raise PoisonError(f"System poisoned: {cls._reason}")

    @classmethod
    def clear_for_human_only(cls):
        """
        Explicit, manual recovery.
        Must never be called by runtime code.
        """
        with cls._lock:
            cls._poisoned = False
            cls._reason = None
            try:
                if POISON_MARKER.exists():
                    POISON_MARKER.unlink()
            except Exception:
                pass
