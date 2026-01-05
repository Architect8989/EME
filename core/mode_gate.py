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

    Enforced invariants:
    - Single global mode
    - Explicit, monotonic transitions
    - EXECUTE requires explicit arming
    - No transition out of EXECUTE
    - No silent no-ops
    - Kill is terminal and irreversible
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
            if cls._killed:
                Poison.trigger("mode gate killed")
            return cls._mode

    @classmethod
    def arm_execute(cls) -> None:
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate killed")

            if cls._mode is not Mode.PROBE and cls._mode is not Mode.CALIBRATE:
                Poison.trigger("arm_execute from invalid mode")

            if cls._armed_for_execute:
                Poison.trigger("duplicate arm_execute")

            cls._armed_for_execute = True

    @classmethod
    def transition(cls, target: Mode) -> None:
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate killed")

            if not isinstance(target, Mode):
                Poison.trigger("invalid mode transition target")

            # monotonic, explicit transitions only
            if cls._mode is Mode.EXECUTE and target is not Mode.EXECUTE:
                Poison.trigger("illegal transition out of EXECUTE")

            if target is Mode.EXECUTE:
                if not cls._armed_for_execute:
                    Poison.trigger("EXECUTE transition without arming")
                # consume the arm exactly once
                cls._armed_for_execute = False

            cls._mode = target
            cls._since = time.time()

    @classmethod
    def assert_allowed(cls, *, require: Mode) -> None:
        Poison.assert_clean()
        with cls._lock:
            if cls._killed:
                Poison.trigger("mode gate killed")

            if cls._mode is not require:
                Poison.trigger(
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
            cls._since = None

        Poison.trigger(f"mode gate kill: {reason}")
