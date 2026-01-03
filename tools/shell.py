from core.system_state import SystemState
from core.poison import Poison


class ShellDisabledError(RuntimeError):
    pass


def run_shell(*_, **__):
    SystemState.assert_initialized()
    Poison.assert_clean()
    raise ShellDisabledError(
        "Shell execution is disabled. "
        "All OS effects must pass through the executor."
    )
