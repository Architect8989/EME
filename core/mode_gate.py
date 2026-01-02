# core/mode_gate.py
"""
Authoritative execution gate.
Nothing executes unless this file allows it.

Modes:
- REFUSE     : default, zero authority
- PROBE      : observation only, no side effects
- CALIBRATE  : controlled actuator tests
- EXECUTE    : frozen-skill execution only

Any ambiguity → REFUSE.
"""

from enum import Enum
import threading
import sys
import time


class Mode(Enum):
    REFUSE = "refuse"
    PROBE = "probe"
    CALIBRATE = "calibrate"
    EXECUTE = "execute"


class ModeViolation(Exception):
    pass


class KillSwitch(Exception):
    pass


class ModeGate:
    _lock = threading.RLock()
    _mode: Mode = Mode.REFUSE
    _armed: bool = False
    _kill: bool = False
    _since: float | None = None

    @classmethod
    def current_mode(cls) -> Mode:
        return cls._mode

    @classmethod
    def arm(cls, mode: Mode):
        with cls._lock:
            if cls._kill:
                raise KillSwitch("System is killed")

            if mode == Mode.EXECUTE and not cls._armed:
                raise ModeViolation("EXECUTE requested without prior arming")

            cls._mode = mode
            cls._since = time.time()

    @classmethod
    def disarm(cls):
        with cls._lock:
            cls._mode = Mode.REFUSE
            cls._armed = False
            cls._since = None

    @classmethod
    def arm_execute(cls):
        """
        Explicit one-way transition.
        Must be called only after:
        - environment contract verified
        - calibration valid
        - skill frozen
        """
        with cls._lock:
            if cls._kill:
                raise KillSwitch("System is killed")
            cls._armed = True

    @classmethod
    def assert_allowed(cls, *, require: Mode):
        with cls._lock:
            if cls._kill:
                raise KillSwitch("Kill switch engaged")

            if cls._mode != require:
                raise ModeViolation(
                    f"Operation requires mode={require.value}, "
                    f"current={cls._mode.value}"
                )

    @classmethod
    def kill(cls, reason: str):
        """
        Irreversible termination.
        Used on safety violations.
        """
        with cls._lock:
            cls._kill = True
            cls._mode = Mode.REFUSE
            cls._armed = False
        sys.stderr.write(f"[KILL] {reason}\n")
        sys.stderr.flush()
        raise KillSwitch(reason)


# ---- Decorators for executors ----

def require_mode(mode: Mode):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            ModeGate.assert_allowed(require=mode)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---- Hard default on import ----
ModeGate.disarm()
