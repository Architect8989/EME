import sys


# main.py is NOT importable as a library
if __name__ != "__main__":
    raise RuntimeError("main.py is not importable. Execute it directly.")


def main():
    # ---- BOOTSTRAP (must be first observable action) ----
    from bootstrap.bootstrap import bootstrap

    info = bootstrap()  # hard-fails on ambiguity

    # ---- PROJECT IMPORTS (legal only after bootstrap) ----
    from core.logger import Logger
    from core.mode_gate import ModeGate, Mode
    from core.poison import Poison, PoisonError
    from execution.action_executor import ActionExecutor
    from execution.life_loop import LifeLoop

    # Platform/backend import is deferred and gated
    from body.linux_backend import LinuxBackend

    # ---- LOGGER INIT (post-bootstrap only) ----
    Logger.init()

    # ---- INITIAL AUTHORITY STATE ----
    ModeGate.arm(Mode.PROBE)

    # ---- BACKEND CREATION (under initialized + guarded state) ----
    backend = LinuxBackend()

    # ---- EXECUTOR HOLDS SOLE AUTHORITY ----
    executor = ActionExecutor(
        backend=backend,
        environment_hash=info["environment_hash"],
    )

    # ---- LIFE LOOP (only long-running component) ----
    loop = LifeLoop(executor)
    loop.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Any uncaught exception poisons the system and exits
        try:
            from core.poison import Poison
            Poison.trigger(f"unhandled exception: {e!r}")
        finally:
            sys.exit(1)
