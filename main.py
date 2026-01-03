import sys

if __name__ != "__main__":
    raise RuntimeError("main.py is not importable")


def main() -> None:
    from bootstrap.bootstrap import bootstrap

    info = bootstrap()

    from core.logger import Logger
    from core.mode_gate import ModeGate, Mode
    from core.poison import Poison
    from execution.action_executor import ActionExecutor
    from execution.life_loop import LifeLoop

    Logger.init()
    logger = Logger.get()

    ModeGate.transition(Mode.PROBE)

    executor = ActionExecutor(
        environment_hash=info["environment_hash"]
    )

    loop = LifeLoop(executor=executor, logger=logger)
    loop.run_experiment(action=None)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        try:
            from core.poison import Poison
            Poison.trigger(f"unhandled exception: {repr(e)}")
        finally:
            sys.exit(1)
