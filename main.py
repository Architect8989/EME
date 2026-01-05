import sys


# main.py must never be imported
if __name__ != "__main__":
    raise RuntimeError("main.py is not importable")


def main() -> None:
    # ---- EARLIEST POSSIBLE HALT BOUNDARY ----
    # No other imports before platform + bootstrap sealing
    from core.os_detection import assert_linux_x11
    from core.system_state import SystemState
    from core.poison import Poison

    try:
        # Hard platform determinism
        assert_linux_x11()

        # Issue bootstrap token exactly once
        bootstrap_token = SystemState._issue_bootstrap_token()

        # ---- BOOTSTRAP PHASE ----
        from bootstrap.bootstrap import bootstrap

        info = bootstrap(bootstrap_token)

        # Mark system initialized exactly once
        SystemState.mark_initialized(bootstrap_token)

        # ---- POST-BOOTSTRAP (EXECUTOR-ONLY WORLD) ----
        from core.logger import Logger
        from core.mode_gate import ModeGate, Mode
        from execution.action_executor import ActionExecutor
        from execution.life_loop import LifeLoop

        Logger.init()
        logger = Logger.get()

        ModeGate.transition(Mode.PROBE)

        executor = ActionExecutor(
            environment_hash=info["environment_hash"]
        )

        loop = LifeLoop(executor=executor, logger=logger)

        # No free actions, no side paths
        loop.run_experiment(action=None)

    except BaseException as e:
        # Any ambiguity or failure is terminal
        try:
            Poison.trigger(f"unhandled exception: {repr(e)}")
        finally:
            sys.exit(1)


if __name__ == "__main__":
    main()
