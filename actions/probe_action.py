from core.system_state import SystemState


class ProbeAction:
    id = "probe.system_identity"

    def __init__(self, *args, **kwargs):
        # Construction itself is forbidden outside executor context
        raise RuntimeError(
            "ProbeAction cannot be instantiated directly. "
            "Use main.py and the executor path only."
        )

    def run(self):
        # Mechanical backstop — should be unreachable
        SystemState.assert_initialized()
        raise RuntimeError(
            "ProbeAction is inert in this artifact. "
            "Direct execution paths are forbidden."
        )
