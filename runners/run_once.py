from execution.life_loop import LifeLoop
from execution.action_executor import ActionExecutor
from core.logger import Logger
from actions.probe_action import ProbeAction

loop = LifeLoop(ActionExecutor(), Logger())
loop.run_experiment(ProbeAction())
