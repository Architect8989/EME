import sys

from bootstrap.bootstrap import bootstrap
from core.system_state import SystemState
from core.logger import Logger
from core.mode_gate import ModeGate, Mode
from core.poison import Poison, PoisonError
from execution.action_executor import ActionExecutor
from execution.life_loop import LifeLoop


def main():
    # bootstrap must run first and only once
    info = bootstrap()

    # explicit initialization boundary
    token = SystemState._issue_bootstrap_token()
    SystemState.mark_initialized(token)

    # logging becomes legal only after init
    Logger.init()

    # initial authority state
    ModeGate.transition(Mode.PROBE)

    # executor owns backend and authority
    executor = ActionExecutor(environment_hash=info["environment_hash"])

    # life loop is the only long-running component
    loop = LifeLoop(executor)

    # example: probe-only startup loop
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
