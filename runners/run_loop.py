from core.system_state import SystemState


class RunnerDisabledError(RuntimeError):
    pass


def run_loop(*args, **kwargs):
    SystemState.assert_initialized()
    raise RunnerDisabledError(
        "run_loop is disabled. Use bootstrap + executor only."
    )


if __name__ == "__main__":
    run_loop()
