import uuid
from typing import Any

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from core.refusal_engine import RefusalEngine, RefusalReason
from core.calibration_profile import load_calibration, CalibrationError
from core.system_state import SystemState
from execution.backend_contract import BackendBase, Result
from core.logger import log_event


class ExecutorToken:
    __slots__ = ("_id",)

    def __init__(self):
        self._id = uuid.uuid4().hex


class ActionExecutor:
    def __init__(self, *, backend: BackendBase, environment_hash: str):
        SystemState.assert_initialized()

        self._token = ExecutorToken()
        self._backend = backend
        self._env_hash = environment_hash

        self._backend._bind_executor(self._token)

        try:
            self._calibration = load_calibration(environment_hash)
        except CalibrationError as e:
            RefusalEngine.abort(
                RefusalReason.CALIBRATION_INVALID,
                str(e),
            )
            raise

    def execute(self, action: Any) -> Result:
        SystemState.assert_initialized()

        if Poison.is_poisoned():
            raise RuntimeError("executor blocked: system poisoned")

        if not hasattr(action, "contract"):
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "action missing contract",
            )

        contract = action.contract

        ModeGate.assert_allowed(require=contract.allowed_mode)

        log_event("action.begin", {"action": contract.name})

        try:
            result = contract.execute(
                backend=self._backend,
                action=lambda: action._execute(self._backend),
            )

            if not isinstance(result, Result):
                RefusalEngine.kill(
                    RefusalReason.INTERNAL_ERROR,
                    "non-Result leaked from action",
                )

            return result

        except Exception as e:
            RefusalEngine.kill(
                RefusalReason.EXECUTION_ERROR,
                repr(e),
            )
            raise

        finally:
            log_event("action.end", {"action": contract.name})
