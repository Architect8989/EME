from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

from core.mode_gate import ModeGate
from core.poison import Poison


class RefusalLevel(Enum):
    REFUSE = auto()
    ABORT = auto()
    KILL = auto()
    POISON = auto()


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
    ):
        decision = RefusalDecision(level=level, reason=reason, message=message)
        cls._last = decision

        if level == RefusalLevel.REFUSE:
            return decision

        if level == RefusalLevel.ABORT:
            ModeGate.disarm()
            return decision

        if level == RefusalLevel.KILL:
            ModeGate.kill(f"{reason.name}: {message}")

        if level == RefusalLevel.POISON:
            Poison.trigger(f"{reason.name}: {message}")

        raise RuntimeError("Unreachable refusal level")

    @classmethod
    def refuse(cls, reason: RefusalReason, message: str):
        return cls.decide(
            level=RefusalLevel.REFUSE,
            reason=reason,
            message=message,
        )

    @classmethod
    def abort(cls, reason: RefusalReason, message: str):
        return cls.decide(
            level=RefusalLevel.ABORT,
            reason=reason,
            message=message,
        )

    @classmethod
    def kill(cls, reason: RefusalReason, message: str):
        return cls.decide(
            level=RefusalLevel.KILL,
            reason=reason,
            message=message,
        )

    @classmethod
    def poison(cls, reason: RefusalReason, message: str):
        return cls.decide(
            level=RefusalLevel.POISON,
            reason=reason,
            message=message,
            )
