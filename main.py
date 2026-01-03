import sys

from bootstrap.bootstrap import bootstrap
from core.logger import Logger
from core.mode_gate import ModeGate, Mode
from core.poison import Poison, PoisonError
from execution.action_executor import ActionExecutor
from execution.life_loop import LifeLoop
from body.linux_backend import LinuxBackend


def main():
    # ---- bootstrap: must be first, must succeed ----
    info = bootstrap()

    # ---- logging becomes legal only after bootstrap ----
    Logger.init()

    # ---- initial authority state ----
    ModeGate.arm(Mode.PROBE)

    # ---- backend is created under initialized + guarded state ----
    backend = LinuxBackend()

    # ---- executor is the sole authority holder ----
    executor = ActionExecutor(
        backend=backend,
        environment_hash=info["environment_hash"],
    )

    # ---- life loop is the only long-running component ----
    loop = LifeLoop(executor)

    loop.run()


if __name__ == "__main__":
    try:
        main()
    except PoisonError:
        sys.exit(1)
    except BaseException as e:
        try:
            Poison.trigger(f"unhandled exception: {e!r}")
        finally:
            sys.exit(1)
