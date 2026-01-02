from core.system_state import SystemState


class ProbeAction:
    id = "probe.system_identity"

    def run(self):
        SystemState.assert_initialized()
        raise RuntimeError(
            "ProbeAction is inert in this build. "
            "Execution must occur through the executor."
        )
