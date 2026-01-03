from core.system_state import SystemState
from core.poison import Poison


class ShellDisabledError(RuntimeError):
    pass


def run_shell(cmd: str):
    SystemState.assert_initialized()
    Poison.assert_clean()
    raise ShellDisabledError(
        "tools.shell is disabled in this build. "
        "Shell execution is not permitted outside the executor."
    )
