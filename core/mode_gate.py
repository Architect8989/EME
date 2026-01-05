from enum import Enum
import threading

from core.poison import Poison


class Mode(Enum):
    STAGE_1 = "stage_1"     # newborn, single-action, sealed
    STAGE_2 = "stage_2"     # future (not reachable now)
    REFUSE = "refuse"


class ModeGate:
    """
    Absolute mode authority.

    Stage-1 invariants:
    - Mode is set exactly once
    - No transitions allowed
    - Any deviation is terminal
    """

    _lock = threading.Lock()
    _mode: Mode | None = None
    _locked: bool = False

    @classmethod
    def force(cls, mode: Mode) -> None:
        Poison.assert_clean()
        if not isinstance(mode, Mode):
            Poison.trigger("invalid mode force")

        with cls._lock:
            if cls._locked:
                Poison.trigger("mode already locked")

            cls._mode = mode
            cls._locked = True

    @classmethod
    def current(cls) -> Mode:
        Poison.assert_clean()
        with cls._lock:
            if not cls._locked or cls._mode is None:
                Poison.trigger("mode not initialized")
            return cls._mode

    @classmethod
    def assert_mode(cls, required: Mode) -> None:
        Poison.assert_clean()
        with cls._lock:
            if not cls._locked or cls._mode is None:
                Poison.trigger("mode not initialized")

            if cls._mode is not required:
                Poison.trigger(
                    f"mode violation: required={required.value}, current={cls._mode.value}"
    )
