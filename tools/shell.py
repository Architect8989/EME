from core.system_state import SystemState
from core.poison import Poison


class ShellDisabledError(RuntimeError):
    pass


def run_shell():
    """
    Shell execution is permanently disabled in this artifact.
    This function is a hard fail-closed sink.
    """
    SystemState.assert_initialized()
    Poison.assert_clean()
    raise ShellDisabledError(
        "Shell execution is forbidden in this build"
    )
