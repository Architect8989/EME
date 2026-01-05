from dataclasses import dataclass
from typing import Callable, Iterable

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from core.state_snapshot import StateSnapshot
from execution.backend_contract import Result, ErrorCode


@dataclass(frozen=True)
class ActionContract:
    """
    Sole authorization surface for actions.

    Enforced invariants:
    - No OS effects outside executor
    - Mode strictly enforced
    - Pre / forbidden / post evaluated deterministically
    - Any ambiguity is terminal
    - No silent success or recovery
    """

    name: str
    allowed_mode: Mode
    precondition: Callable[[StateSnapshot], bool]
    postcondition: Callable[[StateSnapshot, StateSnapshot], bool]
    forbidden: Iterable[Callable[[StateSnapshot], bool]]
    max_impact: float

    def execute(
        self,
        *,
        backend,
        action: Callable[[], Result],
    ) -> Result:
        # absolute guards
        Poison.assert_clean()
        ModeGate.assert_allowed(require=self.allowed_mode)

        # ---- PRE STATE ----
        try:
            before = StateSnapshot.from_backend(backend)
        except BaseException as e:
            Poison.trigger(f"{self.name}: pre-state capture failed: {repr(e)}")

        # ---- PRECONDITION ----
        try:
            pre_ok = self.precondition(before)
        except BaseException as e:
            Poison.trigger(f"{self.name}: precondition error: {repr(e)}")

        if pre_ok is None:
            Poison.trigger(f"{self.name}: precondition indeterminate")

        if pre_ok is False:
            return Result.err_result(
                ErrorCode.PRECONDITION_VIOLATION,
                started_at_ns=0,
                finished_at_ns=0,
                reason="precondition_failed",
            )

        # ---- FORBIDDEN ----
        for forbid in self.forbidden:
            try:
                hit = forbid(before)
            except BaseException as e:
                Poison.trigger(f"{self.name}: forbidden check error: {repr(e)}")

            if hit:
                Poison.trigger(f"{self.name}: forbidden state detected")

        # ---- EXECUTE (DELEGATED ONLY) ----
        Poison.assert_clean()
        try:
            result = action()
        except BaseException as e:
            Poison.trigger(f"{self.name}: action execution error: {repr(e)}")

        if not isinstance(result, Result):
            Poison.trigger(f"{self.name}: non-Result returned")

        if not result.ok:
            return result

        # ---- POST STATE ----
        try:
            after = StateSnapshot.from_backend(backend)
        except BaseException as e:
            Poison.trigger(f"{self.name}: post-state capture failed: {repr(e)}")

        # ---- POSTCONDITION ----
        try:
            post_ok = self.postcondition(before, after)
        except BaseException as e:
            Poison.trigger(f"{self.name}: postcondition error: {repr(e)}")

        if post_ok is None:
            Poison.trigger(f"{self.name}: postcondition indeterminate")

        if post_ok is False:
            ModeGate.kill(f"{self.name}: postcondition violated")

        return result
