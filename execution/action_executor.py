import uuid
from typing import Any

from core.mode_gate import ModeGate
from core.poison import Poison
from core.refusal_engine import RefusalEngine, RefusalReason
from core.calibration_profile import load_calibration, CalibrationError
from core.system_state import SystemState
from execution.backend_contract import Result
from core.logger import log_event


class ExecutorToken:
    __slots__ = ("_id",)

    def __init__(self):
        self._id = uuid.uuid4().hex


class ActionExecutor:
    __slots__ = ("_token", "_backend", "_env_hash", "_calibration")

    def __init__(self, *, environment_hash: str):
        # ---- hard guards ----
        SystemState.assert_initialized()
        Poison.assert_clean()

        # ---- executor authority ----
        token = ExecutorToken()

        # ---- lazy backend import (platform-safe) ----
        try:
            from body.linux_backend import LinuxBackend
        except Exception as e:
            Poison.trigger(f"backend import failed: {e!r}")
            raise

        backend = LinuxBackend(token)

        self._token = token
        self._backend = backend
        self._env_hash = environment_hash

        # ---- calibration is mandatory ----
        try:
            self._calibration = load_calibration(environment_hash)
        except CalibrationError as e:
            RefusalEngine.abort(
                RefusalReason.CALIBRATION_INVALID,
                str(e),
            )
            raise

    def execute(self, action: Any) -> Result:
        # ---- global invariants ----
        SystemState.assert_initialized()
        Poison.assert_clean()

        if not hasattr(action, "contract"):
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "action missing contract",
            )

        contract = action.contract

        # ---- authority gate ----
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
