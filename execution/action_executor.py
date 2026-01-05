from typing import Any

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from core.system_state import SystemState
from execution.backend_contract import Result
from core.logger import log_event


class ExecutorToken:
    __slots__ = ()


class ActionExecutor:
    """
    Stage-1 execution authority.

    Invariants:
    - System initialized
    - Stage-1 mode only
    - Exactly one allowed action
    - Any deviation is terminal
    """

    __slots__ = ("_token", "_backend")

    def __init__(self) -> None:
        SystemState.assert_initialized()
        Poison.assert_clean()
        ModeGate.assert_mode(Mode.STAGE_1)

        token = ExecutorToken()

        try:
            from body.linux_backend import LinuxBackend
        except BaseException as e:
            Poison.trigger(f"backend import failed: {repr(e)}")

        self._backend = LinuxBackend(token)
        self._token = token

    def execute(self, action: Any) -> Result:
        SystemState.assert_initialized()
        Poison.assert_clean()
        ModeGate.assert_mode(Mode.STAGE_1)

        # Hard whitelist: only MoveMouse1px is allowed
        from actions.move_mouse_1px import MoveMouse1px

        if not isinstance(action, MoveMouse1px):
            Poison.trigger("non-Stage-1 action attempted")

        log_event("action.begin", {"action": "move_mouse_1px"})

        try:
            result = action._execute(self._backend)

            if not isinstance(result, Result):
                Poison.trigger("invalid execution result")

            return result

        except BaseException as e:
            Poison.trigger(f"action execution failed: {repr(e)}")

        finally:
            log_event("action.end", {"action": "move_mouse_1px"})
