import os

os.environ.setdefault("DISPLAY", ":0")

from execution.life_loop import LifeLoop
from execution.action_executor import ActionExecutor
from core.logger import Logger

# choose a trivial, reversible action ONLY
from actions.move_mouse import MoveMouse


def run():
    logger = Logger()
    executor = ActionExecutor()
    loop = LifeLoop(executor, logger)

    action = MoveMouse()
    return loop.run_experiment(action)


if __name__ == "__main__":
    rec = run()
    print(rec)
