from core.system_state import SystemState


class ShellDisabledError(RuntimeError):
    pass


def run_shell(cmd: str):
    SystemState.assert_initialized()
    raise ShellDisabledError(
        "tools.shell is disabled in this build. "
        "Shell execution is not permitted outside the executor."
    )
