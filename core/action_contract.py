from dataclasses import dataclass
from typing import Callable, Any, Iterable

from core.mode_gate import ModeGate, Mode
from core.state_snapshot import StateSnapshot, StateSnapshotError
from execution.backend_contract import BackendBase, Result, ErrorCode


class ActionContractViolation(Exception):
    pass


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
        ModeGate.assert_allowed(require=self.allowed_mode)

        try:
            before = StateSnapshot.from_backend(backend)
        except StateSnapshotError as e:
            raise ActionContractViolation(f"{self.name}: state capture failed (before): {e}")

        if not self.precondition(before):
            return Result.err(ErrorCode.PRECONDITION_FAILED)

        for forbid in self.forbidden:
            if forbid(before):
                ModeGate.kill(f"{self.name}: forbidden state detected")

        result = action()
        if not result.ok:
            return result

        try:
            after = StateSnapshot.from_backend(backend)
        except StateSnapshotError as e:
            ModeGate.kill(f"{self.name}: state capture failed (after): {e}")
            raise

        if not self.postcondition(before, after):
            ModeGate.kill(f"{self.name}: postcondition violated")

        return result
