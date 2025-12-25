"""
Run exactly one experiment.
Used by CLI and batch runner.
"""

from execution.life_loop import LifeLoop
from execution.action_executor import ActionExecutor
from core.logger import Logger

from actions.move_mouse import MoveMouse   # <-- NEW


def run():
    logger = Logger()
    executor = ActionExecutor()
    loop = LifeLoop(executor, logger)

    action = MoveMouse()                   # <-- USE MOTOR ACTION
    return loop.run_experiment(action)


if __name__ == "__main__":
    run()
