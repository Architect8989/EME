from enum import Enum
import threading
import time

from core.poison import Poison


class Mode(Enum):
    REFUSE = "refuse"
    PROBE = "probe"
    CALIBRATE = "calibrate"
    EXECUTE = "execute"


class ModeViolation(RuntimeError):
    pass


class ModeGate:
    """
    Deterministic, fail-closed mode authority.

    Mechanical invariants:
    - Single global mode
    - Explicit, monotonic transitions
    - EXECUTE requires prior arming
    - No recovery after kill
    - No side effects outside poison
    """

    _lock = threading.Lock()
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
    def arm_execute(cls) -> None:
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate killed")
            if cls._armed_for_execute:
                return
            cls._armed_for_execute = True

    @classmethod
    def transition(cls, target: Mode) -> None:
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate killed")

            if target == Mode.EXECUTE and not cls._armed_for_execute:
                Poison.trigger("EXECUTE transition without arming")

            if cls._mode == Mode.EXECUTE and target is not Mode.EXECUTE:
                Poison.trigger("illegal transition out of EXECUTE")

            cls._mode = target
            cls._since = time.time()

    @classmethod
    def assert_allowed(cls, *, require: Mode) -> None:
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate killed")

            if cls._mode is not require:
                raise ModeViolation(
                    f"mode violation: required={require.value}, current={cls._mode.value}"
                )

    @classmethod
    def kill(cls, reason: str) -> None:
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate already killed")

            cls._killed = True
            cls._mode = Mode.REFUSE
            cls._armed_for_execute = False

        Poison.trigger(f"mode gate kill: {reason}")
