from enum import Enum
import threading
import sys
import time

from core.poison import Poison


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
    _armed_for_execute: bool = False
    _killed: bool = False
    _since: float | None = None

    @classmethod
    def current_mode(cls) -> Mode:
        Poison.assert_clean()
        with cls._lock:
            return cls._mode

    @classmethod
    def arm_execute(cls):
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                raise KillSwitch("system killed")
            if cls._armed_for_execute:
                return
            cls._armed_for_execute = True

    @classmethod
    def transition(cls, target: Mode):
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                raise KillSwitch("system killed")

            # monotonic authority rules
            if target == Mode.EXECUTE and not cls._armed_for_execute:
                Poison.trigger("EXECUTE transition without explicit arming")

            if cls._mode == Mode.EXECUTE and target != Mode.EXECUTE:
                Poison.trigger("illegal transition out of EXECUTE")

            cls._mode = target
            cls._since = time.time()

    @classmethod
    def assert_allowed(cls, *, require: Mode):
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                raise KillSwitch("system killed")

            if cls._mode is not require:
                raise ModeViolation(
                    f"mode violation: required={require.value}, current={cls._mode.value}"
                )

    @classmethod
    def kill(cls, reason: str):
        with cls._lock:
            if cls._killed:
                raise KillSwitch("system already killed")
            cls._killed = True
            cls._mode = Mode.REFUSE
            cls._armed_for_execute = False

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
