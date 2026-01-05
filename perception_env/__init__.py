from core.mode_gate import ModeGate, Mode
from core.poison import Poison

if ModeGate.current() == Mode.STAGE_1:
    Poison.trigger("perception_env accessed during Stage-1")
