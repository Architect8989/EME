from dataclasses import dataclass
from typing import Callable, Iterable

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from core.state_snapshot import StateSnapshot
from execution.backend_contract import BackendBase, Result, ErrorCode


@dataclass(frozen=True)
class ActionContract:
    name: str
    allowed_mode: Mode
    precondition: Callable[[StateSnapshot], bool]
    postcondition: Callable[[StateSnapshot, StateSnapshot], bool]
    forbidden: Iterable[Callable[[StateSnapshot], bool]]
    max_impact: float

    def execute(
        self,
        *,
        backend: BackendBase,
        action: Callable[[], Result],
    ) -> Result:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=self.allowed_mode)

        try:
            before = StateSnapshot.from_backend(backend)
        except Exception as e:
            Poison.trigger(f"{self.name}: failed to capture pre-action state: {e}")

        try:
            pre_ok = self.precondition(before)
        except Exception as e:
            Poison.trigger(f"{self.name}: precondition evaluation error: {e}")

        if pre_ok is False:
            return Result.err(ErrorCode.PRECONDITION_FAILED)

        if pre_ok is None:
            Poison.trigger(f"{self.name}: precondition indeterminate")

        for forbid in self.forbidden:
            try:
                forbidden_hit = forbid(before)
            except Exception as e:
                Poison.trigger(f"{self.name}: forbidden check error: {e}")

            if forbidden_hit:
                Poison.trigger(f"{self.name}: forbidden state detected")

        Poison.assert_clean()
        result = action()

        if not result.ok:
            return result

        try:
            after = StateSnapshot.from_backend(backend)
        except Exception as e:
            Poison.trigger(f"{self.name}: failed to capture post-action state: {e}")

        try:
            post_ok = self.postcondition(before, after)
        except Exception as e:
            Poison.trigger(f"{self.name}: postcondition evaluation error: {e}")

        if post_ok is False:
            ModeGate.kill(f"{self.name}: postcondition violated")

        if post_ok is None:
            Poison.trigger(f"{self.name}: postcondition indeterminate")

        return result
