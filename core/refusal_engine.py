from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

from core.mode_gate import ModeGate
from core.poison import Poison


class RefusalLevel(Enum):
    REFUSE = auto()   # return only, no side effects
    ABORT = auto()    # poison + immediate exit
    KILL = auto()     # kill switch + exit
    POISON = auto()   # poison + exit


class RefusalReason(Enum):
    UNKNOWN_STATE = auto()
    PRECONDITION_FAILED = auto()
    POSTCONDITION_FAILED = auto()
    FORBIDDEN_STATE = auto()
    CALIBRATION_INVALID = auto()
    ENVIRONMENT_DRIFT = auto()
    EXECUTION_ERROR = auto()
    INTERNAL_ERROR = auto()


@dataclass(frozen=True)
class RefusalDecision:
    level: RefusalLevel
    reason: RefusalReason
    message: str


class RefusalEngine:
    _last: Optional[RefusalDecision] = None

    @classmethod
    def last_decision(cls) -> Optional[RefusalDecision]:
        return cls._last

    @classmethod
    def decide(
        cls,
        *,
        level: RefusalLevel,
        reason: RefusalReason,
        message: str,
    ) -> RefusalDecision:
        decision = RefusalDecision(level=level, reason=reason, message=message)
        cls._last = decision

        if level is RefusalLevel.REFUSE:
            # Explicitly non-terminal: caller must stop voluntarily
            return decision

        if level is RefusalLevel.ABORT:
            # Terminal: poison and exit immediately
            Poison.trigger(f"{reason.name}: {message}")

        if level is RefusalLevel.POISON:
            # Terminal: poison and exit immediately
            Poison.trigger(f"{reason.name}: {message}")

        if level is RefusalLevel.KILL:
            # Terminal: kill switch and exit immediately
            ModeGate.kill(f"{reason.name}: {message}")

        # No execution may continue past this point
        raise RuntimeError("RefusalEngine reached unreachable state")

    @classmethod
    def refuse(cls, reason: RefusalReason, message: str) -> RefusalDecision:
        return cls.decide(
            level=RefusalLevel.REFUSE,
            reason=reason,
            message=message,
        )

    @classmethod
    def abort(cls, reason: RefusalReason, message: str) -> None:
        cls.decide(
            level=RefusalLevel.ABORT,
            reason=reason,
            message=message,
        )

    @classmethod
    def kill(cls, reason: RefusalReason, message: str) -> None:
        cls.decide(
            level=RefusalLevel.KILL,
            reason=reason,
            message=message,
        )

    @classmethod
    def poison(cls, reason: RefusalReason, message: str) -> None:
        cls.decide(
            level=RefusalLevel.POISON,
            reason=reason,
            message=message,
        )
