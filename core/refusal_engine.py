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
    def _record(cls, decision: RefusalDecision) -> None:
        cls._last = decision

    @classmethod
    def decide(
        cls,
        *,
        level: RefusalLevel,
        reason: RefusalReason,
        message: str,
    ) -> None:
        decision = RefusalDecision(level=level, reason=reason, message=message)
        cls._record(decision)

        if level is RefusalLevel.REFUSE:
            Poison.trigger(f"refusal reached non-terminal state: {reason.name}")

        if level is RefusalLevel.ABORT:
            Poison.trigger(f"{reason.name}: {message}")

        if level is RefusalLevel.POISON:
            Poison.trigger(f"{reason.name}: {message}")

        if level is RefusalLevel.KILL:
            ModeGate.kill(f"{reason.name}: {message}")

        Poison.trigger("refusal engine unreachable state")

    @classmethod
    def refuse(cls, reason: RefusalReason, message: str) -> None:
        cls.decide(
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
