from core.system_state import SystemState


class RunnerDisabledError(RuntimeError):
    pass


def run_batch(*args, **kwargs):
    SystemState.assert_initialized()
    raise RunnerDisabledError(
        "run_batch is disabled. Use bootstrap + executor only."
    )


if __name__ == "__main__":
    run_batch()
