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
    """
    Unforgeable executor capability.
    Identity-only, single-holder.
    """
    __slots__ = ("_id",)

    def __init__(self) -> None:
        self._id = uuid.uuid4().hex


class ActionExecutor:
    """
    Sole execution authority.

    Enforced invariants:
    - System must be fully initialized
    - Exactly one executor token per executor instance
    - Backend never exposed without executor context
    - Poison dominates all execution
    - Any ambiguity is terminal
    """

    __slots__ = ("_token", "_backend", "_env_hash", "_calibration")

    def __init__(self, *, environment_hash: str) -> None:
        # ---- GLOBAL LATCHES ----
        SystemState.assert_initialized()
        Poison.assert_clean()

        if not isinstance(environment_hash, str) or not environment_hash:
            Poison.trigger("invalid environment hash")

        # ---- EXECUTOR CAPABILITY ----
        token = ExecutorToken()

        # ---- BACKEND BINDING (EXECUTOR-ONLY) ----
        try:
            from body.linux_backend import LinuxBackend
        except BaseException as e:
            Poison.trigger(f"backend import failed: {repr(e)}")

        backend = LinuxBackend(token)

        # Seal ownership
        self._token = token
        self._backend = backend
        self._env_hash = environment_hash

        # ---- CALIBRATION (MANDATORY) ----
        try:
            self._calibration = load_calibration(environment_hash)
        except BaseException as e:
            Poison.trigger(f"calibration invalid: {repr(e)}")

    # ─────────────────────────────
    # NO BACKEND / TOKEN ESCAPE
    # ─────────────────────────────

    def _get_backend(self, token: ExecutorToken):
        if token is not self._token:
            Poison.trigger("executor token mismatch")
        return self._backend

    # ─────────────────────────────
    # EXECUTION PATH (FAIL-CLOSED)
    # ─────────────────────────────

    def execute(self, action: Any) -> Result:
        # absolute guards
        SystemState.assert_initialized()
        Poison.assert_clean()

        if action is None:
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "null action",
            )

        if not hasattr(action, "_execute") or not hasattr(action, "contract"):
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "invalid action object",
            )

        contract = action.contract

        if (
            not hasattr(contract, "execute")
            or not hasattr(contract, "allowed_mode")
            or not hasattr(contract, "name")
        ):
            RefusalEngine.kill(
                RefusalReason.INTERNAL_ERROR,
                "invalid action contract",
            )

        ModeGate.assert_allowed(require=contract.allowed_mode)

        log_event("action.begin", {"action": contract.name})

        try:
            # backend never leaks outside executor scope
            backend = self._get_backend(self._token)

            result = contract.execute(
                backend=backend,
                action=lambda: action._execute(backend),
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
            # poison may already have exited
            log_event("action.end", {"action": contract.name})
