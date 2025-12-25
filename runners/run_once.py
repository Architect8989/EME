"""
Run exactly one experiment.
Used by CLI and batch runner.
"""

from execution.life_loop import LifeLoop
from execution.action_executor import ActionExecutor
from actions.probe_action import ProbeAction
from core.logger import Logger


def run():
    logger = Logger()
    executor = ActionExecutor()
    loop = LifeLoop(executor, logger)

    action = ProbeAction()
    return loop.run_experiment(action)


if __name__ == "__main__":
    run()
