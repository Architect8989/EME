from enum import Enum
import threading
import sys
import time

from core.poison import Poison, PoisonError


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
        Poison.assert_clean()
        with cls._lock:
            return cls._mode

    @classmethod
    def arm(cls, mode: Mode):
        Poison.assert_clean()
        with cls._lock:
            if cls._kill:
                raise KillSwitch("System is killed")

            if mode == Mode.EXECUTE and not cls._armed:
                Poison.trigger("EXECUTE requested without prior arming")

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
        Poison.assert_clean()
        with cls._lock:
            if cls._kill:
                raise KillSwitch("System is killed")
            cls._armed = True

    @classmethod
    def assert_allowed(cls, *, require: Mode):
        Poison.assert_clean()
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
        with cls._lock:
            cls._kill = True
            cls._mode = Mode.REFUSE
            cls._armed = False
        sys.stderr.write(f"[KILL] {reason}\n")
        sys.stderr.flush()
        raise KillSwitch(reason)


def require_mode(mode: Mode):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            Poison.assert_clean()
            ModeGate.assert_allowed(require=mode)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


ModeGate.disarm()
