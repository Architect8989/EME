from execution.life_loop import LifeLoop
from execution.action_executor import ActionExecutor
from core.logger import Logger
from actions.probe_action import ProbeAction

loop = LifeLoop(ActionExecutor(), Logger())
loop.run_experiment(ProbeAction())
def run():
    # whatever the script does in __main__
    # move that logic here
    main_record = run_probe()   # or whatever your one-shot call is
    return main_record
