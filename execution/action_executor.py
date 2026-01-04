import uuid
from typing import Any

from core.mode_gate import ModeGate
from core.poison import Poison
from core.refusal_engine import RefusalEngine, RefusalReason
from core.calibration_profile import load_calibration
from core.system_state import SystemState
from execution.backend_contract import Result
from core.logger import log_event


class ExecutorToken:
    __slots__ = ("_id",)

    def __init__(self):
        self._id = uuid.uuid4().hex


class ActionExecutor:
    """
    Sole execution authority.

    Mechanical invariants:
    - Requires completed bootstrap
    - Exactly one executor token
    - Backend never exposed outside executor
    - Any ambiguity is terminal
    """

    __slots__ = ("_token", "_backend", "_env_hash", "_calibration")

    def __init__(self, *, environment_hash: str):
        SystemState.assert_initialized()
        Poison.assert_clean()

        if not isinstance(environment_hash, str) or not environment_hash:
            Poison.trigger("invalid environment hash")

        token = ExecutorToken()

        try:
            from body.linux_backend import LinuxBackend
        except BaseException as e:
            Poison.trigger(f"backend import failed: {repr(e)}")

        backend = LinuxBackend(token)

        self._token = token
        self._backend = backend
        self._env_hash = environment_hash

        try:
            self._calibration = load_calibration(environment_hash)
        except BaseException as e:
            Poison.trigger(f"calibration invalid: {repr(e)}")

    @property
    def backend(self):
        return self._backend

    @property
    def token(self):
        return self._token

    def execute(self, action: Any) -> Result:
        SystemState.assert_initialized()
        Poison.assert_clean()

        if action is None:
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "null action",
            )

        if not hasattr(action, "contract"):
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "action missing contract",
            )

        contract = action.contract

        if not hasattr(contract, "execute") or not hasattr(contract, "allowed_mode"):
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "invalid action contract",
            )

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

        except BaseException as e:
            RefusalEngine.kill(
                RefusalReason.EXECUTION_ERROR,
                repr(e),
            )

        finally:
            log_event("action.end", {"action": contract.name})
