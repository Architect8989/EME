import sys

# main.py must never be imported
if __name__ != "__main__":
    raise RuntimeError("main.py is not importable")


def main() -> None:
    # ---- EARLIEST HALT BOUNDARY ----
    from core.os_detection import assert_linux_x11
    from core.system_state import SystemState
    from core.poison import Poison
    from core.mode_gate import ModeGate, Mode

    try:
        # Platform determinism
        assert_linux_x11()

        # Issue bootstrap token exactly once
        bootstrap_token = SystemState._issue_bootstrap_token()

        # ---- BOOTSTRAP ----
        from bootstrap.bootstrap import bootstrap
        bootstrap(bootstrap_token)

        # Mark initialized exactly once
        SystemState.mark_initialized(bootstrap_token)

        # Enforce Stage-1 (cannot change after this)
        ModeGate.assert_mode(Mode.STAGE_1)

        # ---- EXECUTOR WORLD (STAGE-1 ONLY) ----
        from core.logger import Logger
        from execution.action_executor import ActionExecutor
        from execution.life_loop import LifeLoop
        from actions.move_mouse_1px import MoveMouse1px

        Logger.init()
        logger = Logger.get()

        executor = ActionExecutor()

        loop = LifeLoop(executor=executor, logger=logger)

        # FORCED single action — no optionality
        action = MoveMouse1px()

        loop.run_stage_1(action=action)

    except BaseException as e:
        try:
            Poison.trigger(f"unhandled exception: {repr(e)}")
        finally:
            sys.exit(1)


if __name__ == "__main__":
    main()
