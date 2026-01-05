from core.poison import Poison
from core.system_state import SystemState


class ProbeAction:
    """
    Inert probe placeholder.

    Enforced invariants:
    - Not instantiable
    - Not executable
    - Exists only as an identifier anchor
    - Any attempt to use is terminal
    """

    id = "probe.system_identity"

    def __init__(self, *args, **kwargs):
        Poison.trigger("ProbeAction instantiation forbidden")

    def _execute(self, *args, **kwargs):
        SystemState.assert_initialized()
        Poison.trigger("ProbeAction execution forbidden")

    def run(self, *args, **kwargs):
        Poison.trigger("ProbeAction direct run forbidden")
