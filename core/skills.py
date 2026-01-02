from dataclasses import dataclass
from typing import List, Callable

from core.mode_gate import ModeGate, Mode
from core.state_snapshot import StateSnapshot
from core.refusal_engine import RefusalEngine, RefusalReason
from core.outcome_ledger import OutcomeLedger
from core.action_contract import ActionContract
from execution.backend_contract import BackendBase, Result


class SkillExecutionError(Exception):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    environment_hash: str
    calibration_hash: str
    actions: List[ActionContract]
    terminal_condition: Callable[[StateSnapshot], bool]

    def execute(
        self,
        *,
        backend: BackendBase,
        ledger: OutcomeLedger,
        environment_hash: str,
        calibration_hash: str,
    ) -> bool:
        ModeGate.assert_allowed(require=Mode.EXECUTE)

        if environment_hash != self.environment_hash:
            RefusalEngine.kill(
                RefusalReason.ENVIRONMENT_DRIFT,
                f"Skill {self.name}: environment mismatch",
            )

        if calibration_hash != self.calibration_hash:
            RefusalEngine.kill(
                RefusalReason.CALIBRATION_INVALID,
                f"Skill {self.name}: calibration mismatch",
            )

        before = StateSnapshot.from_backend(backend)

        for contract in self.actions:
            result = contract.execute(
                backend=backend,
                action=lambda c=contract: c  # action already bound inside contract
            )

            ledger.append(
                environment_hash=environment_hash,
                calibration_hash=calibration_hash,
                state_before_hash=before.screen_hash,
                action={"skill": self.name, "contract": contract.name},
                result={"ok": result.ok, "code": result.code.name},
                state_after_hash=None,
                refusal=None,
            )

            if not result.ok:
                RefusalEngine.abort(
                    RefusalReason.EXECUTION_ERROR,
                    f"Skill {self.name}: action failed",
                )
                return False

            before = StateSnapshot.from_backend(backend)

        if not self.terminal_condition(before):
            RefusalEngine.kill(
                RefusalReason.POSTCONDITION_FAILED,
                f"Skill {self.name}: terminal condition not met",
            )

        return True
